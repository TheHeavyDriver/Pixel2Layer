"""Shared SAM 2 model loading + preprocessing (lazy torch/sam2 imports).

Everything here is import-safe without torch installed; functions raise a
descriptive error only when actually called without the ``[train]`` extras.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

import cv2
import numpy as np


def sam2_available() -> bool:
    """True when torch and the sam2 package are both installed."""
    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("sam2") is not None
    )


def require_torch_and_sam2() -> None:
    if not sam2_available():
        raise RuntimeError(
            "SAM 2 requires torch and the sam2 package. Install with: "
            "cd apps/api && .venv/bin/pip install -e '.[train]'"
        )


def build_sam2_model(model_cfg: str, checkpoint, device: str | None = None):
    """Build a SAM 2 model from ``sam2`` (checkpoint → image encoder + decoder)."""
    require_torch_and_sam2()
    import torch
    from sam2.build_sam import build_sam2

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(model_cfg, str(checkpoint), device=device)
    model.eval()
    return model


@dataclass
class Sam2Transform:
    """Maps image-space coordinates into the padded, resized SAM 2 input space."""

    scale: float
    pad_left: int
    pad_top: int
    input_size: tuple[int, int]  # (H, W) of the tensor fed to SAM 2

    def apply_points(self, points: np.ndarray) -> np.ndarray:
        pts = points.astype(np.float32) * self.scale
        pts[:, 0] += self.pad_left
        pts[:, 1] += self.pad_top
        return pts

    def apply_box(self, box: list[int]) -> list[int]:
        """[x, y, w, h] → [x0, y0, x1, y1] in SAM 2 input space."""
        x, y, w, h = box
        return [
            int(round(x * self.scale + self.pad_left)),
            int(round(y * self.scale + self.pad_top)),
            int(round((x + w) * self.scale + self.pad_left)),
            int(round((y + h) * self.scale + self.pad_top)),
        ]


def preprocess_for_sam2(bgr: np.ndarray, *, long_side: int = 1024, window: int = 32) -> tuple:
    """Resize + pad a BGR image for the SAM 2 image encoder.

    Returns ``(tensor, Sam2Transform)`` where tensor is ``[1, 3, H, W]`` float
    in ``[0, 255]`` (SAM 2 is trained without ImageNet normalization).
    """
    require_torch_and_sam2()
    import torch

    to_rgb = bgr[:, :, ::-1].copy()
    h, w = to_rgb.shape[:2]
    scale = min(1.0, long_side / max(h, w))
    if scale < 1.0:
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
        rgb = np.asarray(cv2.resize(to_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA))
    else:
        scale, new_h, new_w = 1.0, h, w
        rgb = to_rgb
    pad_w = (-new_w) % window
    pad_h = (-new_h) % window
    padded = np.pad(rgb, ((0, pad_h), (0, pad_w), (0, 0)), mode="constant")
    tensor = torch.from_numpy(padded).permute(2, 0, 1).contiguous().float().unsqueeze(0)
    transform = Sam2Transform(
        scale=scale,
        pad_left=0,
        pad_top=0,
        input_size=(new_h + pad_h, new_w + pad_w),
    )
    return tensor, transform