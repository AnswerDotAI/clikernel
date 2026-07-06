"""Example clikernel inspector: block shell/subprocess execution from the kernel.

Copy this to `$XDG_CONFIG_HOME/clikernel/inspectors.py` (usually
`~/.config/clikernel/inspectors.py`) to enable it. clikernel calls each inspector
with the parsed AST of every cell, before the cell runs. An inspector may return a
string (prepended to the cell's output as a note), raise (the cell does not run and
the exception is reported), or return None (do nothing). Define `inspect` and/or a
list `inspectors` of such functions.

This one raises, so it blocks. To warn instead, `return` the message rather than raising.
"""
import ast

_BANNED_MODS = {"subprocess"}

def _shell_call(n):
    "os.system/os.popen, or the get_ipython().system/getoutput that a `!`/`!!` escape compiles to"
    if not isinstance(n, ast.Attribute): return False
    v = n.value
    if isinstance(v, ast.Name) and v.id == "os" and n.attr in ("system", "popen"): return True
    return isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "get_ipython" and n.attr in ("system", "getoutput")

def _hit(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] in _BANNED_MODS for a in n.names): return True
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in _BANNED_MODS: return True
        if _shell_call(n): return True
    return False

def inspect(tree):
    if _hit(tree): raise RuntimeError("subprocess/shell execution is not allowed from the kernel — use the Bash tool, which routes through the permission layer.")
