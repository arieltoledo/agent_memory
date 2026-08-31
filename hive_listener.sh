#!/usr/bin/env bash
# CodeHive listener for this repository. Run with: ./hive_listener.sh &
set -euo pipefail

project_id="memory-project"
listener=".agents/skills/codehive-protocol/listener.js"
runtime_dir=".codehive/runtime"
log_file="${runtime_dir}/listener.log"
latest_file="${runtime_dir}/latest-message.txt"

mkdir -p "${runtime_dir}"

while true; do
  message="$(PROJECT_ID="${project_id}" node "${listener}" 2>&1 || true)"

  if [[ -n "${message}" ]]; then
    printf '%s\n' "${message}" | tee -a "${log_file}" > "${latest_file}"
  fi

  sleep 1
done
