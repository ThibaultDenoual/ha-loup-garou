import { test, expect } from '@playwright/test';

// The Companion App keeps the game page open across Home Assistant restarts.
// After an update, the reconnecting page sees a new build and reloads itself.

async function serveBuilds(page) {
  const route = { build: 'build-1', sockets: [] };
  await page.routeWebSocket(/\/loup_garou\/ws$/, ws => {
    const server = ws.connectToServer();
    server.onMessage(text => {
      const msg = JSON.parse(text);
      if (msg.type === 'config') msg.config.build = route.build;
      ws.send(JSON.stringify(msg));
    });
    route.sockets.push(ws);
  });
  return route;
}

for (const path of ['index.html', 'launcher.html']) {
  test(`${path} reloads after the server was updated`, async ({ page }) => {
    const route = await serveBuilds(page);
    let loads = 0;
    page.on('load', () => { loads += 1; });
    await page.goto(`/loup_garou/game/${path}`);
    await expect.poll(() => route.sockets.length).toBe(1);
    await page.waitForTimeout(500);

    // Home Assistant restarts with the same game: no reload.
    await route.sockets.at(-1).close();
    await expect.poll(() => route.sockets.length, { timeout: 5000 }).toBe(2);
    await page.waitForTimeout(800);
    expect(loads).toBe(1);

    // Home Assistant restarts with an update: the page reloads.
    route.build = 'build-2';
    await route.sockets.at(-1).close();
    await expect.poll(() => loads, { timeout: 8000 }).toBe(2);
  });
}
