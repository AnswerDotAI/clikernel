"""Use the `clikernel` MCP session as the default workspace for Python work: reading and changing files, notebook work, trying things out, checking how a library behaves, and reshaping data. One session stays open, so imports and variables carry between calls. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.

Prefer it over one-off Python scripts (`python -c`, shell heredocs). Prefer in-kernel tools over shell equivalents when they exist: file search and directory listing go through the `rgapi` pyskill (`rg()`/`fd()`/`ls()`), and GitHub and local git work through the `ghapi` pyskill, when those are installed. Shell commands remain the right tool for project test/build commands and non-Python tools.

# Starting and stopping

Call `create(kernel="py")` before executing Python code. Creation reports what startup imported: read that banner, it says what to do next. New kernels require an explicit implementation. Add `dlgname` to bind a kernel to a dialog. Omit `kernel` only to reuse an existing binding. An explicit implementation must match that binding.

A kernel this conversation creates stops when the conversation ends, unless created with `autoclose=false`. Use `create(kernel="py", dlgname="work", autoclose=false)` when a kernel should stay running afterwards, and tell the user its id. This requires a gateway that keeps running. Mention it if the reply shows a conversation-started gateway.

To continue earlier work, or to use the user's solveit kernel, `list_kernels` then `use_kernel` with the id. Attaching runs no setup and claims no ownership: the kernel's live state is the point, and it is never stopped for you.

`restart` gives a fresh interpreter under the same id; Python startup re-runs in Python kernels this conversation created, so redo everything else. `interrupt` stops a long `exec` and keeps state. If a reply says the kernel is gone, call `create` or `use_kernel` before executing again. Execution never creates or switches kernels.

Remote gateways are the same tools with a `host` argument on `list_kernels`, `use_kernel`, and `create`, named in `~/.config/clikernel/gateways.toml`. After selecting with a host, plain `exec` runs there until the next selection.

# Working in it

Run code with `exec(code=...)` in the selected kernel. For native Luau work, select `create(kernel="luau")` first. The same execution tool and autoclose rules apply to every implementation. A `dlgname` execution override uses an existing binding for that call without changing the current selection. These rules also apply on named remote gateways.

For APL, use `create(kernel="apl")` then `exec(code="avg←+/÷≢ ⋄ avg 2 4 9")`. `basedpl` must be installed in the gateway's environment. It provides the `apl` kernelspec. Python startup and inspectors do not run in APL.

Start native work with `exec(code="help()")` for the bundled guide and examples, or `exec(code='help("ex.edit_file")')` for function details.

Luau has persistent globals, cell-local `local` variables, and native `rg.search`, `rg.find`, `fs.read_text`, `ex.edit_text`, `ex.view_file`/`ex.edit_file`, `ex.view_cell`/`ex.edit_cell`, `os.execute`, and `io.popen` APIs. File edits use arrays of command fields (like Python exhash tuples); `{inplace=false}` previews. Shell commands use `/bin/sh -c`; pipes support read/lines/write/flush/close and persist until closed. Interrupts terminate subprocess groups and close outstanding pipes. Python startup/inspectors and IPython magics do not apply to Luau. The following guidance is for Python:

- Magics work as written, including `%%bash` for shell work. `%cd` expands `~` and is the way to change directory: prefer it over `os.chdir`.
- Python kernels created by clikernel display every expression result by default (`ast_node_interactivity='all'`); user startup can override this.
- Everything a cell outputs lands in the conversation. Be selective: `len(v)` first, then decide what to show.
- Don't re-run an `import` already run this session. If a name raises `NameError`, the kernel restarted or is newly attached: redo setup.
- After an `nbdev-export` (or any edit to a module already imported), `importlib.reload` that module and re-import any names you hold from it: a name bound by `from x import y` keeps the old object, while a `@patch`ed method refreshes with the reload because the patch writes onto the shared class. Restart only when a class you hold instances of was itself redefined. Check what is loaded by calling it, never with `inspect.getsource`, which reads the file on disk.
- Try the simple import or API call first, before changing the environment, monkeypatching, or adding setup.
"""
