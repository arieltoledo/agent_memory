# CodeHive Protocol

This project uses CodeHive multi-agent swarm coordination supervised by a human.

The complete instructions are in `.agents/skills/codehive-protocol/SKILL.md`.

MCP server: `npx tsx /home/arieltoledo/Development/codehive/mcp/server.ts`

The coordination loop is mandatory: read the coordination room, execute orders, send updates, read recovery messages, then wait using the strategy for your platform.