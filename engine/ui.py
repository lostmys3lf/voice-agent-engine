"""Small UI components: the synced-caption audio player and the AI disclosure.

The player reveals the caption progressively, paced by the audio element's
actual playback position — voice is primary, text is a synced caption.
Silent-failure handling: if autoplay is blocked, a manual play button appears
(and the full caption is shown) instead of failing silently.
"""

import json
from string import Template

import streamlit as st
import streamlit.components.v1 as components


def render_html(html: str, height: int) -> None:
    """Embed inline HTML/JS. Prefers st.iframe (components.v1.html is deprecated
    and slated for removal); falls back for older Streamlit versions."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height)

_PLAYER = Template("""
<div style="font-family:'Segoe UI',sans-serif;">
  <div style="display:flex;gap:10px;align-items:flex-start;">
    <div style="font-size:30px;line-height:1;">$AVATAR</div>
    <div style="background:${COLOR}14;border-left:4px solid $COLOR;padding:10px 14px;
                border-radius:10px;min-height:48px;flex:1;">
      <div style="font-weight:600;color:$COLOR;font-size:13px;margin-bottom:2px;">$NAME</div>
      <div id="cap" style="font-size:16px;line-height:1.55;color:#222;"></div>
    </div>
  </div>
  <audio id="au" src="data:audio/mpeg;base64,$B64"></audio>
  <div style="margin-top:6px;">
    <button id="pb" style="display:none;cursor:pointer;">$PLAY</button>
    <button id="rb" style="cursor:pointer;">$REPLAY</button>
  </div>
</div>
<script>
var words = $TEXT_JSON.split(/\\s+/);
var TID = "$TID";
var au = document.getElementById('au'), cap = document.getElementById('cap');
var pb = document.getElementById('pb'), rb = document.getElementById('rb');
function reveal(frac) {
  var n = Math.max(1, Math.ceil(words.length * frac));
  cap.textContent = words.slice(0, n).join(' ');
}
au.addEventListener('timeupdate', function () {
  if (au.duration > 0) reveal(Math.min(1, au.currentTime / au.duration));
});
au.addEventListener('ended', function () { reveal(1); });
pb.onclick = function () { au.currentTime = 0; au.play(); pb.style.display = 'none'; };
rb.onclick = function () { au.currentTime = 0; au.play(); };
function alreadyPlayed() {
  try { return sessionStorage.getItem('vp-' + TID); } catch (e) { return null; }
}
function markPlayed() {
  try { sessionStorage.setItem('vp-' + TID, '1'); } catch (e) {}
}
if ($AUTOPLAY && !alreadyPlayed()) {
  // autoplay guard: Streamlit reruns re-mount this iframe; only play a turn once
  au.play().then(markPlayed).catch(function () {
    // autoplay blocked by the browser -> visible fallback, never a silent failure
    pb.style.display = 'inline-block';
    reveal(1);
  });
} else {
  reveal(1);
}
</script>
""")


def audio_caption_player(text: str, audio_b64: str, persona: dict, turn_id: str,
                         autoplay: bool, strings: dict, height: int = 220) -> None:
    html = _PLAYER.substitute(
        AVATAR=persona["avatar"],
        COLOR=persona["color"],
        NAME=persona["name"],
        B64=audio_b64,
        TEXT_JSON=json.dumps(text),
        TID=turn_id,
        AUTOPLAY="true" if autoplay else "false",
        PLAY=strings["play_manual"],
        REPLAY=strings["replay"],
    )
    render_html(html, height=height)


def disclosure(strings: dict) -> None:
    st.caption(f"🔊 {strings['disclosure']}")
