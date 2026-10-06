from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

from app.services.finetune.dataset import DatasetBuilder, DatasetManifest
from app.services.finetune.train import _cmd_prepare
from tests.fixtures import make_poster, to_png_bytes


def _write_raw(tmp: Path) -> list[Path]:
    raw = tmp / "raw"
    raw.mkdir()
    poster = make_poster(
        width=240,
        height=180,
        bg=(245, 245, 245),
        shapes=[
            ("circle", 60, 90, 30, (200, 40, 40)),
            ("rect", 130, 50, 80, 60, (40, 90, 200)),
        ],
    )
    blank = np.full((120, 160, 3), (250, 250, 250), dtype=np.uint8)
    (raw / "poster.png").write_bytes(to_png_bytes(poster))
    (raw / "blank.png").write_bytes(to_png_bytes(blank))
    return [raw / "poster.png", raw / "blank.png"]


def test_builder_produces_instances_and_skips_blank() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _write_raw(tmp)
        builder = DatasetBuilder(min_region_area=100)

        manifest = builder.build(tmp / "raw", tmp / "out", name="logo-masks")

        assert manifest.name == "logo-masks"
        # blank image is skipped, poster is kept
        assert len(manifest.samples) == 1
        sample = manifest.samples[0]
        assert len(sample.instances) >= 2

        assert sample.image.exists()
        assert sample.mask.exists()
        mask = cv2.imread(str(sample.mask), cv2.IMREAD_GRAYSCALE)
        # instance labels are valid ids; per-instance pixels nonempty
        for inst in sample.instances:
            assert inst.id >= 1
            assert (mask == inst.id).sum() == inst.area
            x, y, w, h = inst.box
            assert w > 0 and h > 0
            assert inst.centroid[0] >= x and inst.centroid[1] >= y

        # image is persisted RGB and has the right shape
        img = cv2.imread(str(sample.image))
        assert img.shape[:2] == (sample.height, sample.width)


def test_builder_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _write_raw(tmp)
        builder = DatasetBuilder(min_region_area=100)
        m1 = builder.build(tmp / "raw", tmp / "out", name="d1")
        m2 = builder.build(tmp / "raw", tmp / "out2", name="d2")
        s1, s2 = m1.samples[0], m2.samples[0]
        assert len(m1.samples) == len(m2.samples)
        # uuids differ, geometry is identical
        assert s1.id != s2.id
        assert [i.box for i in s1.instances] == [i.box for i in s2.instances]
        assert [i.area for i in s1.instances] == [i.area for i in s2.instances]
        assert (s1.mask.read_bytes() == s2.mask.read_bytes())
        assert (s1.image.read_bytes() == s2.image.read_bytes())


def test_manifest_round_trips(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _write_raw(tmp)
        builder = DatasetBuilder(min_region_area=100)
        manifest = builder.build(tmp / "raw", tmp / "out", name="roundtrip")
        path = manifest.save(tmp / "manifest.json")

        loaded = DatasetManifest.load(path)
        assert loaded.name == manifest.name
        assert len(loaded.samples) == len(manifest.samples)
        assert loaded.samples[0].instances[0].box == manifest.samples[0].instances[0].box
        assert loaded.samples[0].image.exists()


def test_prepare_cli_builds_dataset(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    img = make_poster(
        width=200,
        height=150,
        bg=(240, 240, 240),
        shapes=[("circle", 60, 75, 25, (10, 10, 200))],
    )
    (raw / "logo.png").write_bytes(to_png_bytes(img))

    from argparse import Namespace

    out = tmp_path / "datasets"
    args = Namespace(
        raw=raw,
        dataset=out,
        name="cli-masks",
        min_region_area=100,
        max_side=1024,
    )
    assert _cmd_prepare(args) == 0
    manifest_path = out / "cli-masks" / "manifest.json"
    assert manifest_path.exists()
    assert len(DatasetManifest.load(manifest_path).samples) == 1