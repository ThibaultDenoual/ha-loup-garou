import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const python = process.env.PYTHON || (
  existsSync(resolve('.venv/bin/python')) ? '.venv/bin/python' : 'python3'
);

export default defineConfig({
  testDir: './tests/ui',
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 12_000 },
  reporter: 'list',
  outputDir: 'test-results/ui',
  use: {
    baseURL: 'http://127.0.0.1:8119',
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `${python} run_devserver.py --port 8119 --language en`,
    url: 'http://127.0.0.1:8119/loup_garou/game/index.html',
    reuseExistingServer: false,
    timeout: 30_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
