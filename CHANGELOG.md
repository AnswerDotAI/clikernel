<!-- do not remove -->

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

