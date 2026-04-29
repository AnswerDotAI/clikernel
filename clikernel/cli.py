print("please wait, loading...", flush=True)
import os,secrets,string,sys,tempfile,termios,traceback
from pathlib import Path

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


_set_default_dirs()


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


def _execute(shell, code):
    from fastcore.nbio import render_text
    outputs = shell.run(code)
    return ("error" if shell.exc else "ok"), render_text(outputs)


def _request_exit(shell): shell._clikernel_exit = True


def _make_shell():
    from execnb.shell import CaptureShell
    shell = CaptureShell(mpl_format=None, history=False)
    shell._clikernel_exit = False
    shell.ask_exit = lambda: _request_exit(shell)
    return shell


def _should_exit(shell): return getattr(shell, "_clikernel_exit", False)


def _disable_echo():
    if not sys.stdin.isatty(): return None
    fd = sys.stdin.fileno()
    attrs = termios.tcgetattr(fd)
    new_attrs = attrs[:]
    new_attrs[3] &= ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSADRAIN, new_attrs)
    return fd, attrs


def _restore_echo(state):
    if state: termios.tcsetattr(state[0], termios.TCSADRAIN, state[1])


def main():
    echo_state = _disable_echo()
    shell = _make_shell()
    delim = _new_delim()
    print("loading complete. first delimiter:", flush=True)
    _write_response(delim)
    try:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if line == _MULTILINE:
                code, err = _read_block(sys.stdin, delim)
                if err:
                    delim = _new_delim()
                    _write_response(delim, _format_error("protocol-error", err))
                    continue
            else: code = line
            try: _, outputs = _execute(shell, code)
            except BaseException: outputs = _format_error("internal-error", traceback.format_exc())
            delim = _new_delim()
            _write_response(delim, outputs)
            if _should_exit(shell): break
    finally: _restore_echo(echo_state)


if __name__ == "__main__": main()
