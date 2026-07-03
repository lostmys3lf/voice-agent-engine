"""Mic-sample analysis for the mic-test gate and silent-input guards.

Voice-to-voice fails silently (no exception), so "no error" != "it works":
these checks catch silence (RMS ~ 0), clipping (peak ~ 1), and too-short takes
before any API call is made.

Browser mics (st.audio_input) are not uniform: some produce IEEE-float WAV,
which Python's `wave` module rejects ("unknown format: 3") — that used to make
a perfectly good recording read as "no voice detected". A minimal RIFF parser
below covers those cases.
"""

import io
import struct
import wave

import numpy as np

_INT_DTYPES = {2: np.int16, 4: np.int32}

_FMT_PCM = 1
_FMT_FLOAT = 3
_FMT_EXTENSIBLE = 0xFFFE


def _parse_riff(data: bytes):
    """Minimal RIFF/WAVE chunk parser for formats `wave` rejects (float32,
    WAVE_FORMAT_EXTENSIBLE). Returns (fmt_code, channels, rate, bits, raw) or None."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos, fmt, raw = 12, None, None
    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        (size,) = struct.unpack("<I", data[pos + 4:pos + 8])
        body = data[pos + 8:pos + 8 + size]
        if chunk_id == b"fmt " and len(body) >= 16:
            code, channels, rate, _, _, bits = struct.unpack("<HHIIHH", body[:16])
            if code == _FMT_EXTENSIBLE and len(body) >= 26:
                (code,) = struct.unpack("<H", body[24:26])  # subformat GUID prefix
            fmt = (code, channels, rate, bits)
        elif chunk_id == b"data":
            raw = body
        pos += 8 + size + (size & 1)  # chunks are word-aligned
    if fmt is None or raw is None:
        return None
    return (*fmt, raw)


def _samples_to_float(raw: bytes, fmt_code: int, bits: int):
    """Decode raw sample bytes to a float64 array normalized to [-1, 1], or None."""
    width = bits // 8
    if fmt_code == _FMT_FLOAT and width in (4, 8):
        dtype = np.float32 if width == 4 else np.float64
        return np.frombuffer(raw[: len(raw) - len(raw) % width], dtype=dtype).astype(np.float64)
    if fmt_code == _FMT_PCM:
        if width == 1:  # 8-bit WAV is unsigned, centered at 128
            x = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
            return (x - 128.0) / 128.0
        dtype = _INT_DTYPES.get(width)
        if dtype is not None:
            x = np.frombuffer(raw[: len(raw) - len(raw) % width], dtype=dtype).astype(np.float64)
            return x / float(np.iinfo(dtype).max)
    return None


def analyze_wav(data: bytes):
    """Return {'rms', 'peak', 'duration'} for a WAV byte blob, or None if unreadable."""
    fmt_code, channels, rate, bits, raw = _FMT_PCM, 0, 0, 0, None
    try:
        with wave.open(io.BytesIO(data)) as w:
            channels = w.getnchannels()
            rate = w.getframerate()
            bits = w.getsampwidth() * 8
            raw = w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        parsed = _parse_riff(data)  # float32 / extensible WAV that `wave` rejects
        if parsed is None:
            return None
        fmt_code, channels, rate, bits, raw = parsed

    if not raw or channels < 1 or rate <= 0 or bits <= 0:
        return None
    x = _samples_to_float(raw, fmt_code, bits)
    if x is None or x.size == 0:
        return None
    if channels > 1:
        x = x[: x.size - x.size % channels].reshape(-1, channels).mean(axis=1)

    return {
        "rms": float(np.sqrt(np.mean(x**2))),
        "peak": float(np.max(np.abs(x))),
        "duration": x.size / rate,
    }


def mic_verdict(stats) -> str:
    """Classify a mic sample: 'ok' | 'weak' | 'none' | 'saturated'.

    Thresholds are deliberately lenient: browser mics with AGC / echo
    cancellation often deliver normal speech at RMS 0.003-0.02.
    """
    if stats is None:
        return "none"
    if stats["duration"] < 0.3 or stats["rms"] < 0.0008:
        return "none"
    if stats["peak"] > 0.99 and stats["rms"] > 0.35:
        return "saturated"
    if stats["rms"] < 0.003:
        return "weak"
    return "ok"
