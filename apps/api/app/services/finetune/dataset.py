"""Pseudo-label dataset builder for SAM 2 fine-tuning.

Design-graphic images (logos, posters, illustrations) rarely ship with
ground-truth segmentation masks. This module synthesizes training labels from
the reconstruction pipeline itself: background-color separation + connected
component analysis produce per-instance foreground masks, which are the
supervision used to LoRA-fine-tune SAM 2 on design-graphic content.

Pure cv2/numpy dependency only — the training CLI and the rest of the pipeline
can run without torch installed.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.services.image_utils import LoadedImage, load_image
from app.services.segmenter import VisionSegmenter

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Instance:
    id: int
    box: list[int]  # [x, y, w, h] in dataset image space
    centroid: list[int]  # [cx, cy]
    area: int


@dataclass
class Sample:
    """One training example: resized image + per-instance mask + box prompts."""

    id: str
    image: Path  # absolute path to dataset image
    mask: Path  # absolute path to PNG mask (0 = background, k = instance k)
    width: int
    height: int
    instances: list[Instance] = field(default_factory=list)


@dataclass
class DatasetManifest:
    """Serializable dataset summary consumed by the training CLI."""

    name: str
    root: Path
    samples: list[Sample] = field(default_factory=list)

    def save(self, path: Path) -> Path:
        path.write_text(
            json.dumps(
                {
                    "name": self.name,
                    "root": str(self.root),
                    "samples": [
                        {
                            "id": s.id,
                            "image": str(s.image.relative_to(self.root)),
                            "mask": str(s.mask.relative_to(self.root)),
                            "width": s.width,
                            "height": s.height,
                            "instances": [
                                {
                                    "id": i.id,
                                    "box": i.box,
                                    "centroid": i.centroid,
                                    "area": i.area,
                                }
                                for i in s.instances
                            ],
                        }
                        for s in self.samples
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: Path) -> DatasetManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        root = Path(data["root"])
        samples = []
        for s in data["samples"]:
            samples.append(
                Sample(
                    id=s["id"],
                    image=root / s["image"],
                    mask=root / s["mask"],
                    width=s["width"],
                    height=s["height"],
                    instances=[
                        Instance(
                            id=i["id"],
                            box=i["box"],
                            centroid=i["centroid"],
                            area=i["area"],
                        )
                        for i in s["instances"]
                    ],
                )
            )
        return cls(name=data["name"], root=root, samples=samples)


class DatasetBuilder:
    """Turn design-graphic images into a SAM 2 LoRA training dataset.

    For each input image:
      1. Resize so the longest side is at most ``max_side`` (keeps masks cheap).
      2. Separate the border-colored background from the foreground.
      3. Split disjoint foreground blobs into per-instance regions.
      4. Persist ``images/<id>.png``, ``masks/<id>.png`` (instance labels) and
         box/centroid prompts in ``manifest.json``.

    Images with no detectable foreground are skipped (they carry no signal).
    The result is deterministic for a given input directory.
    """

    def __init__(
        self,
        *,
        min_region_area: float = 400.0,
        max_regions: int = 24,
        bg_tolerance: int = 28,
        max_side: int = 1024,
    ) -> None:
        self.min_region_area = min_region_area
        self.max_regions = max_regions
        self.bg_tolerance = bg_tolerance
        self.max_side = max_side
        self._ow = VisionSegmenter(
            min_region_area=min_region_area,
            max_regions=max_regions,
            bg_tolerance=bg_tolerance,
        )

    def build(self, raw_dir: Path, out_dir: Path, name: str) -> DatasetManifest:
        """Build (or rebuild) a dataset under ``out_dir/<name>``.

        Returns the parsed manifest for immediate use by the training CLI.
        """
        raw_dir = Path(raw_dir).resolve()
        out_dir = Path(out_dir).resolve() / name
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "images").mkdir(exist_ok=True)
        (out_dir / "masks").mkdir(exist_ok=True)

        sources = sorted(
            p for p in raw_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS
        )
        samples: list[Sample] = []
        for source in sources:
            try:
                sample = self._process(source, out_dir)
            except ValueError:
                continue
            if sample is not None:
                samples.append(sample)

        manifest = DatasetManifest(name=name, root=out_dir, samples=samples)
        manifest.save(out_dir / "manifest.json")
        return manifest

    # -- internals ----------------------------------------------------------

    def _process(self, source: Path, out_dir: Path) -> Sample | None:
        image = load_image(source.read_bytes())
        bgr, height, width = self._resize(image.bgr, self.max_side)

        regions = self._ow.segment(
            LoadedImage(
                bgr=bgr,
                rgba=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA),
                width=width,
                height=height,
            )
        )
        if not regions:
            return None

        sample_id = f"{source.stem}-{uuid.uuid4().hex[:6]}"
        img_path = out_dir / "images" / f"{sample_id}.png"
        mask_path = out_dir / "masks" / f"{sample_id}.png"

        instance_mask = np.zeros((height, width), dtype=np.uint8)
        instances: list[Instance] = []
        for idx, region in enumerate(regions, start=1):
            if idx > self.max_regions:
                break
            part = region.mask[
                region.y : region.y + region.height, region.x : region.x + region.width
            ]
            if np.count_nonzero(part) < self.min_region_area:
                continue
            view = instance_mask[
                region.y : region.y + region.height, region.x : region.x + region.width
            ]
            view[part > 0] = idx
            instances.append(
                Instance(
                    id=idx,
                    box=[region.x, region.y, region.width, region.height],
                    centroid=[region.x + region.width // 2, region.y + region.height // 2],
                    area=int(np.count_nonzero(part)),
                )
            )

        if not instances:
            return None

        cv2.imwrite(str(mask_path), instance_mask)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        cv2.imwrite(str(img_path), rgb)
        return Sample(
            id=sample_id,
            image=img_path,
            mask=mask_path,
            width=width,
            height=height,
            instances=instances,
        )

    @staticmethod
    def _resize(bgr: np.ndarray, max_side: int) -> tuple[np.ndarray, int, int]:
        height, width = bgr.shape[:2]
        longest = max(height, width)
        if longest <= max_side:
            return bgr, height, width
        scale = max_side / longest
        new_w, new_h = int(round(width * scale)), int(round(height * scale))
        resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized, new_h, new_w