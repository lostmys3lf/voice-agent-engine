# 🎙️ Voice Agent Engine

A **reusable real-time voice-agent engine** built as a personal engineering project.
It runs a live speech-to-speech conversation with a steerable AI persona — mic-test
gate, synced captions, barge-in, a resilient fallback pipeline, and a post-conversation
scoring pass — and everything scenario-specific is **data, not code**.

> Swap one config file and the same engine becomes interview practice, a language
> partner, customer-service training, negotiation drills, and more.

**Reference scenario shipped:** *AI Voice Roleplay for sales training* (fictional,
in Bahasa Indonesia) — the AI plays a customer, you practice as the sales advisor,
and a SPIN-based rubric (a public sales framework) scores you at the end. All voices and personas are AI-generated,
and this is disclosed on screen.

## Architecture

```
┌───────────────────────────── Streamlit app ─────────────────────────────┐
│  Stage machine: setup → briefing → mic test → simulation → debrief      │
│                                                                          │
│  engine/            scenario-agnostic:                                   │
│   ├─ realtime.py    PRIMARY  — speech-to-speech over WebRTC (barge-in,  │
│   │                 ephemeral token minted server-side; the API key      │
│   │                 never reaches the browser)                           │
│   ├─ chained.py     FALLBACK — STT → LLM → TTS with a steerable voice   │
│   ├─ audio.py       mic-test gate & silent-input guards (RMS/peak)      │
│   ├─ scoring.py     config-driven rubric scoring + coach feedback       │
│   ├─ scenario.py    scenario discovery, validation, prompt assembly     │
│   ├─ ui.py          synced-caption audio player (voice first, text as   │
│   │                 a live caption — not a script wall)                  │
│   └─ i18n.py        engine chrome strings per language                   │
│                                                                          │
│  scenarios/         one config file per use case (pure data)             │
│   └─ sales_roleplay.py   4 fictional personas, briefing, SPIN rubric    │
└──────────────────────────────────────────────────────────────────────────┘
```

**The core design rule:** the engine never hardcodes persona text, role names,
briefing copy, scoring criteria, or display language. A scenario file declares
roles, personas (name, avatar, color, mood, voice + voice instructions, brief,
hidden goal, de-escalation), briefing, opening behavior, a scoring rubric, and
the display language. **Adding a use case = adding one file. Zero engine edits.**

## Why two voice paths?

| Path | What it is | Why it exists |
|---|---|---|
| **Realtime (primary)** | Browser mic streams over WebRTC to a speech-to-speech model; the persona's voice streams back with no STT→LLM→TTS turn gap. Supports barge-in. | The natural, no-awkward-pause feel. |
| **Chained (fallback)** | Push-to-talk → STT → LLM → steerable TTS. | A persistent WebRTC connection is the riskiest part of a live demo. The chained path keeps a take alive when Realtime is flaky. |

Both are selectable in the UI, and you can drop from Realtime to chained
mid-session without losing the transcript.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Provide an OpenAI API key either in the UI or via the `OPENAI_API_KEY`
environment variable. The key is never committed, logged, or sent to the
browser (Realtime uses a short-lived ephemeral token minted server-side).

Then: pick a scenario + persona → read the briefing → pass the mic test
(Start stays locked until your mic level is OK) → talk to the persona →
end the session for a rubric verdict, coach feedback, and a downloadable
transcript.

## Writing your own scenario

Copy `scenarios/sales_roleplay.py`, change the data, done. The schema is
documented in `engine/scenario.py`; malformed configs fail loudly at startup.
The engine picks up every `SCENARIO` dict in `scenarios/` automatically.

## Deliberate scope limits

This is a technical demo, kept lightweight on purpose: no backend service,
no SPA, no LMS/SSO, no cloud storage, no diarization, no scenario-authoring
GUI. A production build would add those around the same engine boundary.

## Disclosure

All conversation partners in this app are AI personas with AI-generated
voices. Every company, product, and person referenced in the shipped
scenario is fictional.
