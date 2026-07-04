"""Realtime speech-to-speech loop (primary path).

Security model: the OpenAI API key stays server-side. Python mints a
short-lived ephemeral client secret; only that secret reaches the browser,
where a minimal inline JS component (the one sanctioned exception in
CLAUDE.md) runs the WebRTC connection.

Barge-in comes from the Realtime API's server-side VAD: when the user starts
speaking, the in-progress response is interrupted automatically.

Transcript capture: the JS keeps a [{role, text}] array from the session's
transcription events and mirrors it into a hidden Streamlit text_area in the
parent page (found by aria-label = SYNC_LABEL) so Python can score it later.
"""

import requests
from string import Template

from . import config

# label of the st.text_area that receives the live transcript JSON
SYNC_LABEL = "rt-sync"


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


_RT_HTML = Template("""
<style>
  /* theme-aware text colors: the iframe sits transparently on Streamlit's page,
     so hardcoded dark text vanishes on the dark theme */
  :root { --fg:#1f2328; --muted:#667085; }
  :root.dark { --fg:#f2f3f5; --muted:#9aa4b2; }
  @media (prefers-color-scheme: dark) {
    :root:not(.light) { --fg:#f2f3f5; --muted:#9aa4b2; }
  }
</style>
<div style="font-family:'Segoe UI',sans-serif;color:var(--fg);">
  <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px;">
    <div style="font-size:32px;line-height:1;">$AVATAR</div>
    <div style="flex:1;">
      <div style="font-weight:600;color:$COLOR;">$NAME</div>
      <div id="status" style="font-size:13px;color:var(--muted);">$IDLE</div>
    </div>
    <button id="startbtn" style="font-size:15px;padding:8px 18px;cursor:pointer;
            background:$COLOR;color:#fff;border:none;border-radius:8px;">▶ $STARTLBL</button>
    <button id="stopbtn" style="display:none;font-size:15px;padding:8px 18px;cursor:pointer;
            border-radius:8px;">⏹ $STOPLBL</button>
    <button id="audiobtn" style="display:none;font-size:15px;padding:8px 12px;cursor:pointer;
            border-radius:8px;">$AUDIOLBL</button>
  </div>
  <div style="background:${COLOR}14;border-left:4px solid $COLOR;padding:10px 14px;
              border-radius:10px;min-height:56px;">
    <div id="cap" style="font-size:16px;line-height:1.55;color:var(--fg);"></div>
  </div>
  <div id="udiv" style="font-size:13px;color:var(--muted);margin-top:6px;min-height:18px;"></div>
</div>
<script>
var TOKEN = "$TOKEN", MODEL = "$MODEL", CALLS_URL = "$CALLS_URL", SYNC = "$SYNC";

// Streamlit's theme can differ from the OS preference; read the actual page
// background so the caption text always contrasts with it.
try {
  var bg = window.parent.getComputedStyle(window.parent.document.body).backgroundColor;
  var m = bg.match(/(\\d+)[, ]+(\\d+)[, ]+(\\d+)/);
  if (m) {
    var lum = 0.299 * m[1] + 0.587 * m[2] + 0.114 * m[3];
    document.documentElement.className = lum < 128 ? 'dark' : 'light';
  }
} catch (e) {}  // cross-origin etc. -> media query fallback applies
var pc = null, dc = null, audioEl = null, transcript = [], cur = "";
var statusEl = document.getElementById('status'), cap = document.getElementById('cap');
var udiv = document.getElementById('udiv');
var startBtn = document.getElementById('startbtn'), stopBtn = document.getElementById('stopbtn');
var audioBtn = document.getElementById('audiobtn');

function setStatus(t) { statusEl.textContent = t; }

// Mirror the transcript into the parent page's hidden text_area so the
// Python side can read it for scoring. Best-effort: wrapped in try/catch.
function sync() {
  try {
    var doc = window.parent.document;
    var ta = doc.querySelector('textarea[aria-label="' + SYNC + '"]');
    if (!ta) return;
    var setter = Object.getOwnPropertyDescriptor(
      window.parent.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, JSON.stringify(transcript));
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
    ta.dispatchEvent(new window.parent.FocusEvent('blur', { bubbles: true }));
  } catch (e) {}
}

async function start() {
  startBtn.style.display = 'none';
  try {
    setStatus("$ASKMIC");
    var ms = await navigator.mediaDevices.getUserMedia({ audio: true });
    pc = new RTCPeerConnection();
    audioEl = document.createElement('audio');
    audioEl.autoplay = true;
    document.body.appendChild(audioEl);
    pc.ontrack = function (e) {
      audioEl.srcObject = e.streams[0];
      var p = audioEl.play();
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
      setStatus("$CONNECTED");
      stopBtn.style.display = 'inline-block';
    };
    dc.onmessage = function (e) {
      try { handle(JSON.parse(e.data)); } catch (err) {}
    };
    var offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    var resp = await fetch(CALLS_URL + '?model=' + encodeURIComponent(MODEL), {
      method: 'POST',
      body: offer.sdp,
      headers: { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/sdp' }
    });
    if (!resp.ok) {
      setStatus('$FAILED (HTTP ' + resp.status + ')');
      startBtn.style.display = 'inline-block';
      return;
    }
    await pc.setRemoteDescription({ type: 'answer', sdp: await resp.text() });
  } catch (err) {
    setStatus('$FAILED: ' + (err && err.message ? err.message : err));
    startBtn.style.display = 'inline-block';
  }
}

function handle(ev) {
  var t = ev.type || '';
  // GA event names, with beta-era fallbacks kept for safety
  if (t === 'response.output_audio_transcript.delta' || t === 'response.audio_transcript.delta') {
    cur += (ev.delta || '');
    cap.textContent = cur;
  } else if (t === 'response.output_audio_transcript.done' || t === 'response.audio_transcript.done') {
    if (cur.trim()) { transcript.push({ role: 'assistant', text: cur.trim() }); sync(); }
    cur = '';
  } else if (t === 'conversation.item.input_audio_transcription.completed') {
    var said = (ev.transcript || '').trim();
    if (said) { transcript.push({ role: 'user', text: said }); udiv.textContent = '🗣 ' + said; sync(); }
  } else if (t === 'input_audio_buffer.speech_started') {
    setStatus('$USPEAK');   // barge-in: server VAD interrupts the response
  } else if (t === 'input_audio_buffer.speech_stopped') {
    setStatus('$THINKING');
  } else if (t === 'response.done' || t === 'response.output_audio.done') {
    setStatus('$CONNECTED');
  } else if (t === 'error') {
    setStatus('⚠ ' + ((ev.error && ev.error.message) || 'error'));
  }
}

function stop() {
  try { if (dc) dc.close(); if (pc) pc.close(); } catch (e) {}
  setStatus('$STOPPED');
  stopBtn.style.display = 'none';
  startBtn.style.display = 'inline-block';
  sync();
}

audioBtn.onclick = function () { if (audioEl) audioEl.play(); audioBtn.style.display = 'none'; };
startBtn.onclick = start;
stopBtn.onclick = stop;
</script>
""")


def realtime_html(token: str, persona: dict, strings: dict) -> str:
    """Build the inline WebRTC component HTML for st.components.v1.html."""
    return _RT_HTML.substitute(
        TOKEN=token,
        MODEL=config.MODEL_REALTIME,
        CALLS_URL=config.REALTIME_CALLS_URL,
        SYNC=SYNC_LABEL,
        AVATAR=persona["avatar"],
        COLOR=persona["color"],
        NAME=persona["name"],
        IDLE=strings["rt_idle"],
        STARTLBL=strings["rt_start"],
        STOPLBL=strings["rt_stop"],
        AUDIOLBL=strings["rt_audio_blocked"],
        ASKMIC=strings["rt_askmic"],
        CONNECTED=strings["rt_connected"],
        USPEAK=strings["rt_userspeaking"],
        THINKING=strings["rt_thinking"],
        FAILED=strings["rt_failed"],
        STOPPED=strings["rt_stopped"],
    )
