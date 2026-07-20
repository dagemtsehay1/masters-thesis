"""Standalone transcription-latency benchmark for the real Whisper model.

Requires faster-whisper and the model weights (downloaded once on first
run), so unlike bench_fusion_latency.py this genuinely exercises CPU
inference - the number it prints is the one that should be checked against
the plan's "voice command latency within a practical offline bound" target
on the actual target laptop.

Run directly:
    uv run python tests/benchmarks/bench_whisper_latency.py [model_size]
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from src.speech.transcriber import WhisperTranscriber

ITERATIONS = 10


def main():
    model_size = sys.argv[1] if len(sys.argv) > 1 else "small"
    print(f"Loading Whisper model '{model_size}' (first run downloads weights)...")
    transcriber = WhisperTranscriber(model_size=model_size, device="cpu", compute_type="int8")

    # ~2s of quiet noise stands in for a short spoken command.
    audio = (np.random.randn(32000) * 200).astype(np.int16).tobytes()

    # Warm-up (first call includes lazy allocation the steady state won't).
    transcriber.transcribe_pcm16(audio, 16000)

    latencies = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        transcriber.transcribe_pcm16(audio, 16000)
        latencies.append((time.perf_counter() - start) * 1000)

    latencies.sort()
    print(f"Whisper '{model_size}' transcription over {ITERATIONS} calls (~2s audio each):")
    print(f"  mean:   {statistics.mean(latencies):.0f} ms")
    print(f"  median: {latencies[len(latencies) // 2]:.0f} ms")
    print(f"  p95:    {latencies[int(len(latencies) * 0.95)]:.0f} ms")


if __name__ == "__main__":
    main()
