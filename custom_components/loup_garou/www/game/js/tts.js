/**
 * Browser TTS — plays pre-recorded MP3 when audio_url is provided, otherwise
 * falls back to Web Speech API.  On any error the promise resolves immediately
 * so the game never stalls client-side.  After resolving the server is
 * notified via tts_done so it can unblock the game engine for the next phase.
 */

let _send;

export function init(send) {
  _send = send;
  // Trigger voice list loading (async in some browsers)
  if (window.speechSynthesis) {
    speechSynthesis.getVoices();
  }
}

function speakWebSpeech(text, lang) {
  if (!window.speechSynthesis || !text) {
    _send('tts_done');
    return Promise.resolve();
  }

  return new Promise(resolve => {
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = lang === 'fr' ? 'fr-FR' : 'en-US';

    const voices = speechSynthesis.getVoices();
    const voice = voices.find(v => v.lang.startsWith(lang === 'fr' ? 'fr' : 'en')) || null;
    if (voice) utt.voice = voice;

    const done = () => { _send('tts_done'); resolve(); };
    utt.onend   = done;
    utt.onerror = (e) => { console.warn('TTS error', e); done(); };

    speechSynthesis.speak(utt);
  });
}

export function speak(text, lang = 'fr', audioUrl = null) {
  if (audioUrl) {
    return new Promise(resolve => {
      const audio = new Audio(audioUrl);
      audio.onended = () => { _send('tts_done'); resolve(); };
      audio.onerror = () => speakWebSpeech(text, lang).then(resolve);
      audio.play().catch(() => speakWebSpeech(text, lang).then(resolve));
    });
  }
  return speakWebSpeech(text, lang);
}
