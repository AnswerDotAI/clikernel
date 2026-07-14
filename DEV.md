# clikernel development notes

The README documents what clikernel does: a persistent IPython worker with a stream protocol and an MCP wrapper. This file documents why it is built the way it is, how the pieces relate, and what we know about the LLM agents that use it, since much of the design only makes sense in light of that. It assumes you can read the code; it gives you the context the code can't.

The one-sentence thesis: a persistent Python process is the substrate, with deliberately small extension points -- the startup file and the cell-inspector hook -- through which behavior layers like [llmdojo](https://github.com/AnswerDotAI/llmdojo) keep an LLM agent on its designed toolchain. The kernel itself stays unopinionated; the opinions plug in.

## Layout

- `base.py`: transport, plus the `RuleBlock` exception that defines the inspector blocking contract. The stream protocol (delimiters, multiline blocks, `.` acknowledgements) and the MCP server machinery (`_Worker`, `_serve`, `run_mcp`). Protocol rationale is in the README.
- `cli.py`: worker assembly. Creates the `CaptureShell`, runs the startup file, loads inspectors, registers `%nbrun`, and wires `_execute` (inspect, then run, then render).
- `skill.py`: the LLM-facing docs, registered as a pyskill so `doc(clikernel.skill)` is the discovery path.
- `mcp.py`: entry point; passes `skill.py`'s text as MCP instructions and enables eager start in Python projects.

## Inspectors and the rules

Each cell is IPython-transformed (so magics and `!` escapes parse), parsed to an AST, and passed to every inspector before it runs. An inspector returns a note string to prepend, returns None, or raises `RuleBlock` to stop the cell. That contract has one sharp edge worth knowing the history of: any *other* exception from an inspector is treated as an inspector bug and fails open, prepending a warning while the cell still runs. Originally a crash rendered as `<blocked>`, and a stray `TypeError` (a `PosixPath` in an `in` test) was reported by the agent as a policy denial that didn't exist; the agent then confabulated a mechanism for it. Blocks must be deliberate and attributable, so deliberate blocking got its own exception type.

Users can add inspectors in `$XDG_CONFIG_HOME/clikernel/inspectors.py` (see `examples/inspectors.py`, which blocks `subprocess` and `os.system`). A broken user inspectors file is reported and skipped rather than preventing startup, same fail-open philosophy.

Why an inspector hook at all, when guidance already exists in skills and prompts? Because a note that arrives in the tool result, at the exact moment of a mistake, binds far better than standing prompt text, which decays over a session. The evidence writeup lives in [llmdojo](https://github.com/AnswerDotAI/llmdojo)'s DEV notes; its session rules are this hook's main consumer.


## Kernel lifecycle under Claude Code

Facts established by live experiment (see llmdojo's DEV notes for the fuller set and their doc-state implications): the MCP server, and so the kernel, dies with the app and restarts on resume, but survives compaction -- the same kernel pid keeps answering across a compact, with its namespace intact. So a resumed conversation sees a fresh kernel behind a fully-replayed context, and a compacted one sees a live kernel behind a rewritten context; the startup file re-runs only in the first case. llmdojo's `claude/` dir holds the user-level Claude Code config (hooks, startup file) that manages those seams.

## Testing and release

`pytest -q`. `test_cli.py` covers the stream protocol, startup file handling (including that `__file__` is popped after startup, since `%run -i` leaves it behind and its presence broke downstream guards), and the inspector fail-open contract. `test_mcp.py` covers the server wrapper. Development style follows the fastai conventions (see the `coding-patterns` skill); versioning is bump-after-release, so the tree always carries the next version. Release is `ship-gh`, `ship-pypi`, `ship-bump`.
