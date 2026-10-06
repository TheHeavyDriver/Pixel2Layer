"""SAM 2 LoRA fine-tuning CLI for design-graphic segmentation.

Two-step workflow (box-prompted port of the official SAM 2 LoRA recipe):

    # 1. Build a pseudo-label dataset from design-graphic images
    python -m app.services.finetune.train prepare --raw data/finetune/raw \\
        --dataset data/finetune/datasets --name logo-masks
    # 2. Fine-tune the SAM 2 image encoder with LoRA (saves only LoRA weights)
    python -m app.services.finetune.train train --dataset data/finetune/datasets/logo-masks \\
        --checkpoint data/finetune/weights/sam2.1_hiera_small.pt \\
        --out data/finetune/weights/lora-mask-sam2.pt

Requires ``pip install -e '.[train]'`` (torch + sam2). The exported checkpoint is
small (~MBs) because only the LoRA A/B matrices are persisted; at runtime the
Sam2Segmenter re-applies them on top of the stock SAM 2 checkpoint.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from app.services.finetune.dataset import DatasetBuilder, DatasetManifest
from app.services.finetune.lora import (
    apply_lora_state_dict,
    apply_lora_to_model,
    lora_params,
    lora_state_dict,
    mask_bce_dice_loss,
)
from app.services.finetune.model_common import preprocess_for_sam2, sam2_available


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SAM 2 LoRA fine-tuning for Pixel2Layer")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="build pseudo-label dataset from raw images")
    prepare.add_argument("--raw", required=True, type=Path, help="dir of design-graphic images")
    prepare.add_argument("--dataset", required=True, type=Path, help="output dataset root")
    prepare.add_argument("--name", default="design-graphics", help="dataset name")
    prepare.add_argument("--min-region-area", type=float, default=400.0)
    prepare.add_argument("--max-side", type=int, default=1024)

    train = sub.add_parser("train", help="LoRA fine-tune SAM 2 and export LoRA weights")
    train.add_argument("--dataset", required=True, type=Path, help="dataset dir with manifest.json")
    train.add_argument("--checkpoint", required=True, type=Path, help="stock SAM 2 checkpoint")
    train.add_argument("--model-cfg", default="sam2.1_hiera_small")
    train.add_argument("--out", required=True, type=Path, help="where to save the LoRA checkpoint")
    train.add_argument("--rank", type=int, default=4)
    train.add_argument("--alpha", type=float, default=8.0)
    train.add_argument("--lr", type=float, default=1e-4)
    train.add_argument("--epochs", type=int, default=5)
    train.add_argument("--token", default="attn", help="LoRA targets module names containing this")
    train.add_argument("--device", default="", help="auto (cuda → cpu) when empty")
    train.add_argument(
        "--resume", type=Path, default=None, help="existing LoRA weights to resume from"
    )
    train.add_argument(
        "--save-every", type=int, default=0, help="checkpoint every N steps (0 = end only)"
    )
    train.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        return _cmd_prepare(args)
    if args.command == "train":
        return _cmd_train(args)
    return 1  # pragma: no cover


# -- prepare ------------------------------------------------------------------


def _cmd_prepare(args) -> int:
    raw = Path(args.raw)
    if not raw.is_dir() or not any(raw.iterdir()):
        print(f"error: raw images dir is missing or empty: {raw}", file=sys.stderr)
        return 1
    builder = DatasetBuilder(min_region_area=args.min_region_area, max_side=args.max_side)
    manifest = builder.build(raw, Path(args.dataset), name=args.name)
    instances = sum(len(s.instances) for s in manifest.samples)
    print(f"dataset '{manifest.name}' ready: {len(manifest.samples)} images, {instances} instances")
    print(f"manifest: {manifest.root / 'manifest.json'}")
    return 0


# -- train --------------------------------------------------------------------


def _cmd_train(args) -> int:
    if not sam2_available():
        print(
            "SAM 2 fine-tuning needs torch + sam2. Install with: "
            "cd apps/api && .venv/bin/pip install -e '.[train]'",
            file=sys.stderr,
        )
        return 2

    manifest_path = Path(args.dataset) / "manifest.json"
    if not manifest_path.exists():
        print(f"error: no manifest at {manifest_path} (run 'prepare' first)", file=sys.stderr)
        return 1
    manifest = DatasetManifest.load(manifest_path)
    if not manifest.samples:
        print("error: dataset is empty", file=sys.stderr)
        return 1

    random.seed(args.seed)
    np.random.seed(args.seed)
    import torch

    torch.manual_seed(args.seed)

    from sam2.build_sam import build_sam2

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = build_sam2(args.model_cfg, str(args.checkpoint), device=device)
    for param in model.parameters():
        param.requires_grad = False

    count = apply_lora_to_model(model, rank=args.rank, alpha=args.alpha, token=args.token)
    if count == 0:
        msg = f"error: no image-encoder attention layers matched token '{args.token}'"
        print(msg, file=sys.stderr)
        return 1
    if args.resume is not None:
        state = torch.load(args.resume, map_location=device, weights_only=False)
        apply_lora_state_dict(model, state["lora"])
        print(f"resumed LoRA from {args.resume}")

    params = lora_params(model)
    print(
        f"device={device} lora_layers={count} trainable_params={sum(p.numel() for p in params):,}"
    )
    optimizer = torch.optim.AdamW(params, lr=args.lr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    samples = manifest.samples
    steps_per_epoch = max(1, len(samples))
    total_steps = args.epochs * steps_per_epoch

    start = time.time()
    step = 0
    running_loss = 0.0
    for epoch in range(1, args.epochs + 1):
        random.shuffle(samples)
        for sample in samples:
            step += 1
            loss = _train_step(model, optimizer, sample, device)
            running_loss = (running_loss * 0.9) + float(loss or 0.0) * 0.1
            if step % 10 == 0 or step == total_steps:
                print(
                    f"step {step}/{total_steps} epoch {epoch}/{args.epochs} "
                    f"loss={running_loss:.4f} ({time.time() - start:.0f}s)"
                )
            if args.save_every and step % args.save_every == 0:
                _save(args, model, step)
    if not args.save_every:
        _save(args, model, step)

    print(f"done in {time.time() - start:.0f}s — saved {args.out}")
    return 0


def _train_step(model, optimizer, sample, device) -> float:
    """One LoRA optimizer step over a single annotated sample."""
    import torch
    from torch.nn import functional as F

    bgr = cv2.imread(str(sample.image))
    if bgr is None:
        return float("nan")
    mask = cv2.imread(str(sample.mask), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return float("nan")
    instance = random.choice(sample.instances)
    instance_mask = (mask == instance.id).astype(np.float32)

    tensor, transform = preprocess_for_sam2(bgr, long_side=1024)
    tensor = tensor.to(device)
    # Pad GT to the encoder input resolution (mirrors the image padding; the
    # loss head down-scales it to the mask-decoder resolution anyway).
    pad_h = transform.input_size[0] - instance_mask.shape[0]
    pad_w = transform.input_size[1] - instance_mask.shape[1]
    if pad_h > 0 or pad_w > 0:
        instance_mask = np.pad(
            instance_mask, ((0, pad_h), (0, pad_w)), mode="constant"
        )

    box = np.array([transform.apply_box(instance.box)], dtype=np.float32)
    boxes = torch.from_numpy(box).unsqueeze(0).to(device)  # [1, 1, 4]
    with torch.no_grad():
        dense, sparse = model.sam_prompt_encoder(boxes=boxes)
        del dense

    image_embed = _encoder_embeddings(model, tensor)
    pred_masks, _, _ = model.sam_mask_decoder(
        image_embeddings=image_embed,
        image_pe=model.sam_prompt_encoder.get_dense_pe(),
        sparse_prompt_embeddings=sparse,
        multimask_output=False,
    )
    gt = torch.from_numpy(instance_mask).unsqueeze(0).unsqueeze(0).to(device)
    gt_resized = F.interpolate(
        gt, size=(pred_masks.shape[-2], pred_masks.shape[-1]), mode="nearest"
    )
    loss = mask_bce_dice_loss(pred_masks, gt_resized)

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return float(loss.item())


def _encoder_embeddings(model, tensor):
    """Image-encoder forward → the downscaled feature fed to mask_decoder.

    Defensive across SAM 2 versions that return either a bare tensor (non-
    windowed encoders) or a ``(high_res_feats, downscaled)`` tuple/list.
    """
    out = model.image_encoder(tensor)
    if hasattr(out, "downscaled"):  # sam2.1 VisualEncoderOutput-style
        return out.downscaled
    if isinstance(out, (tuple, list)):
        return out[-1]
    return out


def _save(args, model, step: int) -> None:
    import torch

    meta = {
        "command": "train",
        "model_cfg": args.model_cfg,
        "rank": args.rank,
        "alpha": args.alpha,
        "token": args.token,
        "step": step,
        "lora_version": 1,
    }
    torch.save({"meta": meta, "lora": lora_state_dict(model)}, args.out)
    print(f"[checkpoint] step {step} → {args.out}")


if __name__ == "__main__":
    raise SystemExit(main())