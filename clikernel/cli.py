import ast,inspect,os,runpy,secrets,shlex,signal,string,sys,tempfile,termios,traceback,tty
from pathlib import Path
from fastcore.xdg import xdg_config_home

def _state_root():
    if d := os.environ.get("CLIKERNEL_STATE_DIR"): return Path(d).expanduser()
    return Path(tempfile.gettempdir()) / f"clikernel-{os.getuid()}"


def _set_default_dirs():
    state = _state_root()
    for env, name in (("IPYTHONDIR", "ipython"), ("MPLCONFIGDIR", "matplotlib")):
        path = Path(os.environ.get(env, state/name)).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault(env, str(path))
    os.environ.setdefault("MPLBACKEND", "Agg")


_ALPHANUM = string.ascii_letters + string.digits
_MULTILINE = "--"


def _new_delim(): return "--" + ''.join(secrets.choice(_ALPHANUM) for _ in range(5))


def _read_block(stdin, delim):
    lines = []
    for line in stdin:
        if line.rstrip("\n") == delim: return "".join(lines), None
        lines.append(line)
    return "", f"missing block terminator: {delim}"


def _format_error(tag, text): return f"<{tag}>\n{text}</{tag}>"


def _write_response(delim, body=None):
    if body: print(body, end='' if body.endswith('\n') else '\n', flush=True)
    print(delim, flush=True)


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


def _inspect(shell, inspectors, code):
    "Run each inspector on the cell's transformed AST; return concatenated notes. An inspector may raise to block the cell."
    if not inspectors: return ""
    try: tree = ast.parse(shell.transform_cell(code))
    except SyntaxError: return ""  # let the cell's own execution report the error
    return "".join(note for f in inspectors if (note := f(tree)))


def _execute(shell, inspectors, code):
    from fastcore.nbio import render_text
    try: note = _inspect(shell, inspectors, code)
    except Exception as e: return "blocked", _format_error("blocked", f"{type(e).__name__}: {e}")
    outputs = shell.run(code)
    return ("error" if shell.exc else "ok"), note + render_text(outputs)


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
    shell = CaptureShell(mpl_format=None, history=False)
    for name in ('nbopen','nbrun'): shell.register_magic_function(_magic_wrap(getattr(shell, name)), 'line', name)
    shell._clikernel_exit = False
    shell.ask_exit = lambda: _request_exit(shell)
    # execnb already captures the exception as a structured error output; suppress
    # IPython's own traceback print so it isn't duplicated (in colour) via stdout.
    shell.showtraceback = lambda *a, **k: None
    shell.showsyntaxerror = lambda *a, **k: None
    return shell


def _should_exit(shell): return getattr(shell, "_clikernel_exit", False)


def _next_line(stdin):
    "Read one line; when not a TTY, SIGINT while idle means 'interrupt execution', not 'kill the worker', so ignore it"
    while True:
        try: return stdin.readline()
        except KeyboardInterrupt:
            if stdin.isatty(): raise


def _tty_clear(stream, idx, mask, cc=None):
    "Clear `mask` bits in termios field `idx` when `stream` is a TTY, with optional `cc` char overrides; returns state for `_restore_termios`"
    if not stream.isatty(): return None
    fd = stream.fileno()
    attrs = termios.tcgetattr(fd)
    new_attrs = attrs[:]
    new_attrs[idx] &= ~mask
    if cc:
        new_attrs[6] = attrs[6][:]
        for k, v in cc.items(): new_attrs[6][k] = v
    termios.tcsetattr(fd, termios.TCSADRAIN, new_attrs)
    return fd, attrs


def _restore_termios(state):
    if state: termios.tcsetattr(state[0], termios.TCSADRAIN, state[1])


def main():
    # Establish our own SIGINT disposition rather than inherit the parent's: a supervisor that ignores
    # SIGINT would otherwise pass SIG_IGN down (inherited across exec), leaving this worker uninterruptible
    signal.signal(signal.SIGINT, signal.default_int_handler)
    print("please wait, loading...", flush=True)
    _set_default_dirs()
    shell = _make_shell()
    inspectors = _load_inspectors()
    # ONLCR off so protocol output stays bare LF; ECHO off (echoed input corrupts the protocol) and ICANON
    # off (canonical mode drops bytes past MAX_CANON with BEL spam; VMIN/VTIME make non-canonical reads
    # return per byte; ISIG stays on so ^C still interrupts)
    output_state = _tty_clear(sys.__stdout__, tty.OFLAG, termios.ONLCR)
    echo_state = _tty_clear(sys.stdin, tty.LFLAG, termios.ECHO | termios.ICANON, {termios.VMIN: 1, termios.VTIME: 0})
    delim = _new_delim()
    print("loading complete. first delimiter:", flush=True)
    _write_response(delim)
    try:
        while True:
            line = _next_line(sys.stdin)
            if not line: break
            line = line.rstrip("\n")
            if line == _MULTILINE:
                code, err = _read_block(sys.stdin, delim)
                if err:
                    _write_response(delim, _format_error("protocol-error", err))
                    continue
            else: code = line
            print(".", flush=True)
            try: _, outputs = _execute(shell, inspectors, code)
            except BaseException: outputs = _format_error("internal-error", traceback.format_exc())
            _write_response(delim, outputs)
            if _should_exit(shell): break
    finally:
        _restore_termios(echo_state)
        _restore_termios(output_state)


if __name__ == "__main__": main()
