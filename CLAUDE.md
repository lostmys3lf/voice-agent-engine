# CLAUDE.md

Durable guidance for AI coding agents in this repo. This file holds **stable decisions and conventions** —
not current code state. It should rarely change as features land.

> Volatile stuff (open bugs, model-swap TODOs, "is X implemented yet") lives in `TODO.md`, **not here.**
> Reference code by **function/section name** (e.g. `render_simulation`), never by line number — line numbers rot.

---

## Project Context

- **Personal / portfolio project.** A **reusable real-time voice-agent engine**. The engine is
  **scenario-agnostic**; a concrete use case is supplied as **data (a scenario config)**, not baked into the
  engine code.
- **Reference scenario (ships in-repo): AI Voice Roleplay for sales training** — the AI plays a
  **customer/prospect**, the user practices as the **salesperson/advisor**. This is *one configuration* of the
  engine, chosen as the flagship demo — not the whole product.
- **The engine's job:** real-time speech-to-speech voice conversation with a steerable persona, with a mic-test
  gate, synced captions, a resilient fallback pipeline, and an optional post-conversation scoring pass. Swap the
  scenario config → interview practice, language partner, CS training, negotiation, etc. **without touching the
  engine.**
- Brand-neutral. Do **not** name, imply, or reproduce any real company, client, product, or internal
  methodology. Invent fictional equivalents.
- Positioned as a **technical demo**, recordable on camera. "Works on camera" = must not stall, drop audio, or
  fail mid-take. The bar is a natural, near-real-time voice conversation **without awkward pauses**. Reliability
  is the floor; that natural feel is what it's judged on.

---

## The engine / scenario boundary (the core design rule)

This is the decision that makes the project reusable — protect it.

- **Engine code is scenario-agnostic.** It must never hardcode persona text, role names, briefing copy, scoring
  criteria, or the display language. It reads all of that from the **active scenario config**.
- **A scenario is data.** Scenarios live under `scenarios/` (one per file), each exporting a config that defines:
  roles (`ai_role` / `user_role`), personas (name, avatar, colour, mood, **voice + voice `instructions`**,
  scenario brief, goal, de-escalation behavior), briefing/mission text, scoring rubric (steps, threshold,
  pass/fail labels, feedback prompt), opening behavior, and display language.
- **Adding a new use case = adding a new scenario file. No engine change.** If a new use case forces an engine
  edit, that edit belongs in the engine as a scenario-agnostic capability, and the specifics stay in config.
- Ship **one** reference scenario (sales roleplay, fictional). One is enough to prove the pattern; the value is
  that a second one would need only config.

---

## Tech Stack & Rationale

- **App**: Streamlit Python. Kept lightweight and self-contained — **no backend service, no SPA.** The code may
  be organized into a small number of modules (engine + scenarios) rather than one giant file, **but only to
  enforce the engine/scenario boundary above** — not as a license for a service/repository architecture.
- **Audio input — push-to-talk is the authoritative path.** Click record → speak → stop. Hands-free continuous
  capture (WebRTC + VAD) is fragile on this stack and is a frequent source of "mic not captured" failures —
  treat it as **Phase 2 / future**, not the primary mechanism.
- **Voice pipeline — two paths, by design:**
  - **Primary — Realtime speech-to-speech** over **WebRTC**: browser mic streams in, persona voice streams back
    with **no STT→LLM→TTS turn gap**. Persona is steered via the session `instructions` + `voice` **from the
    scenario config**. Supports **barge-in** (user can interrupt). This is the natural, no-pause feel.
  - **Fallback — chained pipeline (do NOT delete; it is the on-camera safety net).** STT → LLM → TTS with a
    steerable voice. Keep it working/selectable so a flaky Realtime connection can't kill a take.
  - Use current, capable models for each role — the agent picks concrete model IDs at build time. The **durable
    decision is the architecture** (Realtime primary, chained fallback), not any specific model string.
  - ⚠️ Realtime needs a persistent WebRTC connection in the browser → higher live-failure risk than chained.
    Mitigate; don't pretend it's free.

---

## Voice UX Principles

The demo should *feel* like a live voice conversation with a character, not a chat app that reads text aloud.

- **Voice is primary; text is a synced caption — not a script wall.** Reveal words **progressively / animated,
  in sync with the spoken audio** (live-caption / typewriter / streaming), or keep text minimal.
- **The AI persona opens the conversation first** — text *and* audible voice.
- **Audible voice output is mandatory.** Every turn must actually emit the persona's voice. Reliable playback
  outranks any input-mode polish.
- **Persona has character**: distinct avatar, colour, mood, and a **distinct steerable voice** (use the voice
  `instructions` so calm / hesitant / angry / skeptical actually sound different) — all from scenario config.

---

## Hard Rules

- **Engine stays scenario-agnostic; scenarios stay data.** No persona/role/briefing/scoring/language text
  hardcoded in engine code. (This replaces the old "single-file, personas as constants" rule.)
- **Never commit secrets.** API key comes from the UI text input or an environment variable only.
- **No client, brand, or confidential material.** No real company names, no internal briefs/PDFs, no proprietary
  methodology. Everything fictional and generic.
- **Do not over-engineer.** Stay lightweight Streamlit. No FastAPI, Pydantic, service/repo layers, or new state
  libraries. The engine/scenario split is the *only* sanctioned structure — keep it minimal.
  - **Realtime exception (narrow):** the Realtime voice loop MAY use browser-side JS embedded via
    `st.components.v1.html(...)` to run the WebRTC connection, plus a Python call to mint an **ephemeral** token
    (API key never reaches the browser). This is the ONLY sanctioned step past plain Streamlit. **Not** a
    license for a React/SPA build, a separate frontend repo, or a backend service — keep the JS inline and minimal.
