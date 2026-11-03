import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const screenshotDir = join(process.cwd(), 'screenshots', 'automated');

async function capture(page, name) {
  await mkdir(screenshotDir, { recursive: true });
  await page.screenshot({
    path: join(screenshotDir, `${name}.png`),
    animations: 'disabled',
  });
}

async function playerCard(grid, name) {
  const cards = grid.locator('.player-card');
  for (let index = 0; index < await cards.count(); index++) {
    const card = cards.nth(index);
    if ((await card.locator('.player-name').textContent())?.trim() === name) return card;
  }
  throw new Error(`No target card for ${name}`);
}

// The dev server is shared across tests: start each one from setup.
test.beforeEach(async ({ page }) => {
  page.on('dialog', dialog => dialog.accept());
  await page.goto('/loup_garou/game/index.html');
  await expect(page.locator('#ws-status')).toHaveClass(/connected/);
  await expect(page.locator('#view-setup, #view-reveal, #view-night, #view-day, #view-vote, #view-game-over').locator('visible=true')).toHaveCount(1);
  if (await page.locator('#btn-abandon').isVisible()) {
    await page.locator('#btn-abandon').click();
    await expect(page.locator('#view-setup')).toBeVisible();
  }
});

test('launcher tabs load localized content and settings', async ({ page }) => {
  await page.goto('/loup_garou/game/launcher.html');
  await expect(page.locator('#ha-connection')).toHaveClass(/connected/);
  await expect(page.locator('.subtitle')).toHaveText('Your village game master');
  await capture(page, 'launcher-home');

  await page.getByRole('tab', { name: 'Rules' }).click();
  await expect(page.locator('#role-ref .role-row')).toHaveCount(12);
  await expect(page.locator('#tab-rules')).toContainText('The story');
  await capture(page, 'launcher-rules');

  await page.getByRole('tab', { name: 'Game setup' }).click();
  await expect(page.locator('#cfg-language')).toHaveValue('en');
  await expect(page.locator('#btn-save-config')).toHaveText('Save settings');
  await capture(page, 'launcher-settings');
});

