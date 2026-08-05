from __future__ import annotations

import pytest

from scripts.embedding_benchmark import _percentile, _validate_vectors


def test_percentile_interpolates_sorted_samples() -> None:
    assert _percentile([40.0, 10.0, 30.0, 20.0], 0.5) == pytest.approx(25.0)
    assert _percentile([12.0], 0.95) == 12.0


def test_validate_vectors_reports_dimension_and_norm_error() -> None:
    dimension, error = _validate_vectors([[1.0, 0.0], [0.0, 1.0]], 2)

    assert dimension == 2
    assert error == pytest.approx(0.0)


def test_validate_vectors_rejects_bad_count_and_shape() -> None:
    with pytest.raises(RuntimeError, match="1 vectors for 2 inputs"):
        _validate_vectors([[1.0, 0.0]], 2)
    with pytest.raises(RuntimeError, match="inconsistent dimensions"):
        _validate_vectors([[1.0, 0.0], [1.0]], 2)
