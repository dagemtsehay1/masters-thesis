import json

from src.monitoring.experiment_log import ExperimentLog, Trial
from src.monitoring.metrics import MetricsCollector


def test_metrics_latency_and_counters():
    metrics = MetricsCollector(history_size=5)
    metrics.record_latency("gesture", 10.0)
    metrics.record_latency("gesture", 20.0)
    assert metrics.latest_latency("gesture") == 20.0
    assert metrics.mean_latency("gesture") == 15.0

    metrics.increment("commands_executed")
    metrics.increment("commands_executed", 2)
    assert metrics.counter("commands_executed") == 3


def test_metrics_history_is_bounded():
    metrics = MetricsCollector(history_size=3)
    for i in range(10):
        metrics.record_latency("whisper", float(i))
    # Only the last 3 are retained - never unbounded growth.
    assert metrics.mean_latency("whisper") == (7 + 8 + 9) / 3


def test_metrics_uptime_is_nonnegative():
    metrics = MetricsCollector()
    assert metrics.uptime_s() >= 0.0


def test_experiment_log_accuracy_and_export(tmp_path):
    log = ExperimentLog(experiment_name="pilot", session_id="p01")
    log.add_trial(Trial("stop", "stop", True, "voice", "en", 0.9, 100.0))
    log.add_trial(Trial("go", "left", False, "gesture", "en", 0.7, 120.0))
    assert log.accuracy() == 0.5

    csv_path = tmp_path / "out.csv"
    json_path = tmp_path / "out.json"
    log.export_csv(str(csv_path))
    log.export_json(str(json_path))

    assert csv_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["experiment_name"] == "pilot"
    assert payload["accuracy"] == 0.5
    assert len(payload["trials"]) == 2


def test_experiment_log_empty_accuracy_is_none():
    assert ExperimentLog().accuracy() is None
