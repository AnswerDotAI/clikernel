"""Use the persistent `clikernel` MCP session as the default workspace for any task advanced through live Python execution -- stateful inspection, file-editing workflows, debugging, experiments, API probes, data transforms, or notebook-style work. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.

# Core idea

`clikernel` exposes one long-lived IPython process (wrapping `execnb.shell.CaptureShell`) that runs Python/IPython code and keeps state across the whole conversation: imports, live objects, monkeypatches, cached results, API clients, small experiments. Treat it as a notebook-style workbench, not a one-shot script runner.

Prefer it over one-off Python scripts (`python -c`, shell heredocs) whenever you need to inspect runtime behavior, test an idea, call a Python API, examine package state, run a live probe, or iterate on an implementation detail. Shell commands are still the right tool for file search, git, project test/build commands, and non-Python tools.

There are two ways to drive it, depending on what the host supports:

- **MCP server** (`clikernel-mcp`): no delimiter protocol, stdin plumbing, or readiness polling to manage -- call one tool, get back the rendered outputs.
- **CLI** (`clikernel`): a plain stdin/stdout process using a delimiter protocol, for hosts that drive background terminal sessions instead of MCP tools.

# MCP tools

`execute`, `restart`, and `interrupt` are self-documenting -- read each tool's own MCP description rather than looking for docs elsewhere. `restart` gives a genuinely fresh interpreter process (new pid, `sys.modules` reset); `interrupt` stops a too-long-running `execute` while keeping session state.

# CLI protocol

When driven as a plain process, `clikernel` prints loading status followed by a random session delimiter -- always `--` plus 5 alphanumeric characters:

    please wait, loading...
    loading complete. first delimiter:
    --aB3x9

Any startup warnings print before the first delimiter. Treat that delimiter as the readiness signal, completion signal, and multiline terminator; it stays the same until the process exits.

Send a single line to execute a single-line request. `clikernel` first prints an acknowledgement line (`.`) -- that means request *accepted*, not execution complete -- then the response body, then the session delimiter:

    1+1
    .
    2
    --aB3x9

Use a bare `--` line to start multiline input, ending the block with the session delimiter exactly:

    --
    def f(x):
        return x + 1

    f(2)
    --aB3x9

Do not look for an IPython prompt, do not use `%cpaste`, and do not invent your own terminator. A blank line is a real (empty) request, so it makes a good idle-poll: an idle kernel answers with `.` and the delimiter; if that doesn't come back quickly, the previous request is still running or the process is wedged.

Python exceptions render as normal notebook error output. Protocol/worker failures render with readable XML-ish error tags, then the session delimiter.

To end the session, send `exit`. In CLI mode there is no `restart` tool -- starting a fresh process *is* the restart, and gives a genuinely fresh interpreter (the equivalent of the MCP `restart` tool).

# Notebook magics

`execute` runs IPython, not plain Python, so magics work as written. Two line magics run cells from a `.ipynb` file by cell id prefix:

    %nbopen foo.ipynb
    %nbrun ab12
    %nbrun ab12 --above
    %nbrun --all --exported
    %nbrun ab12 --fname other.ipynb

`%nbopen` sets the default notebook for later `%nbrun` calls (passing `--fname` does too). `%nbrun` runs the cell whose id starts with the given prefix; `--above`/`--below` also run the cells before/after it, `--all` runs every code cell, and `--exported` filters to cells carrying an nbdev `#| export`/`#| exports` directive. The notebook is re-read from disk on each call, so file edits are picked up; each executed cell's output is printed under a `--- {cell id} ---` header. Cell execution shares the persistent session state, and `restart` clears the `%nbopen` default.

Prefer these magics over copying cell source into `execute` by hand when working through a notebook -- e.g. after editing a cell, `%nbrun <id>` re-runs it in place, and `%nbrun <id> --above` rebuilds the state it depends on.

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
    print(doc(pyskills.skill))
"""

__all__ = []
