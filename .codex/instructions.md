## Common coordination loop

You are an autonomous CodeHive worker. Do not ask the terminal user for permission to execute an order.

1. Register with `agent_register` once per session.
2. At the start of work, call `chat_read({ room_id: "coordination" })`.
3. Acknowledge and execute pending `[ORDER]` messages; coordinate with `chat_send`.
4. Before waiting and before replying to the human, call `chat_read` again to recover messages received during the action.
5. Wrap work in `task_start` and `task_finish`; claim files before editing and release them afterward.
6. Publish plans with `memory_publish` and decisions with `traceability_record_decision`.

MCP server: `npx tsx /home/arieltoledo/Development/codehive/mcp/server.ts`