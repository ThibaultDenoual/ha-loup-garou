# Browser UI tests

This is an on-demand Playwright suite; it is intentionally not part of the default
pytest or CI run. It starts a private standalone dev server on port `8119`, drives
the launcher and a complete five-player game, and writes mobile screenshots to
`screenshots/automated/`.

```bash
npm ci
npx playwright install chromium
npm run test:ui
```

The Python environment used for `run_devserver.py` defaults to `.venv/bin/python`.
Set `PYTHON` to another interpreter if needed. The suite uses a 390×844 CSS-pixel
viewport at 2× device scale. The server is shut down by Playwright after the run.
