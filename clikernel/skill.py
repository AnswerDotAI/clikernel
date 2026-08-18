"""Use the `clikernel` MCP session as the default workspace for Python work: reading and changing files, notebook work, trying things out, checking how a library behaves, and reshaping data. One session stays open, so imports and variables carry between calls. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.

Prefer it over one-off Python scripts (`python -c`, shell heredocs). Prefer in-kernel tools over shell equivalents when they exist: file search and directory listing go through the `rgapi` pyskill (`rg()`/`fd()`/`ls()`), and GitHub and local git work through the `ghapi` pyskill, when those are installed. Shell commands remain the right tool for project test/build commands and non-Python tools.

# Starting and stopping

The first `execute` creates a kernel and reports what it imported: read that banner, it says what to do next. That kernel stops when the conversation ends. Use a bare `connect` instead when the kernel should stay running afterwards, and tell the user its id.

To continue earlier work, or to use the user's solveit kernel, `list_kernels` then `connect` with the id. Attaching runs no setup: the kernel's live state is the point.

`restart` gives a fresh interpreter under the same id, so redo any setup. `interrupt` stops a long `execute` and keeps state. If a reply says the kernel has stopped, `connect` again. If `connect` fails, the gateway server is not running: tell the user rather than working around it.

Remote gateways are the same verbs with a `host`, named in `~/.config/clikernel/gateways.toml`.

# Working in it

- Magics work as written. `%cd` expands `~` and is the way to change directory: prefer it over `os.chdir`.
- Only the last expression in a cell displays. `print(...)` any earlier value you need to see.
- Everything a cell outputs lands in the conversation. Be selective: `len(v)` first, then decide what to show.
- Don't re-run an `import` already run this session. If a name raises `NameError`, the kernel restarted or is newly attached: redo setup.
- After an `nbdev-export` (or any edit to a module already imported), `importlib.reload` that module and re-import any names you hold from it: a name bound by `from x import y` keeps the old object, while a `@patch`ed method refreshes with the reload because the patch writes onto the shared class. Restart only when a class you hold instances of was itself redefined. Check what is loaded by calling it, never with `inspect.getsource`, which reads the file on disk.
- Try the simple import or API call first, before changing the environment, monkeypatching, or adding setup.
"""
