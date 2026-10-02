"""Integration tests for Stage 5 — helpers read real-shaped data dirs."""

from __future__ import annotations

import shutil

import pandas as pd
import pytest

from pipeline.dashboard.ml_metrics import sample_volume, score_summary
from pipeline.paths import ensure_data_dirs, features_dir, predictions_dir
from tests.conftest import FIXTURES


@pytest.mark.integration
def test_ml_helpers_read_data_tree(tmp_path):
    fdir = features_dir(tmp_path)
    pdir = predictions_dir(tmp_path)
    fdir.mkdir(parents=True)
    pdir.mkdir(parents=True)
    shutil.copy(FIXTURES / "features_golden.csv", fdir / "features_a.csv")
    shutil.copy(FIXTURES / "predictions_sample.csv", pdir / "predictions_a.csv")

    features = pd.concat([pd.read_csv(p) for p in fdir.glob("features_*.csv")])
    preds = pd.concat([pd.read_csv(p) for p in pdir.glob("predictions_*.csv")])
    assert sample_volume(features) == 5
    assert score_summary(preds)["count"] == 3


@pytest.mark.integration
def test_dashboard_loaders_use_environment_storage(monkeypatch, tmp_path):
    from pipeline.dashboard.app import (
        load_features, load_predictions, load_quality_log,
    )
    from pipeline.preprocess import QUALITY_LOG

    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "storage"))
    paths = ensure_data_dirs()
    shutil.copy(FIXTURES / "features_golden.csv", paths["features"] / "features_a.csv")
    shutil.copy(FIXTURES / "predictions_sample.csv", paths["predictions"] / "predictions_a.csv")
    quality = pd.DataFrame({"total_rows": [5], "dropped_rows": [1]})
    quality.to_csv(paths["quality"] / QUALITY_LOG, index=False)

    assert sample_volume(load_features()) == 5
    assert score_summary(load_predictions())["count"] == 3
    pd.testing.assert_frame_equal(load_quality_log(), quality)
    # Explicit-base loaders remain independent of the environment override.
    assert load_features(tmp_path).empty
    assert load_predictions(tmp_path).empty
    assert load_quality_log(tmp_path).empty
