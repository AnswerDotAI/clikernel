"""Serve persistent Jupyter kernels to LLMs as concise text, over MCP or a plain stream protocol

`clikernel` gives LLM agents persistent kernel sessions over MCP or a plain stream protocol. Imports, variables, and results remain available between calls. Agents can create kernels or attach to existing ones, including a user's live solveit kernel.

[jupygate](https://github.com/AnswerDotAI/jupygate) hosts the kernels. Clikernel routes requests to local or named remote gateways and supplies startup code to Python kernels.

New kernels close with their creating conversation by default. Attaching to an existing kernel does not claim ownership. Use `autoclose=false` on a persistent gateway to keep a new kernel for later conversations. See [core](https://AnswerDotAI.github.io/clikernel/core.html) for configuration and lifecycle details.

Modules:

- `clikernel.cli`: The stream-protocol frontend: the service on stdin/stdout for token-reading clients
- `clikernel.core`: Gateway naming, startup delivery, and MCP sessions on jupygate gateways
- `clikernel.mcp`: Route stdio MCP requests to jupygate gateways
- `clikernel.rules`: Static AST checks that catch common agent kernel mistakes before execution
- `clikernel.skill`: Use `clikernel` MCP as the default persistent Python workspace for file/notebook reads and edits, exploration, library checks, data reshaping and debugging. Imports and variables carry across calls. Read before writing, running or debugging Python with `clikernel` connected."""

__version__ = "0.2.22"


