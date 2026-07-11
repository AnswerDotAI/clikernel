import ast,inspect,os,runpy,shlex,sys,traceback
from pathlib import Path
from fastcore.xdg import xdg_config_home
from clikernel import INSTRUCTIONS
from clikernel.base import fmt_error,init_worker,run_startup,serve_stream

def _state_root():
    if d := os.environ.get("CLIKERNEL_STATE_DIR"): return Path(d).expanduser()
    from fastcore.xdg import xdg_state_home
    return xdg_state_home()/'clikernel'


def _set_default_dirs():
    path = Path(os.environ.get("MPLCONFIGDIR", _state_root()/"matplotlib")).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(path))
    os.environ.setdefault("MPLBACKEND", "Agg")


def _load_inspectors():
    "Cell inspectors from `$XDG_CONFIG_HOME/clikernel/inspectors.py`: each is called with the cell AST before execution, and may return a note (prepended to the output) or raise (blocking the cell). The file may define `inspect` and/or an `inspectors` list."
    path = xdg_config_home()/"clikernel"/"inspectors.py"
    if not path.exists(): return []
    try: ns = runpy.run_path(str(path))
    except Exception:
        print(f"clikernel: failed to load {path}:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return []
    ins = list(ns.get("inspectors", []))
    if callable(ns.get("inspect")): ins.append(ns["inspect"])
    return ins


def _stream_text(outputs):
    "Concatenate the stdout stream text from a `shell.run` output list."
    return "".join("".join(o["text"]) if isinstance(o["text"], list) else o["text"]
        for o in outputs if o.get("output_type") == "stream" and o.get("name") == "stdout")


def _startup_block(shell):
    "Run `$XDG_CONFIG_HOME/clikernel/startup.py` in the persistent session (so its imports and names are available to later requests), returning its `<startup file=...>` banner element via `run_startup`."
    def runner(src):
        out = _stream_text(shell.run(src))
        if not shell.exc: return out, None
        exc = shell.exc
        return out, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return run_startup(xdg_config_home()/"clikernel"/"startup.py", runner)


def _call_inspector(f, tree, code):
    "1-arg inspectors get the transformed AST; 2-arg ones also get the raw cell source (for lexical checks)"
    return f(tree, code) if len(inspect.signature(f).parameters) > 1 else f(tree)


def _inspect(shell, inspectors, code):
    "Run each inspector on the cell; return concatenated notes. An inspector may raise to block the cell."
    if not inspectors: return ""
    try: tree = ast.parse(shell.transform_cell(code))
    except SyntaxError: return ""  # let the cell's own execution report the error
    return "".join(note for f in inspectors if (note := _call_inspector(f, tree, code)))


def _execute(shell, inspectors, code):
    from fastcore.nbio import render_text
    try: note = _inspect(shell, inspectors, code)
    except Exception as e: return fmt_error("blocked", f"{type(e).__name__}: {e}")
    return note + render_text(shell.run(code))


def _request_exit(shell): shell._clikernel_exit = True


def _magic_wrap(fn):
    "Make a line magic from `fn`: `--name` flags for bool params, `--name value` otherwise, else positional"
    params = inspect.signature(fn).parameters
    def magic(line):
        args,kw = [],{}
        toks = iter(shlex.split(line))
        for t in toks:
            if t.startswith('--'):
                k = t[2:]
                kw[k] = True if params[k].annotation in (bool,'bool') else next(toks)
            else: args.append(t)
        return fn(*args, **kw)
    return magic


def _make_shell():
    from execnb.shell import CaptureShell
    # Named so fastcore's in_notebook/in_jupyter (a class-name check) treat clikernel as a notebook env
    class CliInteractiveShell(CaptureShell): pass
    shell = CliInteractiveShell(mpl_format=None, history=False, profile=True)
    for name in ('nbopen','nbrun'): shell.register_magic_function(_magic_wrap(getattr(shell, name)), 'line', name)
    shell._clikernel_exit = False
    shell.ask_exit = lambda: _request_exit(shell)
    # execnb already captures the exception as a structured error output; suppress
    # IPython's own traceback print so it isn't duplicated (in colour) via stdout.
    shell.showtraceback = lambda *a, **k: None
    shell.showsyntaxerror = lambda *a, **k: None
    return shell


def _should_exit(shell): return getattr(shell, "_clikernel_exit", False)


def main():
    init_worker()
    _set_default_dirs()
    shell = _make_shell()
    block = _startup_block(shell)
    inspectors = _load_inspectors()
    serve_stream(lambda code: _execute(shell, inspectors, code),
        INSTRUCTIONS + ("\n\n" + block if block else ""), should_exit=lambda: _should_exit(shell))


if __name__ == "__main__": main()