test('pass-the-phone game includes seer, werewolf, witch, day, vote, and victory', async ({ page }) => {
  const names = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve'];
  const rolesByPlayer = new Map();

  await page.goto('/loup_garou/game/index.html');
  await expect(page.locator('#st-phase')).toHaveText('Prepare the village');
  await capture(page, 'game-setup-empty');

  for (const name of names) {
    await page.locator('#btn-add-player').click();
    await page.locator('#setup-player-list input').last().fill(name);
  }
  for (const [role, count] of [['werewolf', 1], ['seer', 1], ['witch', 1], ['villager', 2]]) {
    const row = page.locator(`.role-slot-row[data-role-id="${role}"]`);
    for (let i = 0; i < count; i++) await row.locator('button').nth(1).click();
  }
  await expect(page.locator('#role-total-label')).toHaveText('5 / 5 roles');
  await expect(page.locator('#btn-start-game')).toBeEnabled();
  await page.evaluate(() => window.scrollTo(0, 0));
  await capture(page, 'game-setup-filled');

  await page.locator('#btn-start-game').click();
  await expect(page.locator('#view-reveal')).toBeVisible();
  for (let index = 0; index < names.length; index++) {
    const name = names[index];
    await expect(page.locator('#reveal-player-label')).toHaveText(name, { timeout: 10_000 });
    if (index === 0) await capture(page, 'role-reveal-handoff');

    await page.locator('#reveal-card').click();
    await expect(page.locator('#reveal-card')).toHaveClass(/flipped/);
    await expect(page.locator('#btn-reveal-seen')).toBeVisible();
    const role = (await page.locator('.reveal-role-name').textContent())?.trim();
    rolesByPlayer.set(name, role);
    if (index === 0) await capture(page, 'role-reveal-card');
    if (role === 'Werewolf') await capture(page, 'role-reveal-werewolf');
    await page.locator('#btn-reveal-seen').click();
  }

  const werewolf = [...rolesByPlayer].find(([, role]) => role === 'Werewolf')?.[0];
  expect(werewolf, 'the role shuffle should assign one werewolf').toBeTruthy();
  await expect(page.locator('#view-night')).toBeVisible();
  // Seer investigates the werewolf, then privately acknowledges the result.
  await expect(page.locator('#night-action')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#na-role-name')).toHaveText('Seer');
  await (await playerCard(page.locator('#na-grid'), werewolf)).click();
  await page.locator('#btn-na-confirm').click();
  await expect(page.locator('#night-seer')).toBeVisible();
  await expect(page.locator('#seer-role')).toHaveText('Werewolf');
  await capture(page, 'seer-result');
  await page.locator('#btn-seer-ack').click();

  // Wolves select a non-wolf, keeping the game alive for the Witch/day flow.
  await expect(page.locator('#night-action')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#na-role-name')).toHaveText('Werewolf');
  const wolfVictim = names.find(name => name !== werewolf);
  await (await playerCard(page.locator('#na-grid'), wolfVictim)).click();
  await expect(page.locator('#btn-na-confirm')).toBeEnabled();
  await capture(page, 'werewolf-target');
  await page.locator('#btn-na-confirm').click();

  // Witch sees the pending victim; inspect poison targeting, then save instead.
  await expect(page.locator('#night-action')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#na-role-name')).toHaveText('Witch');
  await expect(page.locator('#na-prompt')).toHaveText("Manage your potions.");
  await expect(page.locator('#na-victim')).toContainText(wolfVictim);
  await expect(page.locator('#witch-save-btn')).toBeEnabled();
  await expect(page.locator('#na-grid .player-card')).toHaveCount(0);
  await capture(page, 'witch-wake');

  await page.locator('#witch-poison-btn').click();
  await expect(page.locator('#na-grid .player-card')).toHaveCount(4);
  await capture(page, 'witch-poison-targets');
  await page.locator('#witch-poison-btn').click();

  await page.locator('#witch-save-btn').click();
  await expect(page.locator('#witch-save-btn')).toHaveClass(/active/);
  await capture(page, 'witch-save-selected');
  await page.locator('#btn-na-confirm').click();

  // Saving the victim yields a no-death morning, then the village votes out the wolf.
  await expect(page.locator('#view-day')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#day-announcement')).toContainText('no one was harmed');
  await capture(page, 'day-no-death');
  await page.locator('#btn-day-vote').click();
  await expect(page.locator('#view-vote')).toBeVisible();
  await expect(page.locator('#vote-ballot')).toBeVisible();
  await capture(page, 'village-vote');

  for (let turn = 0; turn < names.length; turn++) {
    if (await page.locator('#view-game-over').isVisible()) break;
    const voter = (await page.locator('#vote-voter-name').textContent())?.trim();
    const target = voter === werewolf ? names.find(name => name !== werewolf) : werewolf;
    await (await playerCard(page.locator('#vote-grid'), target)).click();
    await page.locator('#btn-vote-confirm').click();
  }

  await expect(page.locator('#view-game-over')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#go-msg')).toContainText('village wins');
  await capture(page, 'game-over-village');

  await page.locator('#btn-restart').click();
  await expect(page.locator('#view-setup')).toBeVisible();
  await expect(page.locator('#setup-player-list input')).toHaveCount(names.length);
});

test('a reload in the middle of a vote carries on from the open ballot', async ({ page }) => {
  const names = ['Alice', 'Bob', 'Carol', 'Dave'];
  await page.goto('/loup_garou/game/index.html');
  for (const name of names) {
    await page.locator('#btn-add-player').click();
    await page.locator('#setup-player-list input').last().fill(name);
  }
  for (const [role, count] of [['werewolf', 1], ['villager', 3]]) {
    const row = page.locator(`.role-slot-row[data-role-id="${role}"]`);
    for (let i = 0; i < count; i++) await row.locator('button').nth(1).click();
  }
  await page.locator('#btn-start-game').click();
  for (const name of names) {
    await expect(page.locator('#reveal-player-label')).toHaveText(name);
    await page.locator('#reveal-card').click();
    await page.locator('#btn-reveal-seen').click();
  }

  // Nobody is eaten; the reload lands back on the same turn.
  await expect(page.locator('#na-role-name')).toHaveText('Werewolf');
  await page.reload();
  await expect(page.locator('#na-role-name')).toHaveText('Werewolf');
  await page.locator('#btn-na-skip').click();

  await page.locator('#btn-day-vote').click();
  await expect(page.locator('#vote-progress')).toHaveText('Votes: 0 of 4');
  await (await playerCard(page.locator('#vote-grid'), 'Carol')).click();
  await page.locator('#btn-vote-confirm').click();
  await expect(page.locator('#vote-progress')).toHaveText('Votes: 1 of 4');

  await page.reload();
  await expect(page.locator('#vote-voter-name')).toHaveText('Bob');
  await expect(page.locator('#vote-progress')).toHaveText('Votes: 1 of 4');

  // Quitting always returns to setup.
  await page.locator('#btn-abandon').click();
  await expect(page.locator('#view-setup')).toBeVisible();
});
