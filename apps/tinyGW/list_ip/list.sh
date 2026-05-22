#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: bash list.sh setting.conf"
  echo
  echo "Required config keys:"
  echo "  USER_ID=admin"
  echo "  USER_PW='password'"
  echo
  echo "Optional config keys:"
  echo "  ROUTER_IP=10.0.0.1"
  echo "  COOKIE_FILE=/tmp/iptime_cookie.txt"
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

SETTING_FILE="$1"
if [[ ! -f "${SETTING_FILE}" ]]; then
  echo "Config file not found: ${SETTING_FILE}" >&2
  exit 2
fi

while IFS='=' read -r key value; do
  key="${key#"${key%%[![:space:]]*}"}"
  key="${key%"${key##*[![:space:]]}"}"

  [[ -z "${key}" || "${key}" == \#* ]] && continue
  [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
    echo "Invalid config key: ${key}" >&2
    exit 2
  }

  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi

  case "${key}" in
    ROUTER_IP|USER_ID|USER_PW|COOKIE_FILE)
      printf -v "${key}" '%s' "${value}"
      ;;
    *)
      echo "Unknown config key: ${key}" >&2
      exit 2
      ;;
  esac
done < "${SETTING_FILE}"

ROUTER_IP="${ROUTER_IP:-10.0.0.1}"
: "${USER_ID:?USER_ID is required in ${SETTING_FILE}}"
: "${USER_PW:?USER_PW is required in ${SETTING_FILE}}"

COOKIE_FILE="${COOKIE_FILE:-/tmp/iptime_cookie.txt}"
BASE_URL="http://${ROUTER_IP}"
API_URL="${BASE_URL}/cgi/service.cgi"

cleanup() {
  rm -f "${COOKIE_FILE}"
}
trap cleanup EXIT

api_call() {
  local payload="$1"

  curl -s \
    -b "${COOKIE_FILE}" \
    -c "${COOKIE_FILE}" \
    -H "Content-Type: application/json; charset=utf-8" \
    -H "Cache-Control: no-store" \
    -H "Origin: ${BASE_URL}" \
    -H "Referer: ${BASE_URL}/ui/" \
    -H "X-Requested-With: XMLHttpRequest" \
    -A "Mozilla/5.0" \
    --data "${payload}" \
    "${API_URL}"
}

json_value() {
  local key="$1"
  sed -n "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
}

rm -f "${COOKIE_FILE}"

login_payload=$(printf '{"method":"session/login","params":{"id":"%s","pw":"%s"}}' "${USER_ID}" "${USER_PW}")
login_response=$(api_call "${login_payload}")

if ! grep -q '"result"[[:space:]]*:[[:space:]]*"done"' <<< "${login_response}"; then
  echo "Login failed"
  echo "${login_response}"
  exit 1
fi

session_response=$(api_call '{"method":"session/info"}')
session_level=$(printf '%s\n' "${session_response}" | json_value "level")

if [[ "${session_level}" != "auth" ]]; then
  echo "Session auth check failed"
  echo "${session_response}"
  exit 1
fi

stations_response=$(api_call '{"method":"network/interface/lan/stations"}')

STATIONS_RESPONSE="${stations_response}" python3 - <<'PY'
import ipaddress
import json
import os
import sys


def ip_sort_key(value):
    try:
        return (0, int(ipaddress.ip_address(value)))
    except ValueError:
        return (1, value)


data = json.loads(os.environ["STATIONS_RESPONSE"])
if data.get("error"):
    print("Failed to load station list")
    print(json.dumps(data["error"], ensure_ascii=False))
    sys.exit(1)

stations = data.get("result") or []
rows = []
for station in stations:
    info = station.get("info") or {}
    connection = station.get("connection") or {}
    ip = (info.get("ip") or "").strip()
    if not ip:
        continue
    rows.append(
        {
            "ip": ip,
            "name": info.get("name") or "-",
            "mac": station.get("mac") or "-",
            "type": connection.get("type") or "-",
        }
    )

rows.sort(key=lambda row: ip_sort_key(row["ip"]))

print(f"{'IP':<15} {'NAME':<28} {'MAC':<17} TYPE")
print(f"{'-' * 15} {'-' * 28} {'-' * 17} {'-' * 8}")
for row in rows:
    print(f"{row['ip']:<15} {row['name'][:28]:<28} {row['mac']:<17} {row['type']}")
print()
print(f"Total devices with IP: {len(rows)}")
PY
