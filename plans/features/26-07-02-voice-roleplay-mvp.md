# 🚀 Build Plan: Real-time Voice-Agent Engine (MVP, greenfield)

> **For the executing agent (Fable):** This is a **from-scratch build** of a brand-neutral portfolio project:
> a **reusable real-time voice-agent engine**, shipping with **one reference scenario** (sales roleplay) as its
> flagship demo. Read `CLAUDE.md` first — especially **"The engine / scenario boundary,"** which is the core
> design rule. This plan defines **what** to build and the **behavior** it must exhibit. You choose the concrete
> code, model IDs, and syntax — stay consistent with `CLAUDE.md`.

---

## 0. Non-negotiable framing (portfolio safety)

Going public (GitHub + LinkedIn). Therefore:

- **No real company, client, brand, product line, or internal methodology** anywhere — code, comments, prompts,
  README, personas, or commit messages. Invent fictional equivalents.
- **No confidential documents** in the repo or its git history.
- **Fresh git history** — starts from an empty `git init`. Do not import any prior `.git`.
- Reads as a **self-initiated engineering project**, not deliverable work.

---

## 1. Overview

- **What:** A **reusable real-time voice-agent engine**. The engine runs a live speech-to-speech conversation
  with a steerable AI persona, gates on a mic test, shows synced captions, falls back to a chained pipeline when
  needed, and can score the conversation afterward. **Everything scenario-specific is data** (a config file), so
  the same engine powers many use cases.
- **Reference scenario shipped:** **AI Voice Roleplay for sales training** — AI plays a customer/prospect, user
  practices as the salesperson; scored on a 6-step sales rubric. This is *one config*, chosen as the demo.
- **Why it's worth showing:** It's not "a sales demo" — it's a **voice-agent framework**. The portfolio story is
  "I built a real-time voice-agent engine; swapping a config turns it into interview practice, a language
  partner, CS training, etc." Demonstrates WebRTC speech-to-speech, barge-in, persona steering, a resilient
  fallback, ephemeral-token security, and a clean reusable boundary.

---

## 2. Scope

### ✅ In scope (MVP)
- **Scenario-agnostic engine** driving the stage flow: **setup → briefing → mic test → simulation → debrief.**
- **Scenario config layer** (`scenarios/`): the engine loads the active scenario and reads *all* persona/role/
  briefing/scoring/language content from it.
- **Primary voice loop:** Realtime **speech-to-speech** over WebRTC (AI voice streams back, no turn gap) with
  **barge-in**.
- **Fallback voice loop:** chained **STT → LLM → TTS** with a steerable voice — selectable, kept working.
- **Mic Test gate:** measure mic level, give a verdict, **lock Start until it passes.**
- **Synced/animated caption** for the AI's speech.
- **Config-driven scoring** at debrief → verdict + feedback + copyable/downloadable transcript.
- **AI-generated-voice disclosure** on screen.
- **One reference scenario** (sales roleplay): ~4 fictional personas + briefing + 6-step rubric.

### ❌ Out of scope (document as future "production stack" — do NOT build)
- LMS/SSO integration, cloud storage, multi-user scaling.
- React/SPA frontend, separate frontend repo, or a backend service (inline `components.html` JS only for Realtime).
- Hands-free continuous VAD on the *chained* fallback.
- Speaker diarization / voice enrollment.
- A GUI for authoring scenarios (config is hand-written for now).

---

## 3. The scenario config (the contract that makes it reusable)

Define a clear schema that a scenario file provides. The engine consumes **only** this — never hardcodes it.
At minimum a scenario declares:

- **`id`, `title`, `language`** (display language; reference = Bahasa Indonesia).
- **`roles`**: `ai_role` and `user_role` (e.g. AI = customer, user = salesperson). Framing only; never flips.
- **`personas`**: list, each with `name`, `avatar`, `color`, `mood`, `voice`, **`voice_instructions`**,
  `scenario_brief`, `goal`, and optional `deescalation` behavior.
- **`briefing`**: the mission/goal text shown before the sim.
- **`opening`**: the AI persona speaks first (behavior/first-line guidance).
- **`scoring`**: `steps` (rubric list), `threshold`, `pass_label`, `fail_label`, and a `feedback_prompt`.

> Design goal: **adding a use case = adding one file here.** Anything the engine needs that a scenario can't
> express is a signal the schema is missing a field — extend the schema, don't hardcode into the engine.

---

## 4. User Flow (Streamlit interactions)

1. **Setup** — enter API key → Connect; pick a **scenario** (only the reference one exists for MVP), then a
   **persona** within it.
2. **Briefing** — show the scenario's mission/goal + AI-voice disclosure.
3. **Mic Test** — record a short sample; live level bar + verdict (OK / weak / not detected). **Start stays
   locked until a passing sample exists.**
4. **Simulation** — Connect & Start; the **AI persona opens first** (audible + caption). User speaks and may
   interrupt (barge-in). Captions render live in sync with the voice.
5. **Debrief** — scoring against the scenario's rubric → verdict + feedback (in the scenario's language) +
   transcript to copy/download.

---

## 5. Architecture & Build Guidance (behavioral, not prescriptive)

Stay within `CLAUDE.md`. Key decisions:

- **Lightweight Streamlit**, split only far enough to enforce the **engine/scenario boundary** (e.g. engine
  logic vs `scenarios/`). No backend, no SPA, no service/repo layers.
