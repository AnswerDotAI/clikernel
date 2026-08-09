# Changelog

<!-- do not remove -->

## 0.2.2

### New Features

- skip AST inspectors on nested `run_cell` so tool-replayed cells (e.g. %nbrun) are not treated as user-typed input ([#32](https://github.com/AnswerDotAI/clikernel/issues/32))


## 0.2.1

### New Features

- Delegate traceback truncation and ANSI stripping to fastcore `render_text`(`tb_maxlen`=120); drop `render_outs` ([#31](https://github.com/AnswerDotAI/clikernel/issues/31))


## 0.2.0

### New Features

- Rewire stream worker onto jupygate kernels via jupyasyncclient, drop in-process shell and Client.`_run`, add stream REPL example ([#29](https://github.com/AnswerDotAI/clikernel/issues/29))
- Return kernel image outputs as MCP image blocks via aidialog `output_parts`/`merge_media` ([#28](https://github.com/AnswerDotAI/clikernel/issues/28))
- Rewrite clikernel as jupygate kernel client: nbdev port, MCP connect/execute/lifecycle tools, persistent kernels, stream CLI retained ([#27](https://github.com/AnswerDotAI/clikernel/issues/27))
- Support top-level await in %nbrun cells under async magics ([#26](https://github.com/AnswerDotAI/clikernel/issues/26))
- Add streamable-http transport with required bearer-token auth ([#25](https://github.com/AnswerDotAI/clikernel/pull/25)), thanks to [@erikgaas](https://github.com/erikgaas)
- Support mcp SDK 2.0, which renamed FastMCP to MCPServer ([#23](https://github.com/AnswerDotAI/clikernel/pull/23)), thanks to [@erikgaas](https://github.com/erikgaas)
- Forward rich image display outputs as MCP ImageContent blocks ([#16](https://github.com/AnswerDotAI/clikernel/pull/16)), thanks to [@ncoop57](https://github.com/ncoop57)


## 0.1.7

### New Features

- Clarify %nbrun stop-on-error semantics, make broken inspectors fatal, and expand nbdev/inspect-runtime guidance ([#20](https://github.com/AnswerDotAI/clikernel/issues/20))
- Replace %nbopen with pyskills notebook integration, add RuleBlock fail-open inspectors, new s-command rules, dojo completion API and refusal messages, and host-based doced state ([#18](https://github.com/AnswerDotAI/clikernel/issues/18))
- Run startup.py via `%run -i` so `__file__` is set ([#17](https://github.com/AnswerDotAI/clikernel/issues/17))
- Improve orient kata feedback to name only missing cell ids and clarify import-cell ruling ([#15](https://github.com/AnswerDotAI/clikernel/issues/15))
- Add stream-protocol banner, read-only kata support, paused-ledger dojo flow, `dojo_resume`, fastcore doc exemption, and displayed-read-only context rule ([#14](https://github.com/AnswerDotAI/clikernel/issues/14))


## 0.1.6

### New Features

- Add dojo completion tracking with skip-on-replay, kata tag scoping, data-file read exemption, tuple-payload rule, and warn-tagged nodoc findings ([#13](https://github.com/AnswerDotAI/clikernel/issues/13))
- Add dojo practice system and live best-practice rules; extract kernel-agnostic core into base.py ([#12](https://github.com/AnswerDotAI/clikernel/issues/12))


## 0.1.5

### New Features

- Enable IPython profile loading by default, matching ipykernel behavior ([#11](https://github.com/AnswerDotAI/clikernel/issues/11))
- Add startup.py support and forward INSTRUCTIONS + startup output as MCP instructions ([#10](https://github.com/AnswerDotAI/clikernel/issues/10))


## 0.1.4

### New Features

- Add cell inspectors, consolidate terminal handling, and harden MCP supervisor with signal guards and error recovery ([#9](https://github.com/AnswerDotAI/clikernel/issues/9))
- Switch MCP server from in-process shell to supervised subprocess worker, add interrupt tool and idle-SIGINT handling ([#8](https://github.com/AnswerDotAI/clikernel/issues/8))


## 0.1.3

### New Features

- Add `exit` MCP tool for hard process reset, and add pyskill ([#7](https://github.com/AnswerDotAI/clikernel/issues/7))
- Add asyncio lock and async wrappers to MCP tools to allow top-level await ([#6](https://github.com/AnswerDotAI/clikernel/issues/6))
- Add %nbopen/%nbrun line magics for running notebook cells by id prefix ([#5](https://github.com/AnswerDotAI/clikernel/issues/5))
- Add MCP server exposing persistent IPython session; suppress duplicate tracebacks and defer init to main() ([#3](https://github.com/AnswerDotAI/clikernel/issues/3))

### Bugs Squashed

- Set `structured_output`=False on MCP tool decorators ([#4](https://github.com/AnswerDotAI/clikernel/issues/4))


## 0.1.2

### New Features

- Add ONLCR terminal flag control ([#2](https://github.com/AnswerDotAI/clikernel/issues/2))


## 0.1.1

### New Features

- Use a fixed per-session delimiter and emit `.` ack before each response ([#1](https://github.com/AnswerDotAI/clikernel/issues/1))


## 0.1.0

- Initial release
