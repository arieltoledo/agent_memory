#!/usr/bin/env bash
# Coder 3 — CodeHive background listener for memory-project.
# Listens to the coordination room and surfaces incoming messages so the
# agent (coder3-verification) can process orders.
#
# Run in background from repo root:
#   nohup ./coder3_hive_listener.sh >/tmp/coder3-hive-listener.log 2>&1 &
#
# Talks to the CodeHive MCP server directly over stdio. Because a bash loop
# cannot call MCP tools natively, it wraps the official listener.js (WebSocket)
# and records every message; the agent reads the room via codehive_chat_read
# and answers via codehive_chat_send with its own intelligence.
set -uo pipefail

project_id="memory-project"
listener=".agents/skills/codehive-protocol/listener.js"
runtime_dir=".codehive/runtime/coder3"
log_file="${runtime_dir}/listener.log"
latest_file="${runtime_dir}/latest-message.txt"

mkdir -p "${runtime_dir}"

echo "[coder3-listener] started at $(date -u +%FT%TZ)" >> "${log_file}"

while true; do
  message="$(PROJECT_ID="${project_id}" node "${listener}" 2>&1 || true)"

  if [[ -n "${message}" ]]; then
    printf '[%s] %s\n' "$(date -u +%FT%TZ)" "${message}" | tee -a "${log_file}" > "${latest_file}"
    # Ping a sentinel so the agent can detect activity timestamp cheaply.
    date -u +%FT%TZ > "${runtime_dir}/last-activity.txt"
  fi

  sleep 1
done
