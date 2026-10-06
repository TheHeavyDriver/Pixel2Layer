"""LoRA (Low-Rank Adaptation) building blocks for SAM 2 fine-tuning.

Imports only torch lazily: this module can be imported by the full app without
torch installed. Fine-tuning (`train.py`) and the Sam2Segmenter require torch +
the ``sam2`` package (install with the ``[train]`` extra).

Follows the official SAM 2 LoRA recipe: rank-``r`` adapters on the attention
projections of the image encoder, base weights frozen, adapters the only
trainable parameters.
"""

from __future__ import annotations

import importlib.util

HAS_TORCH = importlib.util.find_spec("torch") is not None

if HAS_TORCH:
    import torch
    from torch import nn
    from torch.nn import functional as F

    class _LoRALinear(nn.Module):
        """nn.Linear wrapper adding ``output += (x @ A @ B) * (alpha / rank)``.

        The original weight/bias are copied in and frozen; only the low-rank
        A/B matrices receive gradients.
        """

        def __init__(
            self,
            in_features: int,
            out_features: int,
            *,
            rank: int,
            alpha: float,
            original=None,
        ) -> None:
            super().__init__()
            self.rank = max(1, int(rank))
            self.scaling = float(alpha) / self.rank

            self.base = nn.Linear(in_features, out_features)
            with torch.no_grad():
                if original is not None:
                    self.base.weight.copy_(original.weight)
                    if original.bias is not None:
                        self.base.bias.copy_(original.bias)
            self.base.requires_grad_(False)

            self.lora_a = nn.Parameter(torch.randn(in_features, self.rank) * 0.02)
            self.lora_b = nn.Parameter(torch.zeros(self.rank, out_features))

        def forward(self, x):
            out = self.base(x)
            return out + (x @ self.lora_a @ self.lora_b) * self.scaling

else:  # pragma: no cover — imported on machines without torch
    _LoRALinear = None  # type: ignore[assignment, misc]


def _require_torch():
    if not HAS_TORCH or "torch" not in globals():
        raise RuntimeError(
            "SAM 2 fine-tuning/LoRA requires torch. Install with: "
            "cd apps/api && .venv/bin/pip install -e '.[train]'"
        )


def apply_lora_to_model(model, *, rank: int = 4, alpha: float = 8.0, token: str = "attn") -> int:
    """Wrap ``nn.Linear`` attention modules of ``model`` with LoRA adapters.

    Replaces, in place, every ``nn.Linear`` whose module name contains
    ``token`` (default ``"attn"`` — SAM 2's image-encoder attention blocks).
    Returns the number of adapted layers.
    """
    _require_torch()
    if isinstance(model, dict):
        raise TypeError("apply_lora_to_model expects a torch nn.Module, not a dict")

    count = 0
    for name, module in list(model.named_modules()):
        if token.lower() not in name.lower():
            continue
        if not isinstance(module, nn.Linear) or isinstance(module, _LoRALinear):
            continue
        in_f, out_f = module.in_features, module.out_features
        replaced = _LoRALinear(
            in_f,
            out_f,
            rank=rank,
            alpha=alpha,
            original=module,
        )
        _setattr_with_dots(model, name, replaced)
        count += 1
    return count


def _setattr_with_dots(root, dotted: str, value) -> None:
    parts = dotted.split(".")
    obj = root
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def lora_params(model) -> list:
    """All LoRA adapter parameters (the only trainable params after wrapping)."""
    _require_torch()
    return [p for name, p in model.named_parameters() if "lora_a" in name or "lora_b" in name]


def lora_state_dict(model) -> dict[str, torch.Tensor]:
    return {name: p.detach().clone() for name, p in model.named_parameters() if "lora_" in name}


def apply_lora_state_dict(model, state: dict[str, torch.Tensor]) -> None:
    """Load saved LoRA A/B tensors back onto ``model`` (after apply_lora)."""
    _require_torch()
    current = dict(model.named_parameters())
    loaded = 0
    for name, tensor in state.items():
        # Tolerate prefixes saved under "model." / "module." etc.
        key = name
        for prefix in ("model.", "module.", ""):
            if key in current:
                break
            key = name[len(prefix) :] if name.startswith(prefix) and prefix else name
        if key in current and ("lora_a" in key or "lora_b" in key):
            with torch.no_grad():
                current[key].copy_(tensor)
            loaded += 1
    if not loaded:
        raise RuntimeError("no matching LoRA parameters found in the saved state dict")


def mask_bce_dice_loss(pred_logits, target_masks) -> torch.Tensor:
    """BCE + Dice mask loss used during fine-tuning."""
    _require_torch()
    pred_logits = pred_logits.float().flatten(1, -1)
    target_masks = target_masks.float().flatten(1, -1)

    bce = F.binary_cross_entropy_with_logits(pred_logits, target_masks, reduction="mean")

    probs = torch.sigmoid(pred_logits)
    smooth = 1.0
    inter = (probs * target_masks).sum(dim=1)
    union = probs.sum(dim=1) + target_masks.sum(dim=1) + smooth
    dice = 1.0 - (2.0 * inter + smooth) / union
    return 0.5 * bce + dice.mean()