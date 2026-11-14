#!/usr/bin/env bash
# Local container deployment rehearsal (ASAA-010): migrate -> deploy -> smoke -> bad release -> rollback -> smoke.
# Requires a running Docker daemon with Compose v2, python3 (with cryptography and PyJWT, e.g. the API venv) and curl.
# Everything is local and throw-away (tmpfs database, generated keys). It deploys nowhere.
#
#   bash deploy/rehearsal.sh            # writes deploy/rehearsal-result.json
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${REHEARSAL_PYTHON:-python3}"
COMPOSE=(docker compose -f deploy/docker-compose.yml)
RESULT=deploy/rehearsal-result.json
STEPS=()
record() { STEPS+=("{\"step\":\"$1\",\"ok\":$2,\"detail\":\"$3\"}"); echo "[$( [ "$2" = true ] && echo PASS || echo FAIL )] $1 - $3"; }
finish() {
  local code=$?
  rm -f "${TOKEN_FILE:-}"
  "${COMPOSE[@]}" --profile migrate down -v --remove-orphans >/dev/null 2>&1 || true
  printf '{"completed":%s,"steps":[%s]}\n' "$([ $code -eq 0 ] && echo true || echo false)" "$(IFS=,; echo "${STEPS[*]:-}")" > "$RESULT"
  exit $code
}
trap finish EXIT

docker info >/dev/null 2>&1 || { echo "Docker daemon is not running; rehearsal cannot run." >&2; exit 3; }

CREDS="$($PY deploy/rehearsal_credentials.py)"
export ASAA_AP_JWT_PUBLIC_KEY="$($PY -c 'import json,sys;print(json.loads(sys.argv[1])["public_key"])' "$CREDS")"
TOKEN="$($PY -c 'import json,sys;print(json.loads(sys.argv[1])["token"])' "$CREDS")"
TOKEN_FILE="$(mktemp)"; printf '%s' "$TOKEN" > "$TOKEN_FILE"

smoke() { $PY apps/ap-api/scripts/smoke_test.py --base-url http://127.0.0.1:8000 --token-file "$TOKEN_FILE" --expect-production; }
wait_ready() { for _ in $(seq 1 40); do curl -fsS http://127.0.0.1:8000/ready >/dev/null 2>&1 && return 0; sleep 2; done; return 1; }
supplier_count() { curl -fsS -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/v1/ap/suppliers?limit=100" | $PY -c 'import json,sys;print(len(json.load(sys.stdin)))'; }

# 1. build release 1 (good) and release 2 (deliberately broken)
docker build -q -t asaa-api:rehearsal-1 apps/ap-api >/dev/null && record build-release-1 true "asaa-api:rehearsal-1"
docker build -q -t asaa-api:rehearsal-2 --build-arg BAD_RELEASE=1 apps/ap-api >/dev/null && record build-bad-release-2 true "asaa-api:rehearsal-2 (import-time failure)"
docker build -q -f Dockerfile.portal -t asaa-portal:rehearsal-1 . >/dev/null && record build-portal true "asaa-portal:rehearsal-1"

# 2. migrate with release 1, then deploy it
export API_IMAGE_TAG=rehearsal-1
"${COMPOSE[@]}" up -d postgres >/dev/null
"${COMPOSE[@]}" --profile migrate run --rm migrate >/dev/null && record migrate true "alembic upgrade head"
REV_BEFORE="$("${COMPOSE[@]}" exec -T postgres psql -U asaa -d asaa_ap -tAc 'select version_num from alembic_version')"
"${COMPOSE[@]}" up -d api portal >/dev/null
wait_ready && record deploy-release-1 true "ready" || { record deploy-release-1 false "api not ready"; exit 1; }
smoke >/dev/null && record smoke-release-1 true "all smoke checks passed" || { record smoke-release-1 false "smoke failed"; exit 1; }
curl -fsS -o /dev/null http://127.0.0.1:8080/ && record portal-serves true "static portal reachable"
curl -fsS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"legal_name":"Rehearsal Supplier"}' \
  http://127.0.0.1:8000/api/v1/ap/suppliers >/dev/null && record write-before-release-2 true "supplier created"
COUNT_BEFORE="$(supplier_count)"

# 3. simulated bad release: release 2 must fail the smoke test
export API_IMAGE_TAG=rehearsal-2
"${COMPOSE[@]}" up -d api >/dev/null
sleep 8
if smoke >/dev/null 2>&1; then record bad-release-detected false "smoke unexpectedly passed on the broken release"; exit 1; fi
record bad-release-detected true "smoke test failed on release 2 as expected"

# 4. rollback to the previous image tag, smoke again, prove data and schema are intact
export API_IMAGE_TAG=rehearsal-1
"${COMPOSE[@]}" up -d api >/dev/null
wait_ready && record rollback-ready true "release 1 restored" || { record rollback-ready false "api not ready after rollback"; exit 1; }
smoke >/dev/null && record smoke-after-rollback true "all smoke checks passed" || { record smoke-after-rollback false "smoke failed after rollback"; exit 1; }
COUNT_AFTER="$(supplier_count)"
[ "$COUNT_BEFORE" = "$COUNT_AFTER" ] && record data-intact true "supplier count $COUNT_AFTER" || { record data-intact false "$COUNT_BEFORE -> $COUNT_AFTER"; exit 1; }
REV_AFTER="$("${COMPOSE[@]}" exec -T postgres psql -U asaa -d asaa_ap -tAc 'select version_num from alembic_version')"
[ "$REV_BEFORE" = "$REV_AFTER" ] && record schema-revision-unchanged true "$REV_AFTER" || { record schema-revision-unchanged false "$REV_BEFORE -> $REV_AFTER"; exit 1; }
echo "Rehearsal completed: migrate -> smoke -> bad release -> rollback -> smoke."
