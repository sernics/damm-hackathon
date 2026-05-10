#!/usr/bin/env bash
# Stop the three Damm Smart Truck services by port.

set -u

stop_port() {
  local name="$1" port="$2"
  local pids
  pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    echo "  [skip] ${name} :${port} not running"
    return
  fi
  echo "  [kill] ${name} :${port} (pids: ${pids})"
  kill ${pids} 2>/dev/null || true
  sleep 0.5
  pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    echo "  [force] ${name} :${port} still up, sending SIGKILL"
    kill -9 ${pids} 2>/dev/null || true
  fi
}

echo "Damm Smart Truck — stopping stack"
echo "------------------------------------"
stop_port "warehouse 3D"   8000
stop_port "veteran-capture" 8001
stop_port "driver-briefing" 8080
echo "------------------------------------"
echo "Done."