- **Engine reads the active scenario config**; it must contain zero persona/role/briefing/scoring/language
  literals of its own.
- **Realtime primary + chained fallback**, both alive and selectable. Persona steered via `voice` +
  `instructions` pulled from config. Pick current capable model IDs yourself; keep the *architecture* fixed.
- **Ephemeral token** minted server-side for Realtime; **API key never reaches the browser.** Inline
  `components.html` JS runs the WebRTC connection — keep it minimal.
- **Session state** drives the stage machine, the selected scenario/persona, and conversation `history`; reset
  `history` on persona/scenario switch.
- **Scoring** is a lightweight LLM/logic pass over the transcript against the scenario's rubric → verdict at the
  configured threshold + feedback in the configured language.

DO NOT: split frontend/backend, add FastAPI/React/Pydantic/service layers, add a new state library, hardcode
scenario content into engine code, or hardcode secrets.

---

## 6. Validation & Error Handling

- Empty / silent audio → skip pipeline, ask to retry.
- No API key → block with a clear message.
- API error / timeout / rate limit → catch, surface a message, do not crash the rerun.
- Persona/scenario switch mid-session → reset conversation state.
- Malformed / incomplete scenario config → fail loudly at load with a clear message (don't half-run).

### 🔇 Silent-failure cases (MANDATORY — fail with NO exception)
State how each is **detected** and the user-facing fallback:
- Voice output returns bytes but never plays (autoplay blocked, or a rerun/sleep cuts the audio element).
- Mic captures silence (RMS ≈ 0) or saturates (RMS ≈ 1) → no transcript, no error.
- No audio input at all (permission denied, wrong device, recorder holding the mic).
- STT hallucinates a plausible sentence on silent / sub-1-second audio.

---

## 7. Testing — Proof of Behavior (NOT "no error")

> "Compiles & runs" is NOT done. "Demonstrably audible / observable" is done.

**Acceptance criteria (observable behavior + pass signal):**
- ✅ Click Start → AI's opening line is **audibly heard to the end**, caption in sync. (pass = sound plays)
- ✅ While speaking, the level indicator **moves**; RMS is neither 0.0000 nor 1.0; a sensible non-empty transcript
  appears. (pass = real input captured)
- ✅ Full turn (user speaks → AI responds) is **audible and clean** on both Realtime and chained fallback.
- ✅ Scoring: 1 "good" + 1 "bad" dummy transcript produce the correct verdict + threshold behavior.
- ✅ **Reusability check:** drop in a second throwaway scenario config (e.g. a 2-line "interview practice") → it
  appears in the picker and runs a voice turn **without any engine-code edit.** (pass = engine untouched)
- ❌ NOT acceptable: "function returns without exception", "TTS returns bytes", "code compiles", "no console error".

**Manual smoke test:** run the app → enter key → pick scenario + persona → pass mic test → confirm the opening
voice plays → do one full turn → open debrief and confirm verdict + feedback + transcript render.

---

## 8. Risks

- Realtime WebRTC live-failure risk on camera → keep the chained fallback selectable and tested.
- Chained latency stacks STT+LLM+TTS → flag if it hurts the demo feel.
- TTS naturalness in Bahasa → use a steerable voice `instructions`, not a basic TTS voice.
- Rerun-induced state/audio bugs → mount audio before any rerun/sleep.
- **Over-abstracting the config layer** → keep the schema as small as the reference scenario actually needs;
  grow it only when a real second use case demands a field.
- Token/cost impact of realtime + scoring.

---

## 9. Definition of Done

- [ ] All §7 acceptance criteria proven by the manual smoke test, with stated evidence — not "no error".
- [ ] Opening line **and** each reply are **audibly heard**; real mic input yields a sensible transcript.
- [ ] Both voice paths (Realtime primary + chained fallback) work and are selectable.
- [ ] Mic Test gate locks Start until it passes.
- [ ] Config-driven scoring + verdict + feedback (scenario language) + transcript export work.
- [ ] **Engine/scenario boundary holds:** the reusability check passes — a second scenario runs with zero engine
      edits. No persona/role/briefing/scoring/language literals live in engine code.
- [ ] Matches `CLAUDE.md`; lightweight Streamlit; no backend/SPA/service layers.
- [ ] AI-voice disclosure shown; reference scenario's user-facing output is Bahasa Indonesia.
- [ ] **Zero** real-company / client / confidential references anywhere (code, prompts, README, commits).
- [ ] Fresh git history; no imported `.git`, no brief/spec documents.
- [ ] `README.md` written as a **personal/portfolio project**, framed as a **reusable voice-agent engine** with
      sales roleplay as the example use case — no client framing.

> 🚨 **Honesty clause.** If voice-in or voice-out cannot be demonstrated working, its status is **FAILED** and
> must be reported plainly. "No error" is not evidence of success.

---

## 10. Suggested build order

1. Engine skeleton + stage machine (`setup → briefing → mictest → simulation → debrief`) + session state, with a
   **scenario loader** stub.
2. Define the **scenario config schema** + author the reference `sales_roleplay` scenario (4 fictional personas).
3. Chained fallback loop first (easiest to prove audible) → then config-driven scoring/debrief.
4. Realtime speech-to-speech loop (ephemeral token + inline WebRTC JS) + barge-in + synced caption.
5. Mic Test gate + silent-failure handling.
6. **Reusability check** with a throwaway second scenario (delete after verifying), then README + AI-voice
   disclosure + final smoke test.
