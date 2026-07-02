"""Mic-sample analysis for the mic-test gate and silent-input guards.

Voice-to-voice fails silently (no exception), so "no error" != "it works":
these checks catch silence (RMS ~ 0), clipping (peak ~ 1), and too-short takes
before any API call is made.
"""

import io
import wave

import numpy as np

_DTYPES = {1: np.int8, 2: np.int16, 4: np.int32}


def analyze_wav(data: bytes):
    """Return {'rms', 'peak', 'duration'} for a WAV byte blob, or None if unreadable."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            n_frames = w.getnframes()
            sample_rate = w.getframerate()
            sample_width = w.getsampwidth()
            channels = w.getnchannels()
            raw = w.readframes(n_frames)
    except (wave.Error, EOFError):
        return None

    dtype = _DTYPES.get(sample_width)
    if dtype is None or n_frames == 0 or sample_rate == 0:
        return None

    x = np.frombuffer(raw, dtype=dtype).astype(np.float64)
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    x /= float(np.iinfo(dtype).max)

    return {
        "rms": float(np.sqrt(np.mean(x**2))) if x.size else 0.0,
        "peak": float(np.max(np.abs(x))) if x.size else 0.0,
        "duration": n_frames / sample_rate,
    }


def mic_verdict(stats) -> str:
    """Classify a mic sample: 'ok' | 'weak' | 'none' | 'saturated'."""
    if stats is None:
        return "none"
    if stats["duration"] < 0.3 or stats["rms"] < 0.0015:
        return "none"
    if stats["peak"] > 0.99 and stats["rms"] > 0.4:
        return "saturated"
    if stats["rms"] < 0.01:
        return "weak"
    return "ok"
