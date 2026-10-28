"""Use `clikernel` MCP as the default persistent Python workspace for file/notebook reads and edits, exploration, library checks, data reshaping and debugging. Imports and variables carry across calls. Read before writing, running or debugging Python with `clikernel` connected.

Prefer it to one-off scripts (`python -c`, shell heredocs) and installed in-kernel pyskills to shell equivalents: `rgapi` (`rg()`/`fd()`/`ls()`) for search/listing; `ghapi` for GitHub/local git. Shell stays right for project tests/builds and non-Python tools.

MCP tool descriptions give parameters/rules; this guide combines calls.

`create(kernel="py")` first; read its reply's startup imports and next steps before running anything. Kernels this conversation creates stop at its end. For one that should outlive it, `create(kernel="py", dlgname="work", autoclose=false)` and tell the user its id. It needs a gateway that keeps running; say so if the reply shows a conversation-started gateway.

To continue earlier work or use the user's solveit kernel: `list_kernels`, then `use_kernel` with the id. Attach runs no setup, claims no ownership and never stops that live kernel for you.

`restart` reruns Python startup only in kernels this conversation created; redo everything else. `interrupt` stops a long `exec`, keeping state. A kernel-gone reply requires `create` or `use_kernel` before executing again.

Remote gateways are named in `~/.config/clikernel/gateways.toml`. Same tools/rules: `host=` on `list_kernels`/`use_kernel`/`create`; plain `exec` follows the selected host until the next selection.

`create(kernel="luau")`/`create(kernel="bpl")`: same `exec`/autoclose rules, no Python startup/magics. Each creation reply gives language basics. Luau's `exec(code="help()")` gives the full native API; `help("ex.edit_file")` covers one function. BPL needs `basedpl` in the gateway environment for its `bpl` kernelspec.

# Python
- Magics work as written, including `%%bash`. Change directory with `%cd` (expands `~`), not `os.chdir`.
- clikernel-created Python kernels display every top-level expression, not expressions inside loops/blocks. User startup can override this.
- All cell output reaches the conversation: `len(v)` first, then choose what to show.
- Don't repeat imports. A `NameError` for a name you set up means the kernel restarted or is newly attached: redo setup.
- After `nbdev-export` or imported-module edits, `importlib.reload` and re-import held names: `from x import y` keeps the old object; `@patch` refreshes on reload by writing onto the shared class. Restart only when a class you hold instances of was redefined. Check loaded behavior by calling it, never `inspect.getsource` (reads disk).
- Try the simple import/API call before environment changes, monkeypatching or extra setup.
"""
