"""Streamlit entry point: stage machine + UI, scenario-agnostic.

Stage flow: setup -> briefing -> mictest -> simulation -> debrief.
All persona/role/briefing/scoring/language content comes from the active
scenario config (scenarios/); the engine never hardcodes it — see CLAUDE.md.
"""

import base64
import hashlib
import json
import os

import streamlit as st
from openai import OpenAI

from engine import audio as engine_audio
from engine import chained, realtime, scoring, ui
from engine.i18n import get_strings
from engine.scenario import (
    ScenarioError,
    build_instructions,
    build_realtime_instructions,
    format_text,
    load_scenarios,
)

st.set_page_config(page_title="Voice Agent Engine", page_icon="🎙️", layout="centered")

_DEFAULTS = {
    "stage": "setup",
    "scenario_id": None,
    "persona_key": None,
    "mode": "realtime",
    "api_key": "",
    "instructions": "",
    "history": [],
    "mic_ok": False,
    "opening_done": False,
    "rt_token": None,
    "last_audio_hash": None,
    "last_reply_b64": None,
    "last_turn_id": None,
    "scoring_result": None,
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

try:
    SCENARIOS = load_scenarios()
except ScenarioError as e:
    st.error(f"Scenario config error: {e}")
    st.stop()


def reset_conversation():
    """Clear all per-session conversation state (also on persona/scenario switch)."""
    st.session_state.history = []
    st.session_state.mic_ok = False
    st.session_state.opening_done = False
    st.session_state.rt_token = None
    st.session_state.last_audio_hash = None
    st.session_state.last_reply_b64 = None
    st.session_state.last_turn_id = None
    st.session_state.scoring_result = None
    for widget_key in ("rt_transcript_raw", "mic_test", "chat_mic"):
        st.session_state.pop(widget_key, None)


def get_client() -> OpenAI:
    return OpenAI(api_key=st.session_state.api_key)


def current_context():
    """Return (scenario, persona, strings) for the active session, or None."""
    sc = SCENARIOS.get(st.session_state.scenario_id)
    if sc is None:
        return None
    persona = next(
        (p for p in sc["personas"] if p["key"] == st.session_state.persona_key), None
    )
    if persona is None:
        return None
    return sc, persona, get_strings(sc["language"])


def parse_rt_transcript(raw: str) -> list:
    """Parse the JSON mirrored by the realtime component into engine history."""
    try:
        items = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    history = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        role = "assistant" if item.get("role") == "assistant" else "user"
        history.append({"role": role, "text": text})
    return history


# ---------------------------------------------------------------- stages ----

def render_setup():
    scenario_ids = list(SCENARIOS)
    default_ix = (
        scenario_ids.index(st.session_state.scenario_id)
        if st.session_state.scenario_id in SCENARIOS
        else 0
    )
    # strings follow the language of the scenario being previewed
    preview = SCENARIOS[scenario_ids[default_ix]]
    S = get_strings(preview["language"])

    st.title("🎙️ Voice Agent Engine")
    ui.disclosure(S)

    sel_id = st.selectbox(
        S["scenario_label"],
        scenario_ids,
        index=default_ix,
        format_func=lambda i: SCENARIOS[i]["title"],
    )
    sc = SCENARIOS[sel_id]
    S = get_strings(sc["language"])

    env_key = os.environ.get("OPENAI_API_KEY", "")
    key_input = st.text_input(S["api_key_label"], type="password")
    if env_key and not key_input:
        st.success(S["api_key_env"])

    personas = sc["personas"]
    persona_keys = [p["key"] for p in personas]
    persona_ix = (
        persona_keys.index(st.session_state.persona_key)
        if st.session_state.persona_key in persona_keys
        else 0
    )
    sel_persona = st.radio(
        S["persona_label"],
        persona_keys,
        index=persona_ix,
        format_func=lambda k: next(
            f'{p["avatar"]} {p["name"]} — {p["mood"]}' for p in personas if p["key"] == k
        ),
    )

    mode_ix = 0 if st.session_state.mode == "realtime" else 1
    sel_mode = st.radio(
        S["mode_label"], ["realtime", "chained"], index=mode_ix,
        format_func=lambda m: S["mode_realtime"] if m == "realtime" else S["mode_chained"],
    )

    if st.button(S["to_briefing"], type="primary"):
        effective_key = key_input.strip() or env_key
        if not effective_key:
            st.error(S["api_key_missing"])
            return
        persona = next(p for p in personas if p["key"] == sel_persona)
        st.session_state.scenario_id = sel_id
        st.session_state.persona_key = sel_persona
        st.session_state.mode = sel_mode
        st.session_state.api_key = effective_key
        st.session_state.instructions = build_instructions(sc, persona)
        reset_conversation()
        st.session_state.stage = "briefing"
        st.rerun()


def render_briefing(sc, persona, S):
    st.header(f'📋 {S["briefing_title"]}')
    st.markdown(format_text(sc["briefing"], sc, persona))
    ui.disclosure(S)
    col_back, col_next = st.columns(2)
    if col_back.button(S["back"]):
        st.session_state.stage = "setup"
        st.rerun()
    if col_next.button(S["to_mictest"], type="primary"):
        st.session_state.stage = "mictest"
        st.rerun()


def render_mictest(sc, persona, S):
    st.header(f'🎤 {S["mictest_title"]}')
    st.markdown(S["mictest_help"])

    sample = st.audio_input(S["mictest_record"], key="mic_test")
    if sample is not None:
        stats = engine_audio.analyze_wav(sample.getvalue())
        verdict = engine_audio.mic_verdict(stats)
        if stats:
            st.progress(min(1.0, stats["rms"] * 25), text=S["level_label"])
            st.caption(
                f'RMS {stats["rms"]:.4f} · peak {stats["peak"]:.2f} · {stats["duration"]:.1f}s'
            )
        # the gate exists to catch *silent* failure — any detected voice passes;
        # weak/saturated only warn (locking out a working mic is the worse failure)
        st.session_state.mic_ok = verdict != "none"
        st.markdown(S[f"mic_{verdict}"])

    col_back, col_next = st.columns(2)
    if col_back.button(S["back"]):
        st.session_state.stage = "briefing"
        st.rerun()
    if col_next.button(S["start_sim"], type="primary", disabled=not st.session_state.mic_ok):
        st.session_state.stage = "simulation"
        st.rerun()
    if not st.session_state.mic_ok:
        st.caption(S["mic_required"])


def render_simulation(sc, persona, S):
    st.header(f'🗣️ {S["sim_title"]} — {persona["avatar"]} {persona["name"]}')
    ui.disclosure(S)
    # keep the mission + product facts at hand during the conversation —
    # same scenario-config text as the briefing stage, just within reach
    with st.expander(S["sim_brief_label"], expanded=True):
        st.markdown(format_text(sc["briefing"], sc, persona))
    if st.session_state.mode == "realtime":
        render_realtime_sim(sc, persona, S)
    else:
        render_chained_sim(sc, persona, S)


def render_realtime_sim(sc, persona, S):
    if st.session_state.rt_token is None:
        if st.button(S["connect_start"], type="primary"):
            with st.spinner(S["connecting"]):
                try:
                    instr = build_realtime_instructions(sc, persona)
                    st.session_state.rt_token = realtime.mint_client_secret(
                        st.session_state.api_key, instr, persona["voice"], sc["language"]
                    )
                except Exception as e:  # surfaced, never crashes the rerun
                    st.error(f'{S["api_error"]}: {e}')
            if st.session_state.rt_token:
                st.rerun()
        if st.button(S["switch_to_fallback"]):
            st.session_state.mode = "chained"
            st.rerun()
        # escape hatch: a bad API key would otherwise strand the user here
        if st.button(S["back"]):
            st.session_state.stage = "mictest"
            st.rerun()
        return

    st.caption(S["rt_start_hint"])
    ui.render_html(
        realtime.realtime_html(st.session_state.rt_token, persona, S), height=260
    )
    # plumbing, not UI: the component mirrors the live transcript into this
    # text_area so Python can score it — keep it out of sight in an expander
    with st.expander(S["rt_transcript_label"], expanded=False):
        st.caption(S["rt_transcript_help"])
        st.text_area(
            realtime.SYNC_LABEL, key="rt_transcript_raw",
            label_visibility="collapsed", height=110,
        )

    col_end, col_switch = st.columns(2)
    if col_end.button(S["end_and_score"], type="primary"):
        history = parse_rt_transcript(st.session_state.get("rt_transcript_raw", ""))
        if not history:
            st.warning(S["empty_transcript_warning"])
        else:
            st.session_state.history = history
            st.session_state.stage = "debrief"
            st.rerun()
    if col_switch.button(S["switch_to_fallback"]):
        # keep whatever transcript we already have so the conversation continues
        history = parse_rt_transcript(st.session_state.get("rt_transcript_raw", ""))
        st.session_state.history = history
        st.session_state.opening_done = bool(history)
        st.session_state.mode = "chained"
        st.session_state.rt_token = None
        st.rerun()


def render_chained_sim(sc, persona, S):
    client = get_client()

    # the AI persona opens the conversation first — text AND audible voice
    if not st.session_state.opening_done:
        with st.spinner(S["opening_wait"]):
            try:
                opening_prompt = format_text(sc["opening"], sc, persona)
                text = chained.generate_reply(
                    client, st.session_state.instructions, [], opening_prompt
                )
                audio_bytes = chained.synthesize(
                    client, text, persona["voice"], persona["voice_instructions"]
                )
            except Exception as e:
                st.error(f'{S["api_error"]}: {e}')
                if st.button(S["back"]):
                    st.session_state.stage = "mictest"
                    st.rerun()
                return
        st.session_state.history.append({"role": "assistant", "text": text})
        st.session_state.last_reply_b64 = base64.b64encode(audio_bytes).decode()
        st.session_state.last_turn_id = f"t{len(st.session_state.history)}"
        st.session_state.opening_done = True

    # past turns as compact text; the latest AI turn as voice + synced caption
    history = st.session_state.history
    last_is_ai = bool(history) and history[-1]["role"] == "assistant"
    shown_as_text = history[:-1] if (last_is_ai and st.session_state.last_reply_b64) else history
    for turn in shown_as_text:
        if turn["role"] == "user":
            st.markdown(f'**🧑 {sc["roles"]["user_role"]}:** {turn["text"]}')
        else:
            st.markdown(f'**{persona["avatar"]} {persona["name"]}:** {turn["text"]}')
    if last_is_ai and st.session_state.last_reply_b64:
        ui.audio_caption_player(
            history[-1]["text"], st.session_state.last_reply_b64, persona,
            st.session_state.last_turn_id, autoplay=True, strings=S,
        )

    recording = st.audio_input(S["press_to_talk"], key="chat_mic")
    if recording is not None:
        wav = recording.getvalue()
        digest = hashlib.md5(wav).hexdigest()
        if digest != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = digest
            if process_chained_turn(client, sc, persona, S, wav):
                st.rerun()

    if st.button(S["end_and_score"], type="primary"):
        if not any(t["role"] == "user" for t in st.session_state.history):
            st.warning(S["empty_transcript_warning"])
        else:
            st.session_state.stage = "debrief"
            st.rerun()


def process_chained_turn(client, sc, persona, S, wav: bytes) -> bool:
    """One full user turn: guards -> STT -> LLM -> TTS. Returns True on success."""
    stats = engine_audio.analyze_wav(wav)
    verdict = engine_audio.mic_verdict(stats)
    if verdict == "none":
        st.warning(S["silent_warning"])
        return False
    if stats["duration"] < 0.4:
        st.warning(S["short_warning"])
        return False
    try:
        with st.spinner(S["processing"]):
            text = chained.transcribe(client, wav, sc["language"])
            if not text:
                st.warning(S["stt_empty_warning"])
                return False
            if stats["duration"] < 1.0 and len(text.split()) > 8:
                # STT hallucination guard: a long sentence can't come from <1s audio
                st.warning(S["stt_empty_warning"])
                return False
            st.session_state.history.append({"role": "user", "text": text})
            reply = chained.generate_reply(
                client, st.session_state.instructions, st.session_state.history
            )
            audio_bytes = chained.synthesize(
                client, reply, persona["voice"], persona["voice_instructions"]
            )
    except Exception as e:
        st.error(f'{S["api_error"]}: {e}')
        return False
    st.session_state.history.append({"role": "assistant", "text": reply})
    st.session_state.last_reply_b64 = base64.b64encode(audio_bytes).decode()
    st.session_state.last_turn_id = f"t{len(st.session_state.history)}"
    return True


def render_debrief(sc, persona, S):
    st.header(f'🏁 {S["debrief_title"]}')
    history = st.session_state.history
    if not history:
        st.warning(S["empty_transcript_warning"])
        if st.button(S["back"]):
            st.session_state.stage = "simulation"
            st.rerun()
        return

    if st.session_state.scoring_result is None:
        with st.spinner(S["scoring_wait"]):
            try:
                st.session_state.scoring_result = scoring.run_scoring(
                    get_client(), sc, history
                )
            except Exception as e:
                st.error(f'{S["api_error"]}: {e}')
                if st.button(S["back"]):
                    st.session_state.stage = "simulation"
                    st.rerun()
                return

    res = st.session_state.scoring_result
    headline = f'{res["verdict"]} — {res["met"]}/{res["total"]} {S["score_label"]}'
    if res["passed"]:
        st.success(f"✅ {headline}")
    else:
        st.warning(f"📈 {headline}")

    for step in res["steps"]:
        icon = "✅" if step["met"] else "❌"
        note = f' — {step["note"]}' if step["note"] else ""
        st.markdown(f'{icon} **{step["step"]}**{note}')

    st.subheader(S["feedback_label"])
    st.write(res["feedback"])

    st.download_button(
        S["download_transcript"],
        data=scoring.transcript_text(sc, history),
        file_name=f'transcript_{sc["id"]}_{persona["key"]}.txt',
        mime="text/plain",
    )
    if st.button(S["new_session"], type="primary"):
        reset_conversation()
        st.session_state.stage = "setup"
        st.rerun()


# ------------------------------------------------------------------ main ----

def render_sidebar(context):
    with st.sidebar:
        st.markdown("### 🎙️ Voice Agent Engine")
        if context:
            sc, persona, S = context
            st.markdown(f'**{sc["title"]}**')
            st.markdown(f'{persona["avatar"]} {persona["name"]} — *{persona["mood"]}*')
            mode_label = S["mode_realtime"] if st.session_state.mode == "realtime" else S["mode_chained"]
            st.caption(mode_label)
            st.caption(f'📍 {st.session_state.stage}')
            ui.disclosure(S)


context = current_context()
if st.session_state.stage != "setup" and context is None:
    st.session_state.stage = "setup"

render_sidebar(context)

if st.session_state.stage == "setup":
    render_setup()
else:
    sc, persona, S = context
    if st.session_state.stage == "briefing":
        render_briefing(sc, persona, S)
    elif st.session_state.stage == "mictest":
        render_mictest(sc, persona, S)
    elif st.session_state.stage == "simulation":
        render_simulation(sc, persona, S)
    elif st.session_state.stage == "debrief":
        render_debrief(sc, persona, S)
