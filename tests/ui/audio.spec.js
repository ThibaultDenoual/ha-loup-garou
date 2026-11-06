import { test, expect } from '@playwright/test';

// Headless Chromium plays any sound, so the page gets the Android WebView's
// rule instead (mediaPlaybackRequiresUserGesture): an audio element may only
// start during a tap, and once it has, it may play again later on its own.
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
    const unlocked = new WeakSet();
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      if (performance.now() - lastTap < 1000) unlocked.add(this);
      if (!unlocked.has(this)) {
        return Promise.reject(new DOMException('play() needs a tap', 'NotAllowedError'));
      }
      return play.call(this);
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

test('after one tap, a line that starts on its own plays', async ({ page, baseURL }) => {
  const statuses = await openLauncher(page);
  // A tap anywhere unlocks the narration player.
  await page.mouse.click(10, 10);
  await expect.poll(() => statuses).toContain('unlocked');

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
