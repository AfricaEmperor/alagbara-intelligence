#!/usr/bin/env bash
# AP-001 Cotonou Event Radar: one launcher for the local artefact.
#   scripts/ap001.sh setup      create venv, install, build PULSE, check OCR
#   scripts/ap001.sh up         start identity (local demo), operator console, PULSE        -> prints URLs and the launch key
#   scripts/ap001.sh down       stop everything started by `up`
#   scripts/ap001.sh status     what is running
#   scripts/ap001.sh sample     load the synthetic sample posters through the same pipeline
#   scripts/ap001.sh demo       run the automated acceptance demonstration (starts its own throw-away stack)
#   scripts/ap001.sh test       run ALL regression suites
#   scripts/ap001.sh backup | verify | report | publish
# Nothing here deploys anything, contacts anyone, or touches Supabase unless YOU export SUPABASE_URL/SUPABASE_ANON_KEY.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PULSE_DIR="${PULSE_DIR:-$ROOT/../pulse-l1}"
STATE="${AP001_STATE:-$ROOT/.ap001}"
VENV="$ROOT/.venv"; RADAR="$VENV/bin/radar"
OP_PORT="${AP001_OPERATOR_PORT:-8750}"; PULSE_PORT="${AP001_PULSE_PORT:-3000}"; IDP_PORT="${AP001_IDP_PORT:-54399}"
DATA="$STATE/data"; FEED="$STATE/feed/feed.json"; RUN="$STATE/run"
say() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 2; }; }
alive() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

