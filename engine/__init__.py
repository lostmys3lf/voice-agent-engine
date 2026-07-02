"""Scenario-agnostic voice-agent engine.

Rules (see CLAUDE.md):
- No persona/role/briefing/scoring/language content lives here — all of it
  comes from the active scenario config in `scenarios/`.
- Adding a new use case = adding a new scenario file, zero engine edits.
"""
