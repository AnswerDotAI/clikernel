"""Serve persistent Jupyter kernels to LLMs as concise text, over MCP or a plain stream protocol

Modules:

- `clikernel.cli`: The stream-protocol frontend: the service on stdin/stdout for token-reading clients
- `clikernel.core`: Connect to gateway-hosted kernels and turn execution into concise text
- `clikernel.mcp`: The MCP frontend: `Client` as tools on stdio
- `clikernel.skill`: Use the `clikernel` MCP session as the default workspace for Python work: reading and changing files, notebook work, trying things out, checking how a library behaves, and reshaping data. One session stays open, so imports and variables carry between calls. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.
- `clikernel.stream`: Streaming JSON-lines worker protocol: nbformat-shaped output events, and a supervisor for select-based UIs."""

__version__ = "0.2.7"
