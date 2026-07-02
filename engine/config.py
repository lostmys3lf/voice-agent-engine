"""Model IDs, centralized so they can be swapped without touching engine logic.

The durable decision is the architecture (Realtime primary + chained fallback),
not these strings — see CLAUDE.md.
"""

# Realtime speech-to-speech over WebRTC (primary path)
MODEL_REALTIME = "gpt-realtime"

# Chained fallback pipeline: STT -> LLM -> TTS
MODEL_STT = "gpt-4o-transcribe"
MODEL_CHAT = "gpt-4.1-mini"
MODEL_TTS = "gpt-4o-mini-tts"  # steerable via `instructions`

# Post-conversation scoring pass
MODEL_SCORING = "gpt-4.1-mini"

# Ephemeral token endpoint (server-side mint; API key never reaches the browser)
REALTIME_CLIENT_SECRETS_URL = "https://api.openai.com/v1/realtime/client_secrets"
REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls"
