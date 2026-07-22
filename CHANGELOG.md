<!-- do not remove -->

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
