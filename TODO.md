# TODO / Known Gaps (volatile — see CLAUDE.md for durable guidance)

## Needs a live smoke test (mic + speakers + API key)
- [ ] Realtime path: opening line audible, barge-in works, captions sync,
      transcript auto-fills the sync text area.
- [ ] Chained path: opening + full turn audible, caption typewriter paces with audio.
- [ ] Mic test verdicts against a real mic (thresholds in `engine/audio.py`
      `mic_verdict`: rms 0.0008 none / 0.003 weak / peak 0.99 saturated; the
      measured RMS/peak/duration now shows on-screen — use it to tune).
      Fixed 2026-07-03: float32/extensible WAV from some browsers was rejected
      by Python's `wave` module and read as "no voice"; a manual RIFF parser
      now covers it, and the gate passes on any *detected* voice (weak/clipped
      only warn). Confirm the checkmark now appears on this machine's mic.
- [ ] Scoring: run one "good" and one "bad" session, confirm verdict + threshold.

## Known fragile spots
- Realtime transcript capture writes into a hidden `st.text_area` from the
  component iframe (`engine/realtime.py::sync`). This is a known Streamlit hack;
  if a Streamlit upgrade breaks it, the "end & score" path for Realtime loses
  its transcript (chained path is unaffected — its history lives in Python).
  Mitigation idea: switch to a bidirectional custom component.
  2026-07-04: CONFIRMED live — hiding the text_area in a collapsed expander
  broke the mirror ("Belum ada percakapan yang bisa dinilai"). It now stays in
  the main body, visually hidden with CSS only (`display:none` via `:has()`).
  Re-verify at the next live session that end-&-score gets the transcript.
- Realtime turn-taking feel is tuned in `engine/realtime.py::mint_client_secret`
  (`turn_detection`: threshold 0.7, silence 1200 ms). If the persona still
  talks over pauses or reacts to room noise, adjust there. Personas now use
  the natural `cedar`/`marin` voices (Realtime-only; the chained path maps
  them via `_TTS_VOICE_FALLBACK` in `engine/chained.py`). If the voice still
  sounds robotic/tinny, suspect a Bluetooth headset dropping to HFP mode —
  test with speakers or a wired headset.
- HTML embedding uses `st.iframe` (new API; `components.v1.html` is deprecated,
  fallback kept in `engine/ui.py::render_html`). Verify live that the iframe is
  not sandboxed in a way that blocks the parent-DOM transcript sync above.
- Model IDs live in `engine/config.py` — revisit as newer models ship.
- Realtime event names: GA names are handled with beta-era fallbacks in
  `engine/realtime.py::handle`; prune the fallbacks once verified live.

## Future (Phase 2 — documented, not built)
- Hands-free continuous capture (WebRTC VAD) for the chained path.
- Scenario-authoring GUI.
- RAG / vector DB for product knowledge: NOT needed at current scale — each
  scenario embeds a compact product fact sheet in `instruction_template`, and
  those instructions ride along on every turn (Realtime session instructions /
  chained system prompt), so the persona stays on-domain by construction.
  Revisit only if a scenario's product catalog outgrows the prompt.
