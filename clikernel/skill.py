"""Use the persistent `clikernel` MCP session as the default workspace for any task advanced through live Python execution -- stateful inspection, file-editing workflows, debugging, experiments, API probes, data transforms, or notebook-style work. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.

# Core idea

`clikernel` exposes one long-lived IPython process (wrapping `execnb.shell.CaptureShell`) that runs Python/IPython code and keeps state across the whole conversation: imports, live objects, monkeypatches, cached results, API clients, small experiments. Treat it as a notebook-style workbench, not a one-shot script runner.

Prefer it over one-off Python scripts (`python -c`, shell heredocs) whenever you need to inspect runtime behavior, test an idea, call a Python API, examine package state, run a live probe, or iterate on an implementation detail. Prefer in-kernel tools over shell equivalents when they exist: file search and directory listing go through the `rgapi` pyskill (`rg()`/`fd()`/`ls()`), and GitHub work (PRs, issues, CI status) through the `ghapi` pyskill, when those are installed. Shell commands remain the right tool for local git operations, project test/build commands, and non-Python tools.

Normally the harness drives it as an MCP server (`clikernel-mcp`). Driven instead as a plain CLI process, `clikernel` documents its delimiter protocol in its own startup banner.

# MCP tools

`execute`, `restart`, and `interrupt` are self-documenting -- read each tool's own MCP description rather than looking for docs elsewhere. `restart` gives a genuinely fresh interpreter process (new pid, `sys.modules` reset); `interrupt` stops a too-long-running `execute` while keeping session state.

# Notebook magics

`execute` runs IPython, not plain Python, so magics work as written. The `%nbrun` line magic runs cells from a `.ipynb` file by cell id prefix:

    %nbrun ab12
    %nbrun ab12 cd34 ef56
    %nbrun ab12 --above
    %nbrun --all --exported
    %nbrun ab12 --fname other.ipynb

`%nbrun` targets the current notebook (`set_dlg(fname)` from `aidialog.dlgskill`), so the same registration covers editing tools and cell running alike; `--fname` overrides for one call. It takes one or more cell id prefixes and runs each matching cell in the order given; `--above`/`--below` also run the cells before/after it, `--all` runs every code cell, `--exported` filters to cells carrying an nbdev `#| export`/`#| exports` directive, and `--skip_noeval` skips `#| eval: false` and `nbdev_export` cells (use it with `--above`/`--all` in nbdev repos, where such cells often hit live services). The run stops at the first cell that errors, unless `--continue_on_error` is passed. The notebook is re-read from disk on each call, so file edits are picked up; each executed cell's output is printed under a `--- {cell id} ---` header. Cell execution shares the persistent session state; `restart` clears the current notebook along with everything else.

Prefer these magics over copying cell source into `execute` by hand when working through a notebook -- e.g. after editing a cell, `%nbrun <id>` re-runs it in place, and `%nbrun <id> --above` rebuilds the state it depends on.

# nbdev projects

In nbdev repos (notebooks in `nbs/` are the source of truth; `doc(nbdev.skill)` covers authoring style), a few kernel-specific rules apply:

- Export with a shell `nbdev-export` run from the project directory, not the in-kernel `nbdev_export()`. A full export is near-instant, so don't scope it with `--path`/`--file_re` - partial exports leave sibling modules stale. A notebook edit is invisible to installed code until export.
- Run notebook tests with a shell `nbdev-test --path /abs/path/nbs/foo.ipynb`, not in-kernel `test_nb`: the persistent kernel isn't the main thread, so signal-based cell timeouts can't work there, and a separate process can't pollute session state. For several notebooks in one parallel run, pass a directory plus `--file_glob` (`--path` takes one path and does not brace-expand).
- After exporting a change to an already-imported module, you may need to restart instead of reload. Other modules can retain stale references created by `from x import ...`, and `@patch` methods can remain attached to older class objects. Restart when the exported change could encounter either case.
- Work red-green with `%nbrun`: run the new test cell to see it fail, edit, export, re-run to see it pass.

# Output shape

Outputs are rendered with `fastcore.nbio.render_text`. A single non-empty stream/display/result/error comes back as just its preferred text form, e.g. `42`. Multiple non-empty outputs use readable XML-ish tags with raw, unescaped body text, e.g.:

    <stdout>
    hello
    </stdout>
    <execute_result>
    42
    </execute_result>

`display_data`/`execute_result` prefer a non-image, markdown-over-HTML representation; images are ignored. Exceptions come back as a single clean `<error>` traceback -- no color codes, not duplicated.

# Interaction rules

- Try the simple import or API call first, before mutating environment, monkeypatching, or adding setup. Only change session state after the ordinary path fails and the reason is understood.
- For file-editing workflows, view the target slice first and make the smallest verified edit -- avoid whole-file rewrites when a line/range/string operation is enough.
- Default to raw triple-quoted strings (`r'''...'''`) for generated markdown, code, regexes, commands, or other source-like text, since backslashes usually need to survive intact. Use normal triple-quoted strings only when Python's own escape processing is what you want. For risky multiline content, verify with `repr(...)` or a focused readback before writing broadly.
- Lean on reprs: many objects returned by libraries in this ecosystem (pyskills results especially) have reprs designed for direct reading. End a cell with the bare expression instead of writing a loop to reformat fields by hand -- only drop to attribute access when the repr genuinely omits what you need.
- To inspect a runtime object, prefer `info_md` from `ipykernel_helper` (where installed) over `inspect.getsource`: `info_md(obj)` is IPython's `?` (signature, docstring, file/line, type) and `info_md(obj, source=True)` is `??` (full source + location). The file:line it reports leads straight to the defining module or notebook cell.

# Critical issues

- Like Jupyter, only the *last* expression in a cell is printed/returned. `print(...)` any earlier value you need to see.
- Don't re-run an `import` you've already run this session -- it's persistent, so it's already done. Use `importlib.reload` if you've changed a module and need the change picked up. If a previously-imported name raises `NameError`, the session restarted -- redo whatever imports/setup the task needs.
- `importlib.reload`ing a module is not always enough to pick up a change: other already-imported modules that did `from x import *`, or that monkeypatched one of its classes (e.g. via fastcore's `@patch`), hold stale references that a targeted reload won't fix. If you hit a stale-class symptom (a class missing a method you know it has, `isinstance` mysteriously failing), you need a fresh interpreter process: the MCP `restart` tool, or in CLI mode, exit and start a new process.
- Everything a cell outputs lands in the conversation and stays there. Be surgical: inspect only what's needed, and don't dump large values -- `print(len(v))` first, then decide whether to print in full or filter down.
- The kernel is scoped to one client session and shared by any subagents within it. If the server restarts or exits, in-memory state is gone -- redo imports and setup.

# Pyskills

This kernel environment commonly has `pyskills` installed -- a plugin system for discovering additional Python capabilities registered by installed packages. When present, checking it is the first thing to do at the start of a session, and using a relevant pyskill is strongly preferred over ad hoc code. See `pyskills.skill`'s own docs for the full discovery/usage workflow:

    from pyskills import list_pyskills, doc
    import pyskills.skill
    doc(pyskills.skill)
"""

__all__ = []
