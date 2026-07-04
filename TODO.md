# TODO / Known Gaps (volatile — see CLAUDE.md for durable guidance)

## Needs a live smoke test (mic + speakers + API key)
- [ ] Realtime path: opening line audible, barge-in works, captions sync,
      end-&-score receives the transcript (now via the v2 component state).
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
- Realtime transcript capture: 2026-07-04, after the CSS-hidden text_area
  mirror ALSO failed live (suspects: `st.iframe` sandboxing parent-DOM access,
  and/or the programmatic value never committing to the server), the whole
  DOM-mirror hack was replaced with an `st.components.v2` bidirectional
  component (`engine/realtime.py::rt_component`). The JS now runs in the main
  document (no iframe) and pushes the transcript to Python via
  `setStateValue('transcript', ...)`; Python reads `result.transcript`.
  Watch live for: (a) each completed turn triggers a script rerun (widget
  state update) — the component must NOT remount mid-session (its `key`
  keeps the identity stable, so audio should keep playing across reruns);
  (b) `st.components.v2` is a new API — pin the Streamlit version if it works.
- Realtime turn-taking feel is tuned in `engine/realtime.py::mint_client_secret`
  (`turn_detection`: threshold 0.7, silence 1200 ms). If the persona still
  talks over pauses or reacts to room noise, adjust there. Personas now use
  the natural `cedar`/`marin` voices (Realtime-only; the chained path maps
  them via `_TTS_VOICE_FALLBACK` in `engine/chained.py`). If the voice still
  sounds robotic/tinny, suspect a Bluetooth headset dropping to HFP mode —
  test with speakers or a wired headset.
- The chained caption player still embeds via `st.iframe`
  (`engine/ui.py::render_html`); it is self-contained, but its dark-theme
  detection reads the parent page background and falls back to
  `prefers-color-scheme` if the iframe is sandboxed — verify caption contrast
  live on the dark theme.
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
