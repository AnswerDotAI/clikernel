# clikernel

`clikernel` is a tiny stdin/stdout worker around `execnb.shell.CaptureShell`. It keeps one IPython-compatible Python process alive and returns concise text for each request.

## The Key Idea

The idea of clikernel is to be a persistent python process that LLMs can use as their primary tool.

A persistent Python process is a good default tool for an LLM agent. The agent can import a module, inspect it, keep helper functions around, cache results, patch objects, and then continue from that state on the next request.

This is especially useful with [pyskills](https://github.com/AnswerDotAI/pyskills). The agent can discover skills, read their docs, import the ones it needs, and keep using them in the same session. That makes Python a universal workbench for repo inspection, API checks, file edits, data transforms, and experiments.

`clikernel` gives an agent the part of a notebook kernel it usually needs: send code, wait for the result, read concise text, and keep the Python state.

## Protocol

On startup, `clikernel` prints loading status followed by a fresh ready delimiter:

```text
please wait, loading...
loading complete. first delimiter:
--aB3x9
```

Send one line to execute it immediately:

```text
1+1
```

For multiline code, send `--` on its own line, then the code, then the latest ready delimiter exactly:

```text
--
def f(x):
    return x + 1

f(2)
--aB3x9
```

After execution, `clikernel` prints the rendered output followed by a new ready delimiter:

```text
3
--Q7z2M
```

Outputs are rendered with `fastcore.nbio.render_text`. A single non-empty output is printed directly. Multiple outputs use raw XML-ish tags, for example `<stdout>`, `<display_data mime="text/markdown">`, and `<execute_result>`.

`clikernel` sets quiet defaults for `IPYTHONDIR`, `MPLCONFIGDIR`, and `MPLBACKEND=Agg` before creating the shell. Existing `IPYTHONDIR` and `MPLCONFIGDIR` values are left alone. Loading messages and any startup warnings are printed before the first delimiter. Set `CLIKERNEL_STATE_DIR` to choose the default parent directory.

## Why The Protocol Is Odd

`clikernel` is built for a client that reads stdout as tokens. Local echo is disabled when stdin is a TTY. The client already knows the code it sent, so echoing it back only makes the LLM read slow, expensive tokens that add no information.

Each response ends with a delimiter on its own line. The client can read until that line appears instead of parsing prompts or waiting and guessing. The delimiter changes after every request. This matters for multiline input, where the current delimiter is also the block terminator. A random current delimiter is unlikely to appear in generated code, copied logs, examples, or earlier transcript text. Old delimiters stop working as soon as the next response is printed.

Startup messages appear before the first delimiter. After that first delimiter, the stream follows the request-response protocol. Outputs are rendered as concise text, using unescaped XML if required when there's multiple outputs.

IPython history is disabled. `IPYTHONDIR` and `MPLCONFIGDIR` get quiet defaults when the environment has not already set them, and `MPLBACKEND` defaults to `Agg`.

## Development

```bash
pip install -e .[dev]
```

### Versioning

Version lives in `clikernel/__init__.py` as `__version__`.

### Release

1) Ensure your GitHub issues are labeled (`bug`, `enhancement`, `breaking`).
2) Run:

```bash
ship-gh
ship-pypi
ship-bump  # dev release always later than prod release
```

