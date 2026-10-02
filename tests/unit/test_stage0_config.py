"""Unit tests for Stage 0 — config and paths."""

from __future__ import annotations

import pytest

from pipeline.config import DEFAULT_CONFIG, Config, load_config
from pipeline.paths import (
    PROJECT_ROOT, data_root, ensure_data_dirs, raw_dir, features_dir,
    models_dir, predictions_dir, quality_dir,
)


@pytest.mark.unit
def test_default_config_train_every_n_events():
    assert DEFAULT_CONFIG.train_every_n_events == 2000
    assert DEFAULT_CONFIG.batch_size == 50


@pytest.mark.unit
def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("TRAIN_EVERY_N_EVENTS", "10")
    monkeypatch.setenv("BATCH_SIZE", "5")
    cfg = load_config()
    assert cfg.train_every_n_events == 10
    assert cfg.batch_size == 5


@pytest.mark.unit
def test_required_data_dir_helpers(tmp_path):
    ensure_data_dirs(tmp_path)
    assert raw_dir(tmp_path).exists()
    assert raw_dir(tmp_path).name == "raw"


@pytest.mark.unit
@pytest.mark.parametrize("override", [None, ""])
def test_default_data_root(monkeypatch, override):
    if override is None:
        monkeypatch.delenv("DATA_ROOT", raising=False)
    else:
        monkeypatch.setenv("DATA_ROOT", override)
    assert data_root() == PROJECT_ROOT / "data"


@pytest.mark.unit
def test_custom_data_root_resolved_at_call_time(monkeypatch, tmp_path):
    for root in (tmp_path / "first", tmp_path / "second"):
        monkeypatch.setenv("DATA_ROOT", str(root))
        assert data_root() == root
        for helper, name in (
            (raw_dir, "raw"), (features_dir, "features"), (models_dir, "models"),
            (predictions_dir, "predictions"), (quality_dir, "quality"),
        ):
            assert helper() == root / name


@pytest.mark.unit
def test_relative_data_root_rejected(monkeypatch):
    monkeypatch.setenv("DATA_ROOT", "relative/data")
    with pytest.raises(ValueError, match="DATA_ROOT must be an absolute path"):
        data_root()


@pytest.mark.unit
@pytest.mark.parametrize("override", ["/another/root", "invalid-relative-root"])
def test_explicit_base_takes_precedence(monkeypatch, tmp_path, override):
    monkeypatch.setenv("DATA_ROOT", override)
    assert data_root(tmp_path) == tmp_path / "data"
