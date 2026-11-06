import { test, expect } from '@playwright/test';

// The phone is passed around during the reveal, so the page must fit one
// screen: no page scroll, and the whole card readable without scrolling it.

async function send(baseURL, ...commands) {
  const ws = new WebSocket(baseURL.replace('http', 'ws') + '/loup_garou/ws');
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  for (const [cmd, data] of commands) {
    ws.send(JSON.stringify({ cmd, data }));
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  ws.close();
}

const fits = page => page.evaluate(() => {
  const face = document.querySelector('#reveal-card .flipped .card-back, #reveal-card.flipped .card-back')
    || document.querySelector('#reveal-card .card-front');
  return {
    page: document.scrollingElement.scrollHeight <= innerHeight,
    card: face.scrollHeight <= face.clientHeight + 1,
  };
});

for (const [width, height] of [[360, 640], [390, 844]]) {
  test(`the reveal fits one ${width}×${height} screen`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height });
    // The Minion has the longest role text; the first player also gets the intro.
    await send(baseURL, ['abandon_game', {}], ['start_game', {
      players: ['Maximilienne', 'Lou', 'Wolfgang'], roles: ['minion', 'little_girl', 'werewolf'],
    }]);
    await page.goto('/loup_garou/game/index.html');
    await expect(page.locator('#view-reveal')).toBeVisible();
    await expect(page.locator('#reveal-intro')).toBeVisible();
    expect(await fits(page)).toEqual({ page: true, card: true });

    await page.locator('#reveal-card').click();
    await expect(page.locator('#btn-reveal-seen')).toBeVisible();
    await page.waitForTimeout(700);  // the flip
    expect(await fits(page)).toEqual({ page: true, card: true });

    await send(baseURL, ['abandon_game', {}]);
  });
}
