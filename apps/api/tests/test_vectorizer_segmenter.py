from __future__ import annotations

import cv2
import numpy as np

from app.services.image_utils import load_image
from app.services.segmenter import VisionSegmenter
from app.services.vectorizer import Vectorizer
from tests.fixtures import make_poster, to_png_bytes


def test_vectorizer_produces_closed_path_for_logo_blob() -> None:
    # A star-ish / irregular filled blob that the shape detector can't classify
    img = make_poster(width=200, height=150, bg=(240, 240, 240))
    pts = np.array([[40, 40], [90, 30], [120, 70], [80, 110], [30, 90]], dtype=np.int32)
    cv2.fillPoly(img, [pts], (200, 60, 60))
    image = load_image(to_png_bytes(img))

    vectors = Vectorizer(min_area=60).detect(image)
    assert vectors, "expected at least one vectorized blob"
    vec = max(vectors, key=lambda v: v.width * v.height)
    assert vec.path.startswith("M ")
    assert vec.path.rstrip().endswith("Z")
    assert vec.width > 0 and vec.height > 0
    assert vec.fill and vec.fill.startswith("#")


def test_vectorizer_skips_near_rectangular_blobs() -> None:
    # Rectangles are geometric shapes, not vector paths.
    img = make_poster(
        width=200, height=150, bg=(240, 240, 240),
        shapes=[("rect", 20, 30, 100, 60, (30, 30, 200))],
    )
    image = load_image(to_png_bytes(img))
    vectors = Vectorizer(min_area=60).detect(image)
    assert vectors == []


def test_segmenter_splits_foreground_from_background() -> None:
    img = make_poster(width=200, height=150, bg=(245, 245, 245))
    cv2.circle(img, (60, 70), 25, (20, 20, 220), thickness=-1)
    cv2.rectangle(img, (130, 60), (170, 110), (30, 190, 90), thickness=-1)
    image = load_image(to_png_bytes(img))

    regions = VisionSegmenter(min_region_area=100).segment(image)
    assert len(regions) >= 2
    # each region carries an approximate label and valid mask
    for r in regions:
        assert 0.0 <= r.confidence <= 1.0
        assert r.width > 10 and r.height > 10
        assert r.mask.shape[0] == image.height
        assert r.mask.shape[1] == image.width


def test_segmenter_marks_solid_background_as_no_regions() -> None:
    img = make_poster(width=100, height=80, bg=(250, 250, 250))
    image = load_image(to_png_bytes(img))
    regions = VisionSegmenter(min_region_area=50).segment(image)
    assert regions == []