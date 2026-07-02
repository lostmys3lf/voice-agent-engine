"""Chained fallback voice loop: STT -> LLM -> TTS.

This is the on-camera safety net when the Realtime WebRTC path is flaky —
do NOT delete it (see CLAUDE.md). All persona content arrives as arguments;
nothing scenario-specific lives here.
"""

import io

from . import config


def transcribe(client, wav_bytes: bytes, language: str) -> str:
    """Speech-to-text for one push-to-talk recording. Returns stripped text."""
    f = io.BytesIO(wav_bytes)
    f.name = "audio.wav"  # the SDK needs a filename to infer the format
    result = client.audio.transcriptions.create(
        model=config.MODEL_STT, file=f, language=language
    )
    return (result.text or "").strip()


def generate_reply(client, instructions: str, history: list, extra_user_text: str = None) -> str:
    """One persona reply. `history` is [{'role': 'user'|'assistant', 'text': ...}].

    `extra_user_text` lets the caller inject a turn that should steer the model
    but not be stored in history (e.g. the scenario's opening directive).
    """
    messages = [{"role": "system", "content": instructions}]
    for turn in history:
        role = "assistant" if turn["role"] == "assistant" else "user"
        messages.append({"role": role, "content": turn["text"]})
    if extra_user_text:
        messages.append({"role": "user", "content": extra_user_text})
    result = client.chat.completions.create(
        model=config.MODEL_CHAT, messages=messages, max_tokens=300, temperature=0.8
    )
    return result.choices[0].message.content.strip()


def synthesize(client, text: str, voice: str, voice_instructions: str) -> bytes:
    """Steerable TTS — `voice_instructions` is what makes personas sound distinct."""
    result = client.audio.speech.create(
        model=config.MODEL_TTS,
        voice=voice,
        input=text,
        instructions=voice_instructions,
        response_format="mp3",
    )
    return result.content
