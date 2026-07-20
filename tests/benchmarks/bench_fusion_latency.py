"""Standalone latency benchmark for FusionEngine.resolve().

Not a pytest test - fusion is pure in-process logic, so this exists to put
an actual number next to the plan's "fusion decision latency should be
sub-millisecond, confirming fusion is never the pipeline's bottleneck"
claim, rather than assuming it.

Run directly:
    uv run python tests/benchmarks/bench_fusion_latency.py
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config.schema import FusionConfig
from src.fusion.engine import FusionEngine
from src.gesture.events import GestureEvent
from src.voice.events import VoiceEvent

ITERATIONS = 10_000


def main():
    engine = FusionEngine(FusionConfig(mode="combined", duplicate_command_cooldown_ms=0))
    voice_event = VoiceEvent(command="go")
    gesture_event = GestureEvent(gesture="left", state="confirmed")

    samples_ms = []
    for i in range(ITERATIONS):
        start = time.perf_counter()
        engine.resolve(voice_event, gesture_event, now=time.time() + i * 10)  # advance "now" past cooldown each call
        samples_ms.append((time.perf_counter() - start) * 1000)

    samples_ms.sort()
    p50 = samples_ms[len(samples_ms) // 2]
    p95 = samples_ms[int(len(samples_ms) * 0.95)]
    print(f"FusionEngine.resolve() over {ITERATIONS} calls:")
    print(f"  mean:   {statistics.mean(samples_ms):.4f} ms")
    print(f"  median: {p50:.4f} ms")
    print(f"  p95:    {p95:.4f} ms")
    print(f"  max:    {max(samples_ms):.4f} ms")


if __name__ == "__main__":
    main()
