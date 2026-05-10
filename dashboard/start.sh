#!/usr/bin/env bash
# Start the three Damm Smart Truck services and open the dashboard.
# Re-runnable: skips any service whose port is already bound.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${REPO_ROOT}/dashboard/logs"
mkdir -p "${LOG_DIR}"

# Load .env so subprocess shells (briefing in particular) see the secrets.
# Briefing uses os.environ directly and does not parse .env on its own.
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
  echo "  [env] loaded ${REPO_ROOT}/.env"
fi

VETERAN_PORT=8001
BRIEFING_PORT=8080
WAREHOUSE_PORT=8000

PIDS=()

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

start_service() {
  local name="$1" port="$2" cmd="$3" logfile="$4" cwd="$5"
  if port_in_use "${port}"; then
    echo "  [skip] ${name} already listening on :${port}"
    return
  fi
  echo "  [start] ${name} on :${port}  (log: ${logfile})"
  ( cd "${cwd}" && eval "${cmd}" ) >"${logfile}" 2>&1 &
  PIDS+=("$!")
}

echo "Damm Smart Truck — launching stack"
echo "------------------------------------"

# Warehouse 3D — static HTTP server (no env, no deps beyond python3)
start_service "warehouse 3D" "${WAREHOUSE_PORT}" \
  "python3 -m http.server ${WAREHOUSE_PORT} --bind 127.0.0.1" \
  "${LOG_DIR}/warehouse.log" \
  "${REPO_ROOT}/app/frontend"

# Veteran Capture — call its venv python directly (avoids needing uv on PATH)
VETERAN_PY="${REPO_ROOT}/veteran-capture/.venv/bin/python"
if [[ ! -x "${VETERAN_PY}" ]]; then
  echo "  [error] veteran-capture venv not found at ${VETERAN_PY}"
else
  start_service "veteran-capture" "${VETERAN_PORT}" \
    "'${VETERAN_PY}' -m veteran_capture.cli serve" \
    "${LOG_DIR}/veteran.log" \
    "${REPO_ROOT}/veteran-capture"
fi

# Driver Briefing — needs ANTHROPIC_API_KEY
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "  [warn] ANTHROPIC_API_KEY not set — briefing will refuse generation"
fi
BRIEFING_PY="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${BRIEFING_PY}" ]]; then
  echo "  [error] briefing venv not found at ${BRIEFING_PY}"
else
  start_service "driver-briefing" "${BRIEFING_PORT}" \
    "'${BRIEFING_PY}' main.py" \
    "${LOG_DIR}/briefing.log" \
    "${REPO_ROOT}"
fi

echo "------------------------------------"
echo "Waiting for services to come up..."
sleep 2

for port in "${WAREHOUSE_PORT}" "${VETERAN_PORT}" "${BRIEFING_PORT}"; do
  if port_in_use "${port}"; then
    echo "  [ok]   :${port}"
  else
    echo "  [down] :${port} — check ${LOG_DIR}"
  fi
done

DASHBOARD="${REPO_ROOT}/dashboard/index.html"
echo ""
echo "Opening dashboard: ${DASHBOARD}"
open "${DASHBOARD}"

echo ""
echo "Stack is running in background."
echo "  logs:  ${LOG_DIR}"
echo "  stop:  ${REPO_ROOT}/dashboard/stop.sh"
