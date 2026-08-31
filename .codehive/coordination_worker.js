#!/usr/bin/env node
// Durable coordination listener: acknowledge, persist event details, reconnect.
const projectId = process.env.PROJECT_ID || "memory-project";
const roomId = process.env.ROOM_ID || "coordination";
const agentId = process.env.AGENT_ID || "codex-memory-worker";
const apiUrl = process.env.CODEHIVE_API_URL || "http://127.0.0.1:3000";
const wsUrl = apiUrl.replace(/^http/, "ws") + `/ws?roomId=${roomId}::${projectId}`;

async function readRoom() {
  const url = new URL(`${apiUrl}/api/projects/${projectId}/messages`);
  url.searchParams.set("room_id", roomId);
  url.searchParams.set("limit", "50");
  const response = await fetch(url);
  if (!response.ok) throw new Error(`chat recovery failed: ${response.status}`);
  return response.json();
}

async function acknowledge(message) {
  if (message.sender_id === agentId || message.sender_type !== "human") return;
  await fetch(`${apiUrl}/api/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      projectId,
      room_id: roomId,
      sender_id: agentId,
      message_type: "status",
      message: `[RECEIVED] ${message.sender_id}: mensaje recibido; el worker lo procesará por coordinación.`,
    }),
  });
}

function listen() {
  const ws = new WebSocket(wsUrl);
  ws.onmessage = async ({ data }) => {
    try {
      const event = JSON.parse(data);
      if (event.type !== "message_sent" || !event.payload?.message) return;
      const snapshot = await readRoom();
      console.log(JSON.stringify({ event: event.payload, messages: snapshot.messages }));
      await acknowledge(event.payload);
    } finally {
      ws.close();
    }
  };
  ws.onclose = () => setTimeout(listen, 500);
  ws.onerror = () => {};
}

listen();
