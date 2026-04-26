# clikernel

`clikernel` is a tiny stdin/stdout worker around `execnb.shell.CaptureShell`. It keeps one IPython-compatible Python process alive and returns concise text for each request.

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

Outputs are rendered with `fastcore.nbio.render_text`. A single non-empty output is printed directly. Multiple outputs use raw XML-ish tags, for example `<stream>`, `<display_data>`, and `<execute_result>`.

`clikernel` sets `IPYTHONDIR`, `MPLCONFIGDIR`, and `MPLBACKEND=Agg` before creating the shell. Loading messages and any startup warnings are printed before the first delimiter. Set `CLIKERNEL_STATE_DIR` to choose the state directory.

## Development

```bash
pip install -e .[dev]
```

## Versioning

Version lives in `clikernel/__init__.py` as `__version__`.
Bump it with:

```bash
ship-bump --part 2   # patch
ship-bump --part 1   # minor
ship-bump --part 0   # major
```

## Release

1) Ensure your GitHub issues are labeled (`bug`, `enhancement`, `breaking`).
2) Run:

```bash
ship-gh
ship-pypi
```
