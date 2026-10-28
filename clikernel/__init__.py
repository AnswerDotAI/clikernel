"""Serve persistent Jupyter kernels to LLMs as concise text, over MCP or a plain stream protocol

Modules:

- `clikernel.cli`: The stream-protocol frontend: the service on stdin/stdout for token-reading clients
- `clikernel.core`: Gateway naming, startup delivery, and MCP sessions on rustygate gateways
- `clikernel.mcp`: Route stdio MCP requests to rustygate gateways
- `clikernel.skill`: Use `clikernel` MCP as the default persistent Python workspace for file/notebook reads and edits, exploration, library checks, data reshaping and debugging. Imports and variables carry across calls. Read before writing, running or debugging Python with `clikernel` connected.
- `clikernel.stream`: Streaming JSON-lines worker protocol: nbformat-shaped output events, and a supervisor for select-based UIs."""

__version__ = "0.2.17"
