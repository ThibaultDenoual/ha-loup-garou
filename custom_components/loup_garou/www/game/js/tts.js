/**
 * Browser narration: plays the pre-recorded MP3 when there is one, otherwise
 * the browser's speech synthesis. When neither can play, it waits about as
 * long as the line would have lasted, so the game keeps its pace in silence.
 * Every line ends with tts_done, which lets the server move on.
 *
 * Phones only let sound start shortly after a tap: the Android Companion App's
 * WebView refuses an <audio> play() a few seconds after the last tap, even on
 * an element that already played. So clips play through the Web Audio API:
 * a tap starts one AudioContext, and once running it plays every later clip
 * without asking again. Each tap also resumes it, in case the phone suspended
 * it (screen lock, app in the background).
 */

let _send;
let _context = null;
const _buffers = new Map();   // url → Promise<AudioBuffer>
const _fallbackPlayer = new Audio();
let _current = null;          // the line in progress

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

function _audioContext() {
  if (!_context) {
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return null;
    _context = new Context();
    const report = () => { if (_context.state === 'running') _report('unlocked'); };
    _context.addEventListener('statechange', report);
    if (_context.state === 'running') queueMicrotask(report);
  }
  return _context;
}

// Inside a tap: start (or resume) the AudioContext, with a silent buffer so
// every WebView counts it as sound started by the user.
function _unlock(event) {
  const context = _audioContext();
  if (!context || context.state === 'running') return;
  const silence = context.createBufferSource();
  silence.buffer = context.createBuffer(1, 1, 22050);
  silence.connect(context.destination);
  silence.start(0);
  context.resume().catch(error => _report('resume-refused', { on: event?.type, error: String(error) }));
}

// Lets tests follow what the narration did, and sends it to the server's
// debug log: phones give no other way to see why a line stayed silent.
function _report(status, detail = {}) {
  document.dispatchEvent(new CustomEvent('narration', { detail: { status, ...detail } }));
  try {
    _send?.('narration_log', { status, audio: _context ? _context.state : 'none', ...detail });
  } catch { /* the socket may be closed */ }
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

function _decode(url) {
  if (!_buffers.has(url)) {
    const loading = fetch(url)
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.arrayBuffer();
      })
      .then(data => _context.decodeAudioData(data));
    loading.catch(() => _buffers.delete(url));  // try again next time
    _buffers.set(url, loading);
  }
  return _buffers.get(url);
}

// Through the running AudioContext: no tap needed. Returns false if it can't.
async function _webAudio(url, line, finish) {
  const context = _audioContext();
  if (!context || context.state !== 'running') {
    _report('webaudio-not-running', { url });
    return false;
  }
  let buffer;
  try {
    buffer = await _decode(url);
  } catch (error) {
    _report('decode-failed', { url, error: String(error) });
    return false;
  }
  if (line.over) return true;
  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);
  source.onended = finish;
  line.stop = () => {
    source.onended = null;
    try { source.stop(); } catch { /* already over */ }
  };
  source.start();
  _report('played', { url, via: 'webaudio' });
  return true;
}

// Before any tap, a plain <audio> element is the only chance (desktop browsers
// allow it); a refusal falls back to speech, then to silence.
function _element(url, text, lang, ms, line, finish) {
  const fallback = () => {
    _report('blocked', { url });
    _speech(text, lang, ms, finish);
  };
  _fallbackPlayer.onended = finish;
  _fallbackPlayer.onerror = fallback;
  _fallbackPlayer.src = url;
  line.stop = () => {
    _fallbackPlayer.onended = _fallbackPlayer.onerror = null;
    _fallbackPlayer.pause();
  };
  const attempt = _fallbackPlayer.play();
  if (attempt) {
    attempt.then(() => _report('played', { url, via: 'element' }))
      .catch(error => { _report('element-refused', { url, error: String(error) }); fallback(); });
  }
}

async function _clip(url, text, lang, ms, line, finish) {
  // A clip that stalls (network, decoder) still ends the line.
  _wait(ms + STALL_MARGIN_MS, finish);
  if (await _webAudio(url, line, finish)) return;
  if (!line.over) _element(url, text, lang, ms, line, finish);
}

/**
 * Narrate one line. Resolves when the line is over; tts_done is sent once.
 * A new line replaces the one in progress: the server has already moved on.
 */
export function speak(text, lang = 'fr', audioUrl = null, seconds = null) {
  if (_current) _current.cancel();
  return new Promise(resolve => {
    const line = {
      over: false,
      stop: () => {},
      finish() {
        if (line.over) return;
        line.over = true;
        line.stop();
        if (_current === line) _current = null;
        _send('tts_done');
        resolve();
      },
      cancel() {
        if (line.over) return;
        line.over = true;
        line.stop();
        if (window.speechSynthesis) speechSynthesis.cancel();
        resolve();
      },
    };
    _current = line;
    _report('line', { url: audioUrl, text: (text || '').slice(0, 40) });
    const ms = _estimateMs(text, seconds);
    const finish = () => line.finish();
    if (audioUrl) _clip(audioUrl, text, lang, ms, line, finish);
    else _speech(text, lang, ms, finish);
  });
}
