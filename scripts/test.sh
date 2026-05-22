#!/usr/bin/env bash
# scripts/test.sh
# Run the test suite, mirroring .github/workflows/tests.yml exactly.
#
# Flags:
#   (none)              Full suite with coverage — same as CI
#   --fast              Skip coverage (faster feedback during development)
#   --file <path>       Run a single test file
#   --watch             Re-run on file changes (requires pytest-watch)
#   -k <expression>     Filter tests by name (passed through to pytest)
#   -v / --verbose      Verbose pytest output
#   -x                  Stop on first failure
#
# Examples:
#   ./scripts/test.sh
#   ./scripts/test.sh --fast
#   ./scripts/test.sh --file tests/test_game_engine.py
#   ./scripts/test.sh --fast -k "TestWinCondition"
#   ./scripts/test.sh -x -v

set -euo pipefail

# ── Colours ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log()  { echo -e "${CYAN}▶ $*${RESET}"; }
ok()   { echo -e "${GREEN}✔ $*${RESET}"; }
warn() { echo -e "${YELLOW}⚠ $*${RESET}"; }
die()  { echo -e "${RED}✘ $*${RESET}" >&2; exit 1; }

# ── Arg parsing ─────────────────────────────────────────────────────────────
FAST=false
WATCH=false
TEST_FILE=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast)    FAST=true;          shift ;;
    --watch)   WATCH=true;         shift ;;
    --file)    TEST_FILE="$2";     shift 2 ;;
    *)         EXTRA_ARGS+=("$1"); shift ;;
  esac
done

# ── Environment ──────────────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Activate venv if it exists and we're not already inside one
if [[ -z "${VIRTUAL_ENV:-}" && -f ".venv/bin/activate" ]]; then
  log "Activating virtual environment …"
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

# Sanity check
if ! command -v pytest &>/dev/null; then
  die "pytest not found. Run ./scripts/setup.sh first."
fi

# ── Build pytest command ─────────────────────────────────────────────────────
PYTEST_ARGS=()

# Target: single file or full suite
if [[ -n "$TEST_FILE" ]]; then
  log "Running single file: ${BOLD}$TEST_FILE${RESET}"
  PYTEST_ARGS+=("$TEST_FILE")
else
  PYTEST_ARGS+=("tests/")
fi

# Coverage: full CI mode vs fast mode
if [[ "$FAST" == true ]]; then
  warn "Fast mode — coverage disabled."
else
  PYTEST_ARGS+=(
    "--cov=custom_components/loup_garou"
    "--cov-report=term-missing"
    "--cov-report=html:htmlcov"
    "--cov-fail-under=75"
  )
fi

# Pass through any extra args (-v, -x, -k, etc.)
PYTEST_ARGS+=("${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}")

# ── Run ──────────────────────────────────────────────────────────────────────
if [[ "$WATCH" == true ]]; then
  if ! command -v ptw &>/dev/null; then
    die "pytest-watch not installed. Run: pip install pytest-watch"
  fi
  log "Watching for changes …"
  ptw -- "${PYTEST_ARGS[@]}"
else
  log "Running: pytest ${PYTEST_ARGS[*]}"
  echo ""

  if PYTHONPATH="$ROOT" pytest "${PYTEST_ARGS[@]}"; then
    echo ""
    ok "All tests passed."
    if [[ "$FAST" == false && -d "htmlcov" ]]; then
      echo -e "   Coverage report: ${CYAN}htmlcov/index.html${RESET}"
    fi
  else
    echo ""
    die "Tests failed."
  fi
fi