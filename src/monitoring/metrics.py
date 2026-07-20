"""Bounded in-memory metrics collection.

Every series is a bounded deque so a long session can never grow metrics
memory without limit. Latencies are recorded per named stage; counters are
monotonic tallies. CPU/memory sampling uses psutil when available and
degrades to "unavailable" (never raises) when it isn't.
"""
import time
from collections import defaultdict, deque
from typing import Dict, Optional

try:
    import psutil

    _PROCESS = psutil.Process()
except Exception:  # psutil optional - dashboard just shows n/a without it
    psutil = None
    _PROCESS = None


class MetricsCollector:
    def __init__(self, history_size: int = 120):
        self._history_size = history_size
        self._latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self._start_time = time.monotonic()

    def record_latency(self, stage: str, latency_ms: float) -> None:
        self._latencies[stage].append(latency_ms)

    def increment(self, counter: str, amount: int = 1) -> None:
        self._counters[counter] += amount

    def record_gauge(self, name: str, value: float) -> None:
        self._gauges[name].append(value)

    def latest_latency(self, stage: str) -> Optional[float]:
        series = self._latencies.get(stage)
        return series[-1] if series else None

    def mean_latency(self, stage: str) -> Optional[float]:
        series = self._latencies.get(stage)
        return sum(series) / len(series) if series else None

    def counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def gauge_series(self, name: str):
        return list(self._gauges.get(name, []))

    def uptime_s(self) -> float:
        return time.monotonic() - self._start_time

    def sample_system(self) -> Dict[str, Optional[float]]:
        """Samples CPU% and RSS memory (MB), recording each as a gauge.
        Returns {'cpu_percent': .., 'memory_mb': ..} with None values when
        psutil isn't available."""
        cpu = memory_mb = None
        if _PROCESS is not None:
            try:
                cpu = _PROCESS.cpu_percent(interval=None)
                memory_mb = _PROCESS.memory_info().rss / (1024 * 1024)
                self.record_gauge("cpu_percent", cpu)
                self.record_gauge("memory_mb", memory_mb)
            except Exception:
                pass
        return {"cpu_percent": cpu, "memory_mb": memory_mb}
