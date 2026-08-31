#!/bin/bash
# Hive listener - monitors chat and responds as opencode-agent

PROJECT_ID="memory_project"
AGENT_ID="opencode-agent"
ROOM_ID="project_main"
LAST_MSG_FILE="/tmp/hive_last_msg_$$"

echo "Starting hive listener for $AGENT_ID..."

while true; do
    # Read latest messages
    RESPONSE=$(curl -s -X POST "http://localhost:3000/api/chat/read" \
        -H "Content-Type: application/json" \
        -d "{\"projectId\":\"$PROJECT_ID\",\"room_id\":\"$ROOM_ID\",\"limit\":10}")
    
    # Extract messages (simplified - in reality would parse JSON)
    # For now, just sleep and check
    sleep 2
done