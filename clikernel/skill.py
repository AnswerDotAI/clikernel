"""Use the `clikernel` MCP session as the default workspace for Python work: reading and changing files, notebook work, trying things out, checking how a library behaves, and reshaping data. One session stays open, so imports and variables carry between calls. Read this before writing, running, or debugging Python code in a session with `clikernel` connected.

Prefer it to one-off scripts (`python -c`, shell heredocs), and in-kernel pyskills to shell equivalents when installed: `rgapi` (`rg()`/`fd()`/`ls()`) for search and listing, `ghapi` for GitHub and local git. Shell stays right for project tests/builds and non-Python tools.

# Kernels

MCP tool descriptions give each tool's parameters and rules; this covers combining them.

`create(kernel="py")` first; its reply reports what startup imported and what to run next: read it before running anything. Kernels this conversation creates stop when it ends; for one that should outlive it, `create(kernel="py", dlgname="work", autoclose=false)` and tell the user its id. That needs a gateway that keeps running: say so if the reply shows a conversation-started gateway.

To continue earlier work or use the user's solveit kernel: `list_kernels`, then `use_kernel` with the id. Attaching runs no setup and claims no ownership: the live state is the point, and it's never stopped for you.

`restart` re-runs Python startup only in kernels this conversation created; redo everything else. `interrupt` stops a long `exec`, keeping state. If a reply says the kernel is gone, `create` or `use_kernel` before executing again.

Remote gateways (named in `~/.config/clikernel/gateways.toml`): same tools, with `host=` on `list_kernels`/`use_kernel`/`create`; all other rules unchanged. After selecting with a host, plain `exec` runs there until the next selection.

# Luau and APL

`create(kernel="luau")`/`create(kernel="apl")`: same `exec` and autoclose rules; no Python startup or magics. Each `create` reply gives the language basics; Luau's `exec(code="help()")` is its full native API guide (`help("ex.edit_file")` for one function). APL needs `basedpl` in the gateway's environment, which provides the `apl` kernelspec.

# Python

- Magics work as written, incl. `%%bash`. Change directory with `%cd` (expands `~`), not `os.chdir`.
- clikernel-created Python kernels display every expression result (`ast_node_interactivity='all'`); user startup can override.
- All cell output lands in the conversation: `len(v)` first, then choose what to show.
- Don't re-run imports already run. A `NameError` for a name you set up means the kernel restarted or is newly attached: redo setup.
- After `nbdev-export` or any edit to an imported module, `importlib.reload` it and re-import held names: `from x import y` keeps the old object; a `@patch`ed method refreshes on reload (the patch writes onto the shared class). Restart only when a class you hold instances of was redefined. Check what's loaded by calling it, never with `inspect.getsource` (reads the file on disk).
- Try the simple import or API call before changing the environment, monkeypatching, or adding setup.
"""
