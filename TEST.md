# Task: Add clikernel Tests

You are starting from a small package in this directory. The goal is to add a focused automated test suite for `clikernel`, the stdin/stdout Python worker built around `execnb.shell.CaptureShell`. clikernel is already installed in this venv, as is pytest.

## Current Behavior To Test

`clikernel` is exposed as a console entry point. When started, it prints a ready delimiter on stdout:

```text
--aB3x9
```

The delimiter is exactly `--` plus 5 alphanumeric characters. It stays the same for the whole session. After every complete request, `clikernel` first prints an acknowledgement line:

```text
.
```

It then prints the rendered output and the session delimiter. Treat that delimiter as the completion signal and, for multiline inputs, as the terminator.

Single-line input executes immediately:

```text
1+1
```

Expected response:

```text
.
2
--aB3x9
```

Multiline input starts with a bare `--` line and ends with the session delimiter exactly:

```text
--
def f(x):
    return x + 1

f(41)
--aB3x9
```

Expected response:

```text
.
42
--aB3x9
```

The process is persistent. Variables, imports, and objects should survive across requests in the same process.

Outputs are rendered by `fastcore.nbio.render_text`. A single non-empty output is emitted directly. Multiple outputs use XML-ish tags with raw body text, for example:

```text
<stdout>
hello
</stdout>
<display_data mime="text/markdown">
**shown**
</display_data>
<execute_result>
42
</execute_result>
```

## Suggested Test Plan

Add `tests/test_cli.py` with subprocess-based tests. A simple helper should start `clikernel` with `stdin=PIPE`, `stdout=PIPE`, `stderr=PIPE`, `text=True`, and read stdout line-by-line until it sees a delimiter matching `^--[A-Za-z0-9]{5}$`.

Useful helper shape:

```python
def read_until_ready(proc):
    lines = []
    while True:
        line = proc.stdout.readline()
        assert line, proc.stderr.read()
        s = line.rstrip('\n')
        if re.fullmatch(r'--[A-Za-z0-9]{5}', s): return ''.join(lines), s
        lines.append(line)
```

Test cases to cover:

1. Startup prints a valid ready delimiter.
2. `1+1` first returns acknowledgement `".\n"`, then body `"2\n"` and the same valid delimiter.
3. State persists: send `x=41`, then `x+1`, and assert the second body is `"42\n"`.
4. Multiline request uses bare `--` plus the session delimiter and returns `"42\n"`.
5. Mixed stdout/display/result output contains the expected `<stdout>`, `<display_data mime="text/markdown">`, and `<execute_result>` blocks.
6. Runtime errors still return acknowledgement `".\n"`, readable error text containing the exception name, and then the same delimiter.

Keep tests small and deterministic. Terminate the subprocess in a fixture/finally block. Avoid sleeping; use blocking readline with a timeout mechanism if needed.

If pytest is not already available in this package's dev dependencies, add it to `pyproject.toml` under `[project.optional-dependencies].dev`. Configure the project so that `pytest -q` works ootb.

Do not publish or tag anything. Keep the changes limited to tests and any minimal test dependency/configuration needed to run them.