- Disclose on-screen that the voice is **AI-generated**.
- Role framing is **per scenario** (e.g. AI = customer, user = salesperson) and must not flip mid-session.
- Display language is **per scenario**; the shipped reference scenario is **Bahasa Indonesia**.

---

## Scope — In / Out

### In scope
- **Scenario-agnostic engine**: stage flow (`setup → briefing → mictest → simulation → debrief`), both voice
  loops, mic-test gate, synced caption, scoring runner — all driven by the active scenario config.
- **Realtime speech-to-speech voice loop** (WebRTC) as the primary natural-feel path, with barge-in.
- **Chained voice loop** (STT → LLM → TTS) kept as the **reliability fallback** — do not delete it.
- **Mic Test gate**: verify mic permission/level (verdict OK / weak / not detected) and **lock "Start" until it
  passes.**
- **One reference scenario** (sales roleplay, fictional): ~4 personas, briefing, 6-step scoring rubric.
- **Config-driven scoring**: verdict (pass / needs-improvement) + feedback, rubric defined in scenario config.

### Out of scope (document as future "production stack" — do NOT build)
- LMS/SSO integration, cloud storage, large concurrent-user scaling.
- A React/SPA frontend, separate frontend repo, or backend service for Realtime (inline `components.html` JS only).
- Hands-free / continuous VAD on the *chained* fallback.
- Speaker diarization / voice enrollment.
- A scenario-authoring GUI (scenarios are hand-written config files for now).

---

## Edge Cases

### Silent failures — the dangerous ones for this app
Voice-to-voice fails **without throwing exceptions**, so "no error" does NOT mean "it works":
- TTS returns bytes but the browser never plays them (autoplay blocked, or a rerun/sleep cuts the audio).
- Mic captures silence (RMS ≈ 0, frame-format issue) or saturates (RMS ≈ 1) — no transcript, no error.
- STT hallucinates a plausible sentence on silent/short audio.
- Mic permission denied, or a screen recorder is holding the mic during a take → another reason the
  **Mic Test gate** matters.

### Other
- Empty / silent audio → skip pipeline, prompt retry.
- No API key → block with a clear message.
- API error → catch and surface; don't crash the rerun.
- Persona/scenario switch mid-session → reset `history`.
- Very short session (1–2 turns) → scoring must still produce sensible output.

---

## Token Economy (efficiency, NOT cutting capability)

Be deliberate with context. These reduce token use without lowering quality:

- **Read only what you need.** Don't re-read files already in context. Prefer targeted reads (specific
  functions / line ranges) over whole-file reads. The engine may be a large file — read the section you're
  touching, not all of it.
- **Reuse, don't re-derive.** If something is already established in this file or earlier in the session,
  reference it — don't re-investigate. Scenario content lives in `scenarios/`; don't re-read the engine to
  recall a persona.
- **Reference, don't paste.** Cite `file:function` instead of pasting large code blocks into plans/answers.
  Include snippets only when essential, a few lines max.
- **Plans are plans.** A plan is the deliverable of a planning step — no full functions / complete file
  rewrites in it.
- **Batch independent tool calls** in one turn instead of one-at-a-time round trips.
- **Be concise in output.** No filler, no restating instructions, no echoing this file, no repeating a point
  across sections. Short bullets over prose.

If forced to choose, correctness and completeness win — but achieve brevity first by cutting redundancy, not
substance.

---

## Verification Philosophy

**"Compiles & runs" is not done. "Demonstrably audible" is done.**

- **Always write a plan before non-trivial changes.** Write generated plans to
  `plans/features/<YY-MM-DD>-<name>.md` or `plans/fix/<YY-MM-DD>-<name>.md`.
- Acceptance criteria must describe **observable behavior** (you HEAR the voice, the mic level moves), not
  "returns 200 / no exception".
- **Manual smoke test**: run the app, connect, pick a scenario/persona, **confirm the AI's voice actually
  plays**, then do one full turn and verify it is audible and clean.
- **Reusability check**: adding a second (throwaway) scenario config must light up in the UI and run **without
  editing engine code**. If it can't, the boundary is broken.
- If an essential feature (voice in / voice out) cannot be demonstrated working, it is **NOT done** — report
  that honestly; never claim success because no error was thrown.

---

## Project Structure

```
voice-agent-engine/
├── app.py              # Streamlit entry: stage machine + UI, scenario-agnostic
├── engine/             # (or top-of-app.py sections) scenario-agnostic voice logic:
│                       #   realtime loop, chained fallback, mic-test, scoring runner, caption
├── scenarios/          # one config per use case (data, not engine logic)
│   └── sales_roleplay  # the shipped reference scenario (fictional)
├── requirements.txt
├── README.md
├── CLAUDE.md           # this file — durable guidance
├── TODO.md             # open bugs / discrepancies (volatile)
└── plans/
    ├── features/       # generated feature plans: <YY-MM-DD>-<name>.md
    └── fix/            # generated fix plans:     <YY-MM-DD>-<name>.md
```

- Refer to code by function name (e.g. `render_setup`, `render_briefing`, `render_simulation`,
  `run_scoring_and_advance`, `render_debrief`, `load_scenario`).
- The exact module split is the agent's call **as long as the engine/scenario boundary holds** — a small, clean
  split is fine; a service-layer architecture is not.
