from scripts.vllm_benchmark import RequestMetrics, _percentile, _summarize


def test_nearest_rank_percentile():
    assert _percentile([40.0, 10.0, 30.0, 20.0], 0.50) == 20.0
    assert _percentile([40.0, 10.0, 30.0, 20.0], 0.95) == 40.0


def test_serving_summary_keeps_per_request_and_aggregate_metrics_separate():
    metrics = [
        RequestMetrics(100.0, 1000.0, 20, 22.0),
        RequestMetrics(200.0, 1200.0, 20, 18.0),
    ]

    result = _summarize(metrics, wall_seconds=2.0, concurrency=2)

    assert result["ttft_ms"] == {"p50": 150.0, "p95": 200.0}
    assert result["latency_ms"] == {"p50": 1100.0, "p95": 1200.0}
    assert result["mean_decode_tokens_per_second_per_request"] == 20.0
    assert result["aggregate_output_tokens_per_second"] == 20.0
    assert result["requests_per_second"] == 1.0
