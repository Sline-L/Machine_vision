#!/usr/bin/env bash
# One-shot EdgeMedic Agent launcher for isolated P0 demos.
# Does NOT touch production systemd units or :8787.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${EDGEMEDIC_ENV_FILE:-$ROOT/deploy/edgemedic-agent.env}"
PID_FILE="${EDGEMEDIC_PIDFILE:-${EDGEMEDIC_PID_FILE:-/tmp/edgemedic-agent.pid}}"
PY="${EDGEMEDIC_PYTHON:-$ROOT/.venv/bin/python}"

if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export EDGEMEDIC_CONTROL_URL="${EDGEMEDIC_CONTROL_URL:-http://127.0.0.1:8788}"
export EDGEMEDIC_LLM_URL="${EDGEMEDIC_LLM_URL:-http://127.0.0.1:8080}"
export EDGEMEDIC_TOKEN="${EDGEMEDIC_TOKEN:-dev-token}"
# Default observe_only. Isolation demos may export execute_replay explicitly.
export EDGEMEDIC_EXECUTION_MODE="${EDGEMEDIC_EXECUTION_MODE:-${EDGEMEDIC_MODE:-observe_only}}"
export EDGEMEDIC_STATUS_HOST="${EDGEMEDIC_STATUS_HOST:-127.0.0.1}"
export EDGEMEDIC_STATUS_PORT="${EDGEMEDIC_STATUS_PORT:-8790}"
export EDGEMEDIC_PIDFILE="$PID_FILE"
export EDGEMEDIC_PID_FILE="$PID_FILE"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"

if [[ "$EDGEMEDIC_EXECUTION_MODE" == "execute_replay" && "$EDGEMEDIC_CONTROL_URL" == *":8787"* ]]; then
  echo "refusing execute_replay against :8787" >&2
  exit 2
fi

if [[ -f "$PID_FILE" ]]; then
  old="$(cat "$PID_FILE" || true)"
  if [[ -n "${old}" ]] && kill -0 "$old" 2>/dev/null; then
    echo "EdgeMedic Agent already running (pid=$old). Refusing duplicate start."
    exit 1
  fi
  rm -f "$PID_FILE"
fi

cd "$ROOT"
echo "Starting EdgeMedic Agent"
echo "  control=$EDGEMEDIC_CONTROL_URL mode=$EDGEMEDIC_EXECUTION_MODE status=:${EDGEMEDIC_STATUS_PORT} pidfile=$PID_FILE"
exec "$PY" -m edgemedic.service \
  --control-url "$EDGEMEDIC_CONTROL_URL" \
  --llm-url "$EDGEMEDIC_LLM_URL" \
  --status-host "$EDGEMEDIC_STATUS_HOST" \
  --status-port "$EDGEMEDIC_STATUS_PORT" \
  --execution-mode "$EDGEMEDIC_EXECUTION_MODE" \
  --pidfile "$PID_FILE" \
  --auto-monitor
