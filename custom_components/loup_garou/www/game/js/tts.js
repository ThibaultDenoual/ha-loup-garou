/**
 * Browser narration: plays the pre-recorded MP3 when there is one, otherwise
 * the browser's speech synthesis. When neither can play, it waits about as
 * long as the line would have lasted, so the game keeps its pace in silence.
 * Every line ends with tts_done, which lets the server move on.
 *
 * Phones (the Android Companion App's WebView in particular) only let a sound
 * start from a tap, and they count that per audio element. So every clip
 * plays through one element, unlocked by the first tap on the page and then
 * reused, which lets later lines start on their own.
 */

let _send;
const _player = new Audio();
_player.preload = 'auto';
let _unlocked = false;
let _current = null;   // { finish } for the line in progress

// Rough speaking rate, used when a line has no known length.
const CHARS_PER_SECOND = 14;
// Extra time before giving up on a clip or an utterance that never ends.
const STALL_MARGIN_MS = 4000;

export function init(send) {
  _send = send;
  // Trigger voice list loading (async in some browsers)
  if (window.speechSynthesis) speechSynthesis.getVoices();
  for (const type of ['pointerdown', 'keydown', 'touchend']) {
    document.addEventListener(type, _unlock, { capture: true, passive: true });
  }
}

// A short silent WAV: 8 kHz, 8-bit mono, 50 ms of the mid value 128.
function _silence() {
  const samples = 400;
  const bytes = new Uint8Array(44 + samples);
  const view = new DataView(bytes.buffer);
  const text = (offset, s) => [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, 36 + samples, true); text(8, 'WAVE');
  text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, 8000, true); view.setUint32(28, 8000, true);
  view.setUint16(32, 1, true); view.setUint16(34, 8, true);
  text(36, 'data'); view.setUint32(40, samples, true);
  bytes.fill(128, 44);
  return `data:audio/wav;base64,${btoa(String.fromCharCode(...bytes))}`;
}

// Inside a tap: play silence on the shared element so the phone unlocks it.
function _unlock() {
  if (_unlocked || _current) return;
  _player.src = _silence();
  const attempt = _player.play();
  if (attempt) {
    attempt.then(() => { _unlocked = true; _report('unlocked'); }).catch(() => {});
  }
}

// Lets tests (and curious developers) follow what the narration did.
function _report(status, detail = {}) {
  document.dispatchEvent(new CustomEvent('narration', { detail: { status, ...detail } }));
}

function _estimateMs(text, seconds) {
  if (seconds) return seconds * 1000;
  return Math.max(1500, ((text || '').length / CHARS_PER_SECOND) * 1000);
}

function _wait(ms, finish) {
  setTimeout(finish, ms);
}

function _speech(text, lang, ms, finish) {
  if (!window.speechSynthesis || !text) {
    _report('silent', { ms });
    _wait(ms, finish);
    return;
  }
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = lang === 'fr' ? 'fr-FR' : 'en-US';
  const voice = speechSynthesis.getVoices().find(v => v.lang.startsWith(lang === 'fr' ? 'fr' : 'en'));
  if (voice) utt.voice = voice;
  utt.onend = finish;
  utt.onerror = (e) => { console.warn('Speech error', e); _report('silent', { ms }); _wait(ms, finish); };
  // Some engines never fire onend; don't let the game hang on them.
  _wait(ms + STALL_MARGIN_MS, finish);
  _report('speech');
  speechSynthesis.speak(utt);
}

function _clip(url, text, lang, ms, finish) {
  const fallback = () => {
    _report('blocked', { url });
    _speech(text, lang, ms, finish);
  };
  _player.onended = finish;
  _player.onerror = fallback;
  _player.src = url;
  // A clip that stalls (network, decoder) still ends the line.
  _wait(ms + STALL_MARGIN_MS, finish);
  const attempt = _player.play();
  if (attempt) attempt.then(() => _report('played', { url })).catch(fallback);
}

/**
 * Narrate one line. Resolves when the line is over; tts_done is sent once.
 * A new line replaces the one in progress: the server has already moved on.
 */
export function speak(text, lang = 'fr', audioUrl = null, seconds = null) {
  if (_current) _current.cancel();
  return new Promise(resolve => {
    let over = false;
    const line = {
      finish() {
        if (over) return;
        over = true;
        _player.onended = _player.onerror = null;
        if (_current === line) _current = null;
        _send('tts_done');
        resolve();
      },
      cancel() {
        if (over) return;
        over = true;
        _player.onended = _player.onerror = null;
        _player.pause();
        if (window.speechSynthesis) speechSynthesis.cancel();
        resolve();
      },
    };
    _current = line;
    const ms = _estimateMs(text, seconds);
    const finish = () => line.finish();
    if (audioUrl) _clip(audioUrl, text, lang, ms, finish);
    else _speech(text, lang, ms, finish);
  });
}
