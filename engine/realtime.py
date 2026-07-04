"""Realtime speech-to-speech loop (primary path).

Security model: the OpenAI API key stays server-side. Python mints a
short-lived ephemeral client secret; only that secret reaches the browser,
where a minimal JS component (the one sanctioned exception in CLAUDE.md)
runs the WebRTC connection.

Barge-in comes from the Realtime API's server-side VAD: when the user starts
speaking, the in-progress response is interrupted automatically.

Transcript capture: the component is an `st.components.v2` bidirectional
component — its JS sends the [{role, text}] transcript to Python via
setStateValue('transcript', ...), read back as `result.transcript`. This
replaced the old hidden-text_area DOM-mirror hack, which failed silently
(sandboxed iframe / uncommitted widget value) and cost two live takes.
"""

import requests
import streamlit.components.v2 as components_v2

from . import config

# session_state key of the mounted component (its state must be cleared on reset)
RT_COMPONENT_KEY = "rt_voice"


def mint_client_secret(api_key: str, instructions: str, voice: str, language: str) -> str:
    """Server-side mint of an ephemeral Realtime token (API key never leaves Python)."""
    payload = {
        "expires_after": {"anchor": "created_at", "seconds": 600},
        "session": {
            "type": "realtime",
            "model": config.MODEL_REALTIME,
            "instructions": instructions,
            "audio": {
                "input": {
                    "transcription": {"model": config.MODEL_STT, "language": language},
                    # turn-taking feel lives here: higher threshold so room noise
                    # doesn't count as the user talking; longer silence window so
                    # the persona waits out natural pauses instead of jumping in
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.7,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 1200,
                    },
                },
                "output": {"voice": voice},
            },
        },
    }
    resp = requests.post(
        config.REALTIME_CLIENT_SECRETS_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    if not resp.ok:
        # surface OpenAI's own error message, not just "400 Client Error"
        try:
            detail = resp.json()["error"]["message"]
        except Exception:
            detail = resp.text[:300]
        raise RuntimeError(f"HTTP {resp.status_code} — {detail}")
    return resp.json()["value"]


# Static markup — persona/labels are filled in by the JS from `data`,
# so the component registers once and stays scenario-agnostic.
_RT_HTML = """
<div class="rt-root">
  <div class="rt-head">
    <div class="rt-avatar" id="rt-avatar"></div>
    <div class="rt-id">
      <div class="rt-name" id="rt-name"></div>
      <div class="rt-status" id="rt-status"></div>
    </div>
    <button id="rt-start" class="rt-btn"></button>
    <button id="rt-stop" class="rt-btn" style="display:none;"></button>
    <button id="rt-audio" class="rt-btn" style="display:none;"></button>
  </div>
  <div class="rt-capbox" id="rt-capbox">
    <div id="rt-cap" class="rt-cap"></div>
  </div>
  <div id="rt-usaid" class="rt-usaid"></div>
</div>
"""

# The component lives in the app's own DOM (no iframe), so `color` simply
# inherits the active Streamlit theme — no dark/light detection needed.
_RT_CSS = """
.rt-root { color: inherit; }
.rt-head { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.rt-avatar { font-size: 32px; line-height: 1; }
.rt-id { flex: 1; }
.rt-name { font-weight: 600; }
.rt-status { font-size: 13px; opacity: .7; }
.rt-btn { font-size: 15px; padding: 8px 18px; cursor: pointer; border: none; border-radius: 8px; }
#rt-start { color: #fff; }
.rt-capbox { border-left: 4px solid; padding: 10px 14px; border-radius: 10px; min-height: 56px; }
.rt-cap { font-size: 16px; line-height: 1.55; }
.rt-usaid { font-size: 13px; opacity: .7; margin-top: 6px; min-height: 18px; }
"""

_RT_JS = """
export default function (component) {
  const { data, setStateValue, parentElement } = component;
  const S = data.strings;
  const q = (id) => parentElement.querySelector('#' + id);
  const statusEl = q('rt-status'), cap = q('rt-cap'), usaid = q('rt-usaid');
  const startBtn = q('rt-start'), stopBtn = q('rt-stop'), audioBtn = q('rt-audio');
  const capbox = q('rt-capbox'), nameEl = q('rt-name');

  q('rt-avatar').textContent = data.avatar;
  nameEl.textContent = data.name;
  nameEl.style.color = data.color;
  startBtn.textContent = '\\u25B6 ' + S.start;
  startBtn.style.background = data.color;
  stopBtn.textContent = '\\u23F9 ' + S.stop;
  audioBtn.textContent = S.audio_blocked;
  capbox.style.borderLeftColor = data.color;
  capbox.style.background = data.color + '14';

  let pc = null, dc = null, ms = null, audioEl = null;
  let transcript = [], cur = '';

  function setStatus(t) { statusEl.textContent = t; }
  setStatus(S.idle);

  // official channel to Python: the transcript arrives as result.transcript
  function sync() { setStateValue('transcript', transcript.slice()); }

  async function start() {
    startBtn.style.display = 'none';
    try {
      setStatus(S.askmic);
      ms = await navigator.mediaDevices.getUserMedia({ audio: true });
      pc = new RTCPeerConnection();
      audioEl = document.createElement('audio');
      audioEl.autoplay = true;
      parentElement.appendChild(audioEl);
      pc.ontrack = function (e) {
        audioEl.srcObject = e.streams[0];
        const p = audioEl.play();
        if (p && p.catch) p.catch(function () {
          // autoplay blocked -> visible unlock button, never a silent failure
          audioBtn.style.display = 'inline-block';
        });
      };
      pc.addTrack(ms.getAudioTracks()[0], ms);
      dc = pc.createDataChannel('oai-events');
      dc.onopen = function () {
        // the persona opens the conversation first
        dc.send(JSON.stringify({ type: 'response.create' }));
        setStatus(S.connected);
        stopBtn.style.display = 'inline-block';
      };
      dc.onmessage = function (e) {
        try { handle(JSON.parse(e.data)); } catch (err) {}
      };
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      const resp = await fetch(data.callsUrl + '?model=' + encodeURIComponent(data.model), {
        method: 'POST',
        body: offer.sdp,
        headers: { 'Authorization': 'Bearer ' + data.token, 'Content-Type': 'application/sdp' }
      });
      if (!resp.ok) {
        setStatus(S.failed + ' (HTTP ' + resp.status + ')');
        startBtn.style.display = 'inline-block';
        return;
      }
      await pc.setRemoteDescription({ type: 'answer', sdp: await resp.text() });
    } catch (err) {
      setStatus(S.failed + ': ' + (err && err.message ? err.message : err));
      startBtn.style.display = 'inline-block';
    }
  }

  function handle(ev) {
    const t = ev.type || '';
    // GA event names, with beta-era fallbacks kept for safety
    if (t === 'response.output_audio_transcript.delta' || t === 'response.audio_transcript.delta') {
      cur += (ev.delta || '');
      cap.textContent = cur;
    } else if (t === 'response.output_audio_transcript.done' || t === 'response.audio_transcript.done') {
      if (cur.trim()) { transcript.push({ role: 'assistant', text: cur.trim() }); sync(); }
      cur = '';
    } else if (t === 'conversation.item.input_audio_transcription.completed') {
      const said = (ev.transcript || '').trim();
      if (said) { transcript.push({ role: 'user', text: said }); usaid.textContent = '\\u{1F5E3} ' + said; sync(); }
    } else if (t === 'input_audio_buffer.speech_started') {
      setStatus(S.userspeaking);   // barge-in: server VAD interrupts the response
    } else if (t === 'input_audio_buffer.speech_stopped') {
      setStatus(S.thinking);
    } else if (t === 'response.done' || t === 'response.output_audio.done') {
      setStatus(S.connected);
    } else if (t === 'error') {
      setStatus('\\u26A0 ' + ((ev.error && ev.error.message) || 'error'));
    }
  }

  function stop() {
    try { if (dc) dc.close(); if (pc) pc.close(); } catch (e) {}
    setStatus(S.stopped);
    stopBtn.style.display = 'none';
    startBtn.style.display = 'inline-block';
    sync();
  }

  audioBtn.onclick = function () { if (audioEl) audioEl.play(); audioBtn.style.display = 'none'; };
  startBtn.onclick = start;
  stopBtn.onclick = stop;

  // unmount (stage change / rerun teardown): release the mic and the connection
  return function () {
    try {
      if (dc) dc.close();
      if (pc) pc.close();
      if (ms) ms.getTracks().forEach(function (tr) { tr.stop(); });
    } catch (e) {}
  };
}
"""

def _noop() -> None:
    """Registered as on_transcript_change so 'transcript' is a valid state key."""


def rt_component(token: str, persona: dict, strings: dict):
    """Mount the Realtime WebRTC component; returns its ComponentResult.

    `result.transcript` is the live [{role, text}] list the JS keeps in sync.
    Registered on every call: the registry lives on the active runtime, and
    re-registering an identical definition is silent by design.
    """
    factory = components_v2.component(
        "rt_voice", html=_RT_HTML, css=_RT_CSS, js=_RT_JS
    )
    return factory(
        key=RT_COMPONENT_KEY,
        data={
            "token": token,
            "model": config.MODEL_REALTIME,
            "callsUrl": config.REALTIME_CALLS_URL,
            "avatar": persona["avatar"],
            "name": persona["name"],
            "color": persona["color"],
            "strings": {
                "idle": strings["rt_idle"],
                "start": strings["rt_start"],
                "stop": strings["rt_stop"],
                "audio_blocked": strings["rt_audio_blocked"],
                "askmic": strings["rt_askmic"],
                "connected": strings["rt_connected"],
                "userspeaking": strings["rt_userspeaking"],
                "thinking": strings["rt_thinking"],
                "failed": strings["rt_failed"],
                "stopped": strings["rt_stopped"],
            },
        },
        default={"transcript": []},
        on_transcript_change=_noop,
    )
