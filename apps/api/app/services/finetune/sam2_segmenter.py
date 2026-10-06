"""Fine-tuned SAM 2 segmentation backend.

Wraps the ``sam2`` package: loads the stock SAM 2 checkpoint, re-applies the
LoRA weights produced by ``app.services.finetune.train``, then runs promptable
segmentation using foreground seeds extracted from the image itself. Outputs
the same ``SegmentedRegion`` contract as the OpenCV ``VisionSegmenter``.

The model is loaded lazily and cached per unique (checkpoint, lora, cfg, device)
tuple. When torch/sam2 or the weights are unavailable, ``available()`` returns
False and the pipeline factory falls back to ``VisionSegmenter``, so the rest of
the app keeps working without the heavy dependencies installed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from app.services.finetune.lora import apply_lora_state_dict, apply_lora_to_model
from app.services.finetune.model_common import (
    build_sam2_model,
    sam2_available,
)
from app.services.image_utils import LoadedImage
from app.services.segmenter import SegmentedRegion, SegmenterBackend

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict = {}


class Sam2Segmenter(SegmenterBackend):
    """SAM 2 + LoRA segmentation engine (requires the ``[train]`` extras)."""

    def __init__(
        self,
        *,
        checkpoint: Path,
        model_cfg: str,
        lora_weights: Path,
        device: str = "",
        min_region_area: float = 200.0,
        max_regions: int = 40,
    ) -> None:
        self.checkpoint = Path(checkpoint)
        self.model_cfg = model_cfg
        self.lora_weights = Path(lora_weights)
        self.device = device
        self.min_region_area = min_region_area
        self.max_regions = max_regions

    def available(self) -> bool:
        return (
            sam2_available()
            and self.checkpoint.exists()
            and self.lora_weights.exists()
        )

    def segment(self, image: LoadedImage) -> list[SegmentedRegion]:
        if not self.available():
            raise RuntimeError(
                "Sam2Segmenter is not available: install the [train] extras and point "
                "SAM2_CHECKPOINT / SAM2_LORA_WEIGHTS at existing files"
            )
        predictor = self._get_predictor()
        predictor.set_image(image.rgb)

        regions: list[SegmentedRegion] = []
        for seed in self._foreground_seeds(image):
            try:
                masks, ious, _ = predictor.predict(
                    point_coords=seed["points"],
                    point_labels=seed["labels"],
                    multimask_output=True,
                )
            except Exception as exc:  # noqa: BLE001 — a bad prompt must not kill the job
                logger.warning("SAM 2 predict failed for one seed: %s", exc)
                continue

            best = self._best_mask_and_conf(masks, ious, image) or []
            if not best:
                continue
            mask, confidence = best
            x, y, w, h = _mask_box(mask)
            if w < 10 or h < 10 or mask.sum() < self.min_region_area:
                continue
            regions.append(
                SegmentedRegion(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    mask=_packed_mask(mask, x, y, w, h, image.height, image.width),
                    label="foreground",
                    confidence=max(0.0, min(1.0, confidence)),
                )
            )
            if len(regions) >= self.max_regions:
                break
        return regions

    # -- internals ------------------------------------------------------------

    def _get_predictor(self):
        key = (str(self.checkpoint), self.lora_weights, self.model_cfg, self.device)
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        return self._load_predictor(key)

    def _load_predictor(self, key):
        model = build_sam2_model(self.model_cfg, self.checkpoint, self.device or None)
        count = apply_lora_to_model(model, rank=4, alpha=8.0, token="attn")
        if count == 0:
            raise RuntimeError("no attention layers found to attach LoRA")
        state = _load_lora_checkpoint(self.lora_weights)
        apply_lora_state_dict(model, state["lora"])
        logger.info("loaded fine-tuned SAM 2 (%s, %d LoRA layers)", self.model_cfg, count)

        from sam2.sam2_image_predictor import Sam2ImagePredictor

        predictor = Sam2ImagePredictor(model)
        _MODEL_CACHE[key] = predictor
        return predictor

    def _foreground_seeds(self, image: LoadedImage) -> list[dict]:
        """Coarse foreground blobs → prompt points for SAM 2."""
        from app.services.segmenter import VisionSegmenter

        fg = VisionSegmenter().segment(image)
        if not fg:
            return []
        combined = max(fg, key=lambda r: r.mask.sum()).mask  # largest blob carries the prompt
        combined = combined.astype(np.uint8)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(combined, connectivity=8)

        seeds = []
        for idx in range(1, num):
            x, y, w, h, area = stats[idx]
            if area < self.min_region_area or w < 8 or h < 8:
                continue
            pts = _sample_points(labels == idx, image.width, image.height)
            if not pts:
                continue
            points = np.array(pts, dtype=np.float32).reshape(-1, 2)
            labels_arr = np.ones(len(points), dtype=np.int32)
            seeds.append({"points": points, "labels": labels_arr})
        return seeds

    @staticmethod
    def _best_mask_and_conf(masks, ious, image):
        m = np.asarray(masks)
        i = np.asarray(ious)
        if m.size == 0:
            return None
        # Collapse any leading dims (preds × prompts) into one and pick the
        # candidate with the highest predicted IoU.
        m_flat = m.reshape(-1, *m.shape[-2:])
        i_flat = i.reshape(-1)
        best_idx = int(np.argmax(i_flat)) if i_flat.size else 0
        binary = (m_flat[best_idx] > 0).astype(np.uint8) * 255
        binary = binary.squeeze()
        H, W = image.height, image.width
        if binary.shape != (H, W):
            binary = cv2.resize(binary, (W, H), interpolation=cv2.INTER_NEAREST)
        confidence = float(np.max(i_flat)) if i_flat.size else 0.7
        return binary, confidence


def _load_lora_checkpoint(path: Path) -> dict:
    import torch

    return torch.load(path, map_location="cpu", weights_only=False)


def _sample_points(mask: np.ndarray, width: int, height: int, n: int = 6) -> list:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    indices = np.linspace(0, len(xs) - 1, min(n, len(xs))).astype(int)
    return [(int(xs[i]), int(ys[i])) for i in indices]


def _mask_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return 0, 0, 0, 0
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def _packed_mask(mask: np.ndarray, x: int, y: int, w: int, h: int, H: int, W: int) -> np.ndarray:
    """Full-size (H, W) uint8 mask consistent with VisionSegmenter output."""
    full = np.zeros((H, W), dtype=np.uint8)
    full[y : y + h, x : x + w] = mask[y : y + h, x : x + w]
    return full