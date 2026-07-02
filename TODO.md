# TODO / Known Gaps (volatile — see CLAUDE.md for durable guidance)

## Needs a live smoke test (mic + speakers + API key)
- [ ] Realtime path: opening line audible, barge-in works, captions sync,
      transcript auto-fills the sync text area.
- [ ] Chained path: opening + full turn audible, caption typewriter paces with audio.
- [ ] Mic test verdicts against a real mic (thresholds in `engine/audio.py`
      `mic_verdict` may need tuning: rms 0.0015 none / 0.01 weak / peak 0.99 saturated).
- [ ] Scoring: run one "good" and one "bad" session, confirm verdict + threshold.

## Known fragile spots
- Realtime transcript capture writes into a hidden `st.text_area` from the
  component iframe (`engine/realtime.py::sync`). This is a known Streamlit hack;
  if a Streamlit upgrade breaks it, the "end & score" path for Realtime loses
  its transcript (chained path is unaffected — its history lives in Python).
  Mitigation idea: switch to a bidirectional custom component.
- HTML embedding uses `st.iframe` (new API; `components.v1.html` is deprecated,
  fallback kept in `engine/ui.py::render_html`). Verify live that the iframe is
  not sandboxed in a way that blocks the parent-DOM transcript sync above.
- Model IDs live in `engine/config.py` — revisit as newer models ship.
- Realtime event names: GA names are handled with beta-era fallbacks in
  `engine/realtime.py::handle`; prune the fallbacks once verified live.

## Future (Phase 2 — documented, not built)
- Hands-free continuous capture (WebRTC VAD) for the chained path.
- Scenario-authoring GUI.