cmd_setup() {
  need python3; need node; need npm
  [ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -e "$ROOT/scout-intelligence-fabric[dev]"
  if command -v tesseract >/dev/null && tesseract --list-langs 2>/dev/null | grep -q '^fra$'; then say "OCR: Tesseract with French is available"
  else warn "OCR: Tesseract (French) NOT found. Install: apt-get install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng  (without it, posters wait in the evidence inbox for a typed transcription)"; fi
  [ -d "$PULSE_DIR" ] || { echo "PULSE not found at $PULSE_DIR (set PULSE_DIR)" >&2; exit 2; }
  (cd "$PULSE_DIR" && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run -s build >/dev/null)
  say "setup complete"
}

cmd_up() {
  [ -x "$RADAR" ] || cmd_setup
  [ -d "$PULSE_DIR/.next" ] || (cd "$PULSE_DIR" && npm run -s build >/dev/null)
  mkdir -p "$DATA" "$STATE/feed" "$RUN"
  alive operator && { echo "already running (use down first)"; return 0; }
  IDP_URL="${SUPABASE_URL:-}"; IDP_KEY="${SUPABASE_ANON_KEY:-}"
  if [ -z "$IDP_URL" ]; then
    warn "No SUPABASE_URL set: starting the LOCAL DEMO identity provider (a mock). Reviewer sign-in on PULSE: rev@example.test / code 123456. For anything real, export SUPABASE_URL and SUPABASE_ANON_KEY instead."
    ( cd "$PULSE_DIR" && exec nohup node scripts/radar/mock-auth-server.mjs "$IDP_PORT" >"$RUN/idp.log" 2>&1 </dev/null ) & echo $! >"$RUN/idp.pid"
    IDP_URL="http://127.0.0.1:$IDP_PORT"; IDP_KEY="test-anon-key-placeholder"
  fi
  # `exec` inside a redirected subshell: the recorded PID is the service itself and no file descriptor leaks to the caller
  ( exec nohup "$RADAR" --data "$DATA" serve --feed "$FEED" --port "$OP_PORT" --key-file "$RUN/operator.key" --pulse-url "http://127.0.0.1:$PULSE_PORT" >"$RUN/operator.log" 2>&1 </dev/null ) & echo $! >"$RUN/operator.pid"
  ( cd "$PULSE_DIR" && export RADAR_FEED_PATH="$FEED" RADAR_MEDIA_DIR="$DATA/media" RADAR_DECISIONS_DIR="$STATE/decisions" SUPABASE_URL="$IDP_URL" SUPABASE_ANON_KEY="$IDP_KEY" \
      && exec nohup node node_modules/next/dist/bin/next start -p "$PULSE_PORT" >"$RUN/pulse.log" 2>&1 </dev/null ) & echo $! >"$RUN/pulse.pid"
  for i in $(seq 1 60); do curl -fs "http://127.0.0.1:$OP_PORT/health" >/dev/null 2>&1 && curl -s -o /dev/null "http://127.0.0.1:$PULSE_PORT/radar/signin" && break; sleep 0.5; done
  say "Operator console : http://127.0.0.1:$OP_PORT/      (your name + launch key: $(cat "$RUN/operator.key"))"
  say "PULSE Radar      : http://127.0.0.1:$PULSE_PORT/radar   (reviewer sign-in; see note above)"
  say "Data: $DATA   Feed: $FEED   Logs: $RUN/*.log"
}

cmd_down() {
  for n in pulse operator idp; do
    if alive $n; then kill "$(cat "$RUN/$n.pid")" 2>/dev/null || true; pkill -P "$(cat "$RUN/$n.pid")" 2>/dev/null || true; fi
    rm -f "$RUN/$n.pid"
  done; pkill -f "next-server" 2>/dev/null || true; rm -f "$RUN/operator.key"; say "stopped"
}

cmd_status() { for n in idp operator pulse; do if alive $n; then echo "$n: running (pid $(cat "$RUN/$n.pid"))"; else echo "$n: stopped"; fi; done; [ -x "$RADAR" ] && "$RADAR" --data "$DATA" verify | head -12 || true; }
cmd_sample() {
  [ -x "$RADAR" ] || cmd_setup; mkdir -p "$DATA"
  "$RADAR" --data "$DATA" register-source sample-uploads upload "Synthetic sample posters" >/dev/null
  "$RADAR" --data "$DATA" approve-source sample-uploads --by sample-loader >/dev/null
  "$RADAR" --data "$DATA" ingest-manifest "$ROOT/sample-data/manifest.csv" --root "$ROOT/sample-data/posters" --report "$STATE/sample-report.csv"
  say "report: $STATE/sample-report.csv  (open the operator console to review the three events)"
}
cmd_backup() { "$RADAR" --data "$DATA" backup --out "$STATE/backups/backup-$(date -u +%Y%m%dT%H%M%S)"; }
cmd_verify() { "$RADAR" --data "$DATA" verify; }
cmd_report() { "$RADAR" --data "$DATA" report; }
cmd_publish() { mkdir -p "$STATE/feed"; "$RADAR" --data "$DATA" export-feed --approved-only --output "$FEED"; say "published to $FEED"; }
cmd_demo() { [ -x "$RADAR" ] || cmd_setup; (cd "$PULSE_DIR" && RADAR_CLI="$RADAR" SAMPLE_DIR="$ROOT/sample-data/posters" DEMO_OUT="${DEMO_OUT:-$ROOT/docs/ap-001/demo}" NODE_PATH="$(npm root -g)" node scripts/radar/demo.mjs); }
cmd_test() {
  [ -x "$RADAR" ] || cmd_setup
  say "== Python (SCOUT, ANA, operator console, ops, PostgreSQL parity)"; (cd "$ROOT/scout-intelligence-fabric" && "$VENV/bin/pytest" -q)
  if command -v psql >/dev/null && [ "$(id -u)" = 0 ]; then say "== PostgreSQL migration suite + mutation check (disposable local database)"; "$ROOT/supabase/tests/run_local_pg.sh" | tail -2; "$ROOT/supabase/tests/mutation_check.py" | tail -1
  else warn "skipping PostgreSQL suites (need local psql and root)"; fi
  cd "$PULSE_DIR"; say "== PULSE: install, typecheck, build, audit"; npm ci --no-audit --no-fund >/dev/null; npm run -s typecheck; npm run -s build >/dev/null; npm audit | tail -1
  say "== PULSE: access matrix"; npm run -s test:radar-access | tail -1
  say "== PULSE: cross-repo end-to-end"; RADAR_CLI="$RADAR" npm run -s test:radar-e2e | tail -1
  say "== PULSE: UI (real browser)"; NODE_PATH="$(npm root -g)" npm run -s test:radar-ui | tail -1
  say "== PULSE: environment / secret boundary"; npm run -s test:radar-env | tail -1
}
case "${1:-}" in setup) cmd_setup;; up) cmd_up;; down) cmd_down;; status) cmd_status;; sample) cmd_sample;; demo) cmd_demo;; test) cmd_test;; backup) cmd_backup;; verify) cmd_verify;; report) cmd_report;; publish) cmd_publish;;
  *) sed -n '2,13p' "$0"; exit 1;; esac
