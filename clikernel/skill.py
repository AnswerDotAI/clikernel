# NB: this file is designed for an LLM reader, not a human. Add it to your LLM's context and ask it to explain.
r"""Use `clikernel` MCP as the default persistent Python workspace for file/notebook reads and edits, exploration, library checks, data reshaping and debugging. Imports and variables carry across calls. Read before writing, running or debugging Python with `clikernel` connected.

- prefer: clikernel over one-off scripts (`python -c`, heredocs); pyskills over shell (rgapi `rg` `fd` `ls`; ghapi: GitHub, git); shell: project tests, builds, non-Python tools
- outlive conversation: `create(kernel="py", dlgname="work", autoclose=false)`, tell user its id; reply shows gateway started by this conversation: say so    /kernel needs a lasting gateway
- earlier or user's solveit kernel: `list_kernels` → `use_kernel(id)`
- `restart`: reruns startup only in kernels this conversation created; redo the rest; `interrupt` keeps state
- `host=` names: `~/.config/clikernel/gateways.toml`; later `exec` stays on that host
- bpl kernel: gateway environment needs basedpl

# Python

- magics work, `%%bash` too; `%cd` (expands `~`), not `os.chdir`
- top-level expressions display, not those in blocks (clikernel default; startup can override)
- all output reaches conversation: `len(v)` first
- imports: once; `NameError` for your name: kernel restarted or attached: redo setup
- after `nbdev-export` or module edit: `importlib.reload`, re-import held names (`from x import y` keeps old object); `@patch` refreshes; restart only if a held instance's class changed
- loaded behavior: call it, never `inspect.getsource`    /reads disk
- before env changes, monkeypatching, extra setup: try the plain import or call
"""
