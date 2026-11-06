import { test, expect } from '@playwright/test';

// Headless Chromium plays any sound, so the page gets the rule the Android
// Companion App's WebView showed in a real game instead: sound may only start
// within a moment of a tap. An <audio> element gets no lasting unlock (it was
// refused a few seconds after the last tap, though it had played before),
// while an AudioContext resumed during a tap keeps running.
//
// Note: page.evaluate() counts as user activation in Playwright, so these
// tests never call it; the narration reports reach them as console messages.
async function phoneWebView(page) {
  const statuses = [];
  page.on('console', m => {
    const [tag, status] = m.text().split(' ');
    if (tag === 'narration:') statuses.push(status);
  });
  await page.addInitScript(() => {
    // Only real input counts (Playwright's own page scripts can look like a
    // tap to navigator.userActivation), and a tap lasts as long as its handlers.
    let lastTap = -Infinity;
    for (const type of ['pointerdown', 'keydown', 'touchend']) {
      window.addEventListener(type, e => { if (e.isTrusted) lastTap = performance.now(); }, true);
    }
    const tapping = () => performance.now() - lastTap < 1000;

    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      if (!tapping()) {
        return Promise.reject(new DOMException('play() needs a tap', 'NotAllowedError'));
      }
      return play.call(this);
    };

    // An AudioContext starts suspended, and only a tap can resume it.
    const Native = window.AudioContext;
    window.AudioContext = class extends Native {
      constructor(...args) {
        super(...args);
        if (!tapping()) super.suspend();
      }
      resume() {
        if (!tapping()) return Promise.reject(new DOMException('resume() needs a tap', 'NotAllowedError'));
        return super.resume();
      }
    };
    // The WebView has no speech synthesis either.
    Object.defineProperty(window, 'speechSynthesis', { value: undefined, configurable: true });
    document.addEventListener('narration', e => console.log(`narration: ${e.detail.status}`));
  });
  return statuses;
}

// Ask the server to narrate from outside the page, so no tap is involved.
async function narrateFromServer(baseURL) {
  const ws = new WebSocket(baseURL.replace('http', 'ws') + '/loup_garou/ws');
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  const done = new Promise(resolve => {
    ws.onmessage = m => { if (JSON.parse(m.data).type === 'test_audio_done') resolve(Date.now()); };
  });
  const sent = Date.now();
  ws.send(JSON.stringify({ cmd: 'test_audio' }));
  return { ws, done, sent };
}

async function openLauncher(page) {
  const statuses = await phoneWebView(page);
  await page.goto('/loup_garou/game/launcher.html');
  await expect(page.locator('#launcher-status, .connection, body').first()).toBeVisible();
  await page.waitForTimeout(500);  // let the socket connect
  return statuses;
}

test('a line long after the last tap still plays', async ({ page, baseURL }) => {
  const statuses = await openLauncher(page);
  // A tap anywhere starts the narration's audio.
  await page.mouse.click(10, 10);
  await expect.poll(() => statuses).toContain('unlocked');
  // Like the Seer's wake after the 9 s night-fall line: well past the tap.
  await page.waitForTimeout(2500);

  const { ws } = await narrateFromServer(baseURL);
  await expect.poll(() => statuses).toContain('played');
  expect(statuses).not.toContain('blocked');
  ws.close();
});

test('a line that cannot play still lasts as long as its clip', async ({ page, baseURL }) => {
  test.setTimeout(60_000);
  const statuses = await openLauncher(page);  // no tap: the clip is refused

  const { ws, done, sent } = await narrateFromServer(baseURL);
  await expect.poll(() => statuses).toEqual(['blocked', 'silent']);
  // The night-fall clip lasts about 9 s in English: the game must not move on at once.
  expect((await done) - sent).toBeGreaterThan(8000);
  ws.close();
});
