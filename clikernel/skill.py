"""Use the persistent `clikernel` MCP session as the default workspace for any task advanced through live Python execution -- stateful inspection, file-editing workflows, debugging, experiments, API probes, data transforms, or notebook-style work. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.

# Core idea

clikernel connects this conversation to Jupyter kernels hosted by a jupygate server that runs all the time, independently of any conversation. Kernels persist until explicitly stopped: state kept across the whole conversation -- imports, live objects, monkeypatches, cached results -- and, when wanted, across conversations. Treat it as a notebook-style workbench, not a one-shot script runner.

Prefer it over one-off Python scripts (`python -c`, shell heredocs) whenever you need to inspect runtime behavior, test an idea, call a Python API, examine package state, run a live probe, or iterate on an implementation detail. Prefer in-kernel tools over shell equivalents when they exist: file search and directory listing go through the `rgapi` pyskill (`rg()`/`fd()`/`ls()`), and GitHub work through the `ghapi` pyskill, when those are installed. Shell commands remain the right tool for local git operations, project test/build commands, and non-Python tools -- and they go through the harness's shell tool, never `subprocess`/`os.system` from the kernel. The kernel route bypasses the harness's permission hooks, and capturing output invites truncating it before reading; the shell tool runs the command visibly and returns everything.

# The lifecycle contract

Nothing is implicit. There is no kernel until `connect` is called, and no kernel is ever stopped except by `stop_kernel`. The tools are self-documenting -- read each tool's MCP description -- and the shape of a session is:

- Start of work: `connect` (bare) creates a fresh kernel, runs the user's `startup.py`, installs their inspectors, and replies with the kernel id and the startup output. Read that output: it says what is imported and what to do next.
- Returning to earlier work (the user asks to continue where a previous conversation left off, or to use their solveit kernel): `list_kernels` to see what's running, then `connect` with the kernel id (or unique prefix). Attach runs nothing -- the kernel's live state is the point.
- End of work: `stop_kernel` if the kernel was for this task only; leave it running if the user wants to return to it, and tell the user its id so they can.

`restart` gives the current kernel a genuinely fresh interpreter under the same id (redo imports after it); `interrupt` stops a too-long `execute` while keeping state. If a reply says the kernel died, `connect` again. If `connect` fails because the gateway is unreachable, the jupygate server is not running -- report that to the user rather than working around it.

Remote gateways (a jupygate or solveit instance elsewhere) are the same verbs with a `host`: a name from `~/.config/clikernel/gateways.toml` (`[gateways.<name>]` tables with `url` and `token` or `token_env`) or a URL. Tokens live in the config file, never in tool arguments.

# Notebook magics

`execute` runs IPython, so magics work as written. The `%nbrun` line magic (registered by aidialog, which the standard startup imports) runs cells from a `.ipynb` file by cell id prefix -- see `doc(dsk)` after startup for its options. It runs *in the kernel*, so its cells share session state and are checked by the session's inspectors.

# Session setup

`connect` (creating) first runs `~/.config/clikernel/startup.py` (with `__file__` bound, so the file can locate its neighbors), then installs inspectors from `~/.config/clikernel/inspectors.py`. Both travel as source, so remote kernels get the same setup as local ones. Inspectors see each cell before it runs (1-arg: the AST; 2-arg: AST and raw source): a returned string prints as a note ahead of the cell's output, raising `RuleBlock` (provided in the file's namespace) blocks the cell, and inspector bugs warn and fail open. Attached kernels are taken as found: no startup, no inspectors.

# Output shape

Outputs are rendered with `fastcore.nbio.render_text`. A single non-empty output comes back as its preferred text form, e.g. `42`; multiple outputs use readable XML-ish tags (`<stdout>`, `<execute_result>`, ...) with raw, unescaped body text. Exceptions come back as one clean traceback: ANSI-stripped, over-long lines capped at 120 characters with `File `/`Cell ` locations and the exception message always whole. `input()` fails fast in-band (`allow_stdin=False`) rather than hanging. Image outputs (plots etc.) arrive as MCP image blocks, resized to a token-friendly budget, each preceded by a `<media id=...>` text tag naming it; when the image cannot be delivered, a `<media-unavailable>` note appears in the text instead.

# Interaction rules

- Try the simple import or API call first, before mutating environment, monkeypatching, or adding setup.
- Like Jupyter, only the *last* expression in a cell displays. `print(...)` any earlier value you need to see.
- Don't re-run an `import` already run this session. If a previously-imported name raises `NameError`, the kernel restarted or is newly attached -- redo setup.
- `importlib.reload` is not always enough: `from x import *` consumers and `@patch`-decorated classes hold stale references. On stale-class symptoms, use the `restart` tool.
- Everything a cell outputs lands in the conversation. Be surgical: `print(len(v))` first, then decide what to show.
- A kernel is shared by anything connected to it: subagents in this session, or the user's own client. Assume shared state is a feature, not a surprise.

# Pyskills

This environment commonly has `pyskills` installed. When present, check it first and prefer a relevant pyskill over ad hoc code:

    from pyskills import list_pyskills, doc
    import pyskills.skill
    doc(pyskills.skill)

# The stream protocol

Driven as a plain CLI process (`clikernel [--host H] [--kernel K]`), the same client speaks a delimiter-framed stdin/stdout protocol, documented in its own startup banner and the README. Run bare it creates a kernel and stops it on exit; `--kernel` attaches and leaves it running.
"""
