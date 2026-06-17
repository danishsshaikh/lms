#!/usr/bin/env bash
set -euo pipefail

SITE="${SITE:-lms.localhost}"
SERVICE="${SERVICE:-frappe}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_PATH="/home/frappe/frappe-bench/apps/lms"
BENCH_PATH="/home/frappe/frappe-bench"

cd "${SCRIPT_DIR}"

log() {
	printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

run_in_frappe() {
	docker compose exec "${SERVICE}" bash -lc "$*"
}

run_in_frappe_as_root() {
	docker compose exec --user root "${SERVICE}" bash -lc "$*"
}

log "Starting Docker services"
docker compose up -d

CONTAINER_ID="$(docker compose ps -q "${SERVICE}")"
if [[ -z "${CONTAINER_ID}" ]]; then
	echo "Could not find running container for service '${SERVICE}'." >&2
	exit 1
fi

log "Copying LMS frontend into container"
docker cp "${PROJECT_ROOT}/frontend/." "${CONTAINER_ID}:${APP_PATH}/frontend/"

log "Copying LMS Python app into container"
docker cp "${PROJECT_ROOT}/lms/." "${CONTAINER_ID}:${APP_PATH}/lms/"

log "Fixing ownership"
run_in_frappe_as_root "chown -R frappe:frappe '${APP_PATH}'"
run_in_frappe_as_root "mkdir -p '${BENCH_PATH}/sites/assets/lms' && chown -R frappe:frappe '${BENCH_PATH}/sites/assets/lms'"

log "Installing frontend dependencies"
run_in_frappe "cd '${APP_PATH}/frontend' && yarn install"

log "Building LMS assets"
run_in_frappe "cd '${BENCH_PATH}' && bench build --app lms"

log "Migrating site ${SITE}"
run_in_frappe "cd '${BENCH_PATH}' && bench --site '${SITE}' migrate"

log "Clearing site cache"
run_in_frappe "cd '${BENCH_PATH}' && bench --site '${SITE}' clear-cache"

log "Restarting Frappe service"
docker compose restart "${SERVICE}"

log "Current containers"
docker ps

log "Done. Open the LMS and hard-refresh the browser if old frontend assets are cached."
