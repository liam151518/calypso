"""Tests for app/models.py. The fal.ai model registry + cost estimator."""

from __future__ import annotations

from app import models


def test_top_models_have_at_least_ten_entries():
    assert len(models.TOP_MODELS) >= 10, "Spec said 'top 10'. Registry should not shrink."


def test_top_models_have_unique_ids():
    ids = [m.id for m in models.TOP_MODELS]
    assert len(set(ids)) == len(ids)


def test_top_models_have_video_and_image_categories():
    cats = {m.category for m in models.TOP_MODELS}
    assert "video" in cats
    assert "image" in cats


def test_video_models_have_per_second_table():
    for m in models.TOP_MODELS:
        if m.category != "video":
            continue
        assert m.per_second_usd, f"video model {m.id} missing cost table"
        for res, rate in m.per_second_usd.items():
            assert rate > 0, f"{m.id}@{res} rate must be > 0"


def test_image_models_have_per_image_cost():
    for m in models.TOP_MODELS:
        if m.category != "image":
            continue
        assert m.per_image_usd > 0, f"image model {m.id} missing cost"


def test_list_models_returns_serialisable_dicts():
    out = models.list_models(api_key=None)
    assert isinstance(out, list)
    assert out
    sample = out[0]
    assert isinstance(sample, dict)
    assert {"id", "name", "category", "vendor"} <= set(sample.keys())


def test_estimate_cost_video_scales_with_duration():
    short = models.estimate_cost("minimax/h3", duration=4, resolution="768p")
    long_ = models.estimate_cost("minimax/h3", duration=12, resolution="768p")
    assert short["category"] == "video"
    assert long_["usd"] > short["usd"]
    assert long_["usd"] == round(short["usd"] * 3, 4)


def test_estimate_cost_video_scales_with_resolution():
    cheap = models.estimate_cost("minimax/h3", duration=8, resolution="480p")
    pricey = models.estimate_cost("minimax/h3", duration=8, resolution="1080p")
    assert pricey["usd"] > cheap["usd"]


def test_estimate_cost_image_scales_with_num_images():
    one = models.estimate_cost("flux-pro/v1.1", num_images=1)
    four = models.estimate_cost("flux-pro/v1.1", num_images=4)
    assert one["category"] == "image"
    assert four["usd"] == round(one["usd"] * 4, 4)


def test_estimate_cost_unknown_model_returns_default():
    est = models.estimate_cost("nope/invalid", duration=8, resolution="768p")
    assert est["usd"] >= 0
    assert est.get("note") == "unknown model"


def test_estimate_cost_falls_back_to_first_valid_resolution():
    est = models.estimate_cost("minimax/h3", duration=8, resolution="4k")
    # Falls back to 480p (the first defined resolution).
    assert est["resolution"] in models.get_model("minimax/h3").resolutions  # type: ignore[union-attr]


def test_default_video_and_image_ids_resolve():
    vid = models.default_video_model_id()
    img = models.default_image_model_id()
    assert models.get_model(vid) is not None
    assert models.get_model(img) is not None


def test_get_model_by_id():
    m = models.get_model("minimax/h3")
    assert m is not None
    assert m.category == "video"
