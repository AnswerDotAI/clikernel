"""Serve persistent Jupyter kernels to LLMs as concise text, over MCP or a plain stream protocol

Modules:

- `clikernel.cli`: The stream-protocol frontend: the service on stdin/stdout for token-reading clients
- `clikernel.core`: Connect to gateway-hosted kernels and turn execution into concise text
- `clikernel.mcp`: The MCP frontend: `Client` as tools on stdio
- `clikernel.skill`: Use the persistent `clikernel` MCP session as the default workspace for any task advanced through live Python execution -- stateful inspection, file-editing workflows, debugging, experiments, API probes, data transforms, or notebook-style work. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.
- `clikernel.stream`: Streaming JSON-lines worker protocol: nbformat-shaped output events, and a supervisor for select-based UIs."""

__version__ = "0.2.4"
