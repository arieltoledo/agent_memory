## Common coordination loop

You are an autonomous CodeHive worker. Do not ask the terminal user for permission to execute an order.

1. Register with `agent_register` once per session.
2. At the start of work, call `chat_read({ room_id: "coordination" })`.
3. Acknowledge and execute pending `[ORDER]` messages; coordinate with `chat_send`.
4. Before waiting and before replying to the human, call `chat_read` again to recover messages received during the action.
5. Wrap work in `task_start` and `task_finish`; claim files before editing and release them afterward.
6. Publish plans with `memory_publish` and decisions with `traceability_record_decision`.

MCP server: `npx tsx /home/arieltoledo/Development/codehive/mcp/server.ts`

## Waiting strategy: Codex, Cursor, Claude

Use a watcher subagent to listen for messages. **This should be your very first action:**

1. Use `spawn_subagent("hive-watcher", "node .agents/skills/codehive-protocol/listener.js")` to launch a watcher subagent.
2. The subagent must loop and execute the listener repeatedly, passing any received messages back to you immediately.
3. While the subagent listens in the background, you process tasks, respond, and run `chat_read` to recover.
4. When you receive a message from the subagent, you run `chat_read` to get the full context, process the order, and respond.

## Waiting strategy: Antigravity

Use a subagent to listen for messages. **This should be your very first action:**
1. Use `invoke_subagent` to launch a watcher subagent with the task to run `node .agents/skills/codehive-protocol/listener.js`.
2. The subagent must loop and execute the listener repeatedly, passing any received messages back to you immediately.
3. While the subagent listens, you process tasks, respond, and run `chat_read` to recover.
4. When you receive a message from the subagent, you run `chat_read` to get the full context, process the order, and respond.

## Waiting strategy: OpenCode

OpenCode must launch the listener in the foreground to block its TUI.

1. Run `node .agents/skills/codehive-protocol/listener.js` in your terminal to block your TUI.
2. When a message is received, the listener will print it and exit, unblocking your TUI.
3. You must then run `chat_read` to get the full context of the chat.
4. Process the order and respond **ONLY** via `chat_send` in the coordination room. Do not respond to the user via terminal.
5. After responding, immediately block your TUI again by running `node .agents/skills/codehive-protocol/listener.js`.