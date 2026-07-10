import json,os,pty,re,select,shutil,signal,subprocess,tempfile,time

DELIM_RE = re.compile(r"--[A-Za-z0-9]{5}")
TIMEOUT = 5


def test_state_root(tmp_path, monkeypatch):
    "Persistent by default (completion ids must outlive tmp cleaners); env override wins"
    from clikernel.cli import _state_root
    from fastcore.xdg import xdg_state_home
    monkeypatch.delenv("CLIKERNEL_STATE_DIR", raising=False)
    assert _state_root() == xdg_state_home()/'clikernel'
    monkeypatch.setenv("CLIKERNEL_STATE_DIR", str(tmp_path))
    assert _state_root() == tmp_path


def test_fmt_error():
    "fmt_error closes the tag on its own line whether or not `text` ends with a newline"
    from clikernel.base import fmt_error
    assert fmt_error("error", "boom") == "<error>\nboom\n</error>"
    assert fmt_error("error", "boom\n") == "<error>\nboom\n</error>"


def _failure_detail(proc):
    if proc.stderr is None: return ""
    ready, _, _ = select.select([proc.stderr], [], [], 0)
    if not ready: return ""
    err = os.read(proc.stderr.fileno(), 65536).decode("utf-8", "replace")
    return f"\nstderr:\n{err}" if err else ""


def _readline(proc, timeout):
    assert proc.stdout is not None
    buf = proc._stdout_buffer
    while b"\n" not in buf:
        ready, _, _ = select.select([proc.stdout], [], [], timeout)
        if not ready: raise AssertionError(f"timed out waiting for clikernel output{_failure_detail(proc)}")
        chunk = os.read(proc.stdout.fileno(), 4096)
        assert chunk, _failure_detail(proc)
        buf.extend(chunk)
    line, _, rest = buf.partition(b"\n")
    proc._stdout_buffer = bytearray(rest)
    return line.decode("utf-8", "replace") + "\n"


def read_until_ready(proc, timeout=TIMEOUT):
    lines = []
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise AssertionError(f"timed out waiting for ready delimiter{_failure_detail(proc)}")
        line = _readline(proc, remaining)
        s = line.rstrip("\n")
        if DELIM_RE.fullmatch(s): return "".join(lines), s
        lines.append(line)


def _env(tmp_path):
    env = os.environ.copy()
    state = os.path.join(tempfile.gettempdir(), f"clikernel-{os.getuid()}")
    env["CLIKERNEL_STATE_DIR"] = str(tmp_path / "state")
    env["IPYTHONDIR"] = str(tmp_path / "ipython")   # isolate from the user's real profile
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")  # ...and from their clikernel startup.py
    env.setdefault("MPLCONFIGDIR", os.path.join(state, "matplotlib"))
    env.setdefault("MPLBACKEND", "Agg")
    env["PYTHONUNBUFFERED"] = "1"
    return env


def start_kernel(tmp_path, extra_env=None):
    cmd = shutil.which("clikernel")
    assert cmd, "clikernel console script is not on PATH"
    env = _env(tmp_path)
    if extra_env: env.update(extra_env)
    proc = subprocess.Popen([cmd], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    proc._stdout_buffer = bytearray()
    return proc


def start_kernel_pty(tmp_path):
    cmd = shutil.which("clikernel")
    assert cmd, "clikernel console script is not on PATH"
    master, slave = pty.openpty()
    try: proc = subprocess.Popen([cmd], stdin=slave, stdout=slave, stderr=subprocess.PIPE, env=_env(tmp_path), close_fds=True)
    finally: os.close(slave)
    proc._pty_master = master
    proc._pty_buffer = bytearray()
    return proc


def stop_kernel(proc):
    if proc.stdin is not None:
        try: proc.stdin.close()
        except OSError: pass
    if hasattr(proc, "_pty_master"):
        try: os.close(proc._pty_master)
        except OSError: pass
    if proc.poll() is None:
        try: proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try: proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1)


def send(proc, text, timeout=TIMEOUT):
    assert proc.stdin is not None
    proc.stdin.write(text.encode("utf-8"))
    proc.stdin.flush()
    assert _readline(proc, timeout) == ".\n"
    return read_until_ready(proc, timeout)


def _read_ptyline(proc, timeout):
    buf = proc._pty_buffer
    while b"\n" not in buf:
        ready, _, _ = select.select([proc._pty_master], [], [], timeout)
        if not ready: raise AssertionError(f"timed out waiting for clikernel pty output{_failure_detail(proc)}")
        chunk = os.read(proc._pty_master, 4096)
        assert chunk, _failure_detail(proc)
        buf.extend(chunk)
    line, _, rest = buf.partition(b"\n")
    proc._pty_buffer = bytearray(rest)
    return line.decode("utf-8", "replace").rstrip("\r") + "\n"


def read_pty_until_ready(proc, timeout=TIMEOUT):
    lines = []
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise AssertionError(f"timed out waiting for ready delimiter{_failure_detail(proc)}")
        line = _read_ptyline(proc, remaining)
        s = line.rstrip("\n")
        if DELIM_RE.fullmatch(s): return "".join(lines), s
        lines.append(line)


def _read_pty_rawline(proc, timeout):
    buf = proc._pty_buffer
    while b"\n" not in buf:
        ready, _, _ = select.select([proc._pty_master], [], [], timeout)
        if not ready: raise AssertionError(f"timed out waiting for clikernel pty output{_failure_detail(proc)}")
        chunk = os.read(proc._pty_master, 4096)
        assert chunk, _failure_detail(proc)
        buf.extend(chunk)
    line, _, rest = buf.partition(b"\n")
    proc._pty_buffer = bytearray(rest)
    return bytes(line + b"\n")


def read_pty_raw_until_ready(proc, timeout=TIMEOUT):
    body = bytearray()
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise AssertionError(f"timed out waiting for ready delimiter{_failure_detail(proc)}")
        line = _read_pty_rawline(proc, remaining)
        s = line.rstrip(b"\r\n").decode("utf-8", "replace")
        if DELIM_RE.fullmatch(s): return bytes(body), s, line
        body.extend(line)


NB_CELLS = [("aaa111", "x = 41\nprint('one')"),
    ("bbb222", "#| export\nprint('two', x + 1)"),
    ("ccc333", "print('three')")]

def make_nb(path):
    cells = [dict(cell_type="code", id=i, metadata={}, outputs=[], execution_count=None, source=src) for i,src in NB_CELLS]
    path.write_text(json.dumps(dict(cells=cells, metadata={}, nbformat=4, nbformat_minor=5)))
    return path


def test_cli(tmp_path):
    "One pipe-driven worker through the whole protocol, ending with exit(); then a fresh worker for quit()."
    proc = start_kernel(tmp_path)
    try:
        body, delim = read_until_ready(proc)
        assert body.startswith("please wait, loading...\n")           # server info announced between the loading lines
        assert "persistent IPython session" in body
        assert body.endswith("loading complete. first delimiter:\n")
        assert DELIM_RE.fullmatch(delim)

        # ack arrives before the result; result then same delimiter
        proc.stdin.write(b"1+1\n")
        proc.stdin.flush()
        assert _readline(proc, TIMEOUT) == ".\n"
        body, nd = read_until_ready(proc)
        assert body == "2\n" and nd == delim

        # state persists
        assert send(proc, "x=41\n")[0] == ""
        assert send(proc, "x+1\n")[0] == "42\n"

        # multiline block; multiple outputs use xmlish blocks
        assert send(proc, f"--\ndef f(x):\n    return x + 1\n\nf(41)\n{delim}\n")[0] == "42\n"
        code = ("--\nfrom IPython.display import Markdown, display\nprint('hello')\n"
            f"display(Markdown('**shown**'))\n42\n{delim}\n")
        body, _ = send(proc, code)
        assert '<stdout>\nhello\n</stdout>\n' in body
        assert '<display_data mime="text/markdown">' in body and '**shown**' in body
        assert '<execute_result>\n42\n</execute_result>\n' in body

        # errors: clean, single traceback, no ansi, genuine stdout preserved
        body, nd = send(proc, "1/0\n")
        assert "ZeroDivisionError" in body and nd == delim
        assert "\x1b[" not in body and body.count("ZeroDivisionError") == 1 and "<stdout>" not in body
        body, _ = send(proc, f"--\nprint('before')\n1/0\n{delim}\n")
        assert "<stdout>\nbefore\n</stdout>" in body and body.count("ZeroDivisionError") == 1

        assert send(proc, "get_ipython().history_manager.enabled\n")[0] == "False\n"

        # SIGINT: ignored while idle (non-tty); interrupts running code
        time.sleep(0.2)
        proc.send_signal(signal.SIGINT)
        time.sleep(0.2)
        assert proc.poll() is None
        assert send(proc, "1+1\n")[0] == "2\n"
        proc.stdin.write(b"import time; time.sleep(30)\n")
        proc.stdin.flush()
        assert _readline(proc, TIMEOUT) == ".\n"
        time.sleep(0.3)
        proc.send_signal(signal.SIGINT)
        body, _ = read_until_ready(proc)
        assert "KeyboardInterrupt" in body
        assert send(proc, "1+1\n")[0] == "2\n"

        # notebook magics
        nb = make_nb(tmp_path/"t.ipynb")
        assert "error" not in send(proc, f"%nbopen {nb}\n")[0].lower()
        body, _ = send(proc, "%nbrun aaa\n")
        assert "--- aaa111 ---" in body and "one" in body
        body, _ = send(proc, "%nbrun bbb222 --above\n")
        assert "one" in body and "two 42" in body
        body, _ = send(proc, "%nbrun --all --exported\n")
        assert "two 42" in body and "one" not in body and "three" not in body

        # exit(): empty body, final delimiter, clean stop
        body, nd = send(proc, "exit()\n")
        assert body == "" and nd == delim
        proc.wait(timeout=TIMEOUT)
        assert proc.returncode == 0
    finally: stop_kernel(proc)

    proc = start_kernel(tmp_path)
    try:
        _, delim = read_until_ready(proc)
        body, nd = send(proc, "quit()\n")
        assert body == "" and nd == delim
        proc.wait(timeout=TIMEOUT)
        assert proc.returncode == 0
    finally: stop_kernel(proc)


def test_cli_tty(tmp_path):
    "One pty-driven worker: input isn't echoed, and output newlines stay LF (no ONLCR CR)."
    proc = start_kernel_pty(tmp_path)
    try:
        body, delim = read_pty_until_ready(proc)
        assert body.startswith("please wait, loading...\n") and body.endswith("loading complete. first delimiter:\n")
        os.write(proc._pty_master, b"1+1\n")
        assert _read_ptyline(proc, TIMEOUT) == ".\n"
        body, nd = read_pty_until_ready(proc)
        assert body == "2\n" and nd == delim
        os.write(proc._pty_master, b"print('hello')\n")
        body, nd2, raw_delim = read_pty_raw_until_ready(proc)
        assert body == b".\nhello\n"
        assert raw_delim == nd2.encode() + b"\n"
        assert b"\r" not in body + raw_delim
        assert nd2 == delim

        # long lines must survive the pty: canonical mode drops bytes past MAX_CANON and spams BEL
        os.write(proc._pty_master, f"--\ns = 'b' * 2\ns += 'b{'b' * 5000}'\nlen(s)\n{delim}\n".encode())
        assert _read_ptyline(proc, TIMEOUT) == ".\n"
        body, nd = read_pty_until_ready(proc)
        assert body == "5003\n" and nd == delim
    finally: stop_kernel(proc)


INSPECTORS_SRC = r'''
import ast
def inspect(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name == "subprocess" for a in n.names):
            return "<reminder>\nuse the Bash tool, not subprocess\n</reminder>\n"
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "blockme":
            raise RuntimeError("blocked by policy")
def inspect2(tree, src):
    if "MARKER2ARG" in src: return "<reminder>\nsaw the source\n</reminder>\n"
inspectors = [inspect2]
'''

def test_cli_inspectors(tmp_path):
    "Inspectors loaded from XDG inspectors.py: a returned note is prepended to output, and a raising inspector blocks the cell before it runs."
    xdg = tmp_path/"xdg"
    (xdg/"clikernel").mkdir(parents=True)
    (xdg/"clikernel"/"inspectors.py").write_text(INSPECTORS_SRC)
    proc = start_kernel(tmp_path, {"XDG_CONFIG_HOME": str(xdg)})
    try:
        read_until_ready(proc)
        body, _ = send(proc, "import subprocess\n")
        assert "use the Bash tool" in body                         # note prepended, cell still ran (no error)
        assert send(proc, "1+1\n")[0] == "2\n"                     # unrelated cell: no note
        body, _ = send(proc, "blockme()\n")
        assert "blocked by policy" in body and "NameError" not in body  # blocked before running
        body, _ = send(proc, "x = 'MARKER2ARG'\n")
        assert "saw the source" in body                            # two-arg inspectors also receive the raw cell source
    finally: stop_kernel(proc)


STARTUP_SRC = "from functools import reduce  # SRC-ONLY-TOKEN\nprint('STARTUP-STDOUT-MARKER')\nGREETING = 'hi from startup'\n"

def test_cli_startup(tmp_path):
    "startup.py from XDG runs in the persistent session (imports/names available to later requests); the banner carries a <startup file=...> element with a <source> child always and an <output> child only when it prints; a broken startup.py is reported but doesn't stop the kernel."
    xdg = tmp_path/"xdg"
    (xdg/"clikernel").mkdir(parents=True)
    sp = xdg/"clikernel"/"startup.py"
    sp.write_text(STARTUP_SRC)
    proc = start_kernel(tmp_path, {"XDG_CONFIG_HOME": str(xdg)})
    try:
        body, _ = read_until_ready(proc)
        assert f'<startup file="{sp}">' in body and "</startup>" in body
        assert "<source>" in body and "SRC-ONLY-TOKEN" in body            # whole source in banner
        assert "<output>" in body and "STARTUP-STDOUT-MARKER" in body      # stdout child present
        assert send(proc, "GREETING\n")[0] == "'hi from startup'\n"      # name defined at startup persists
        assert send(proc, "reduce(lambda a,b:a+b, [1,2,3])\n")[0] == "6\n"  # import from startup persists
    finally: stop_kernel(proc)

    (xdg/"clikernel"/"startup.py").write_text("SILENT = 1\n")             # imports/defs but prints nothing
    proc = start_kernel(tmp_path, {"XDG_CONFIG_HOME": str(xdg)})
    try:
        body, _ = read_until_ready(proc)
        assert f'<startup file="{sp}">' in body and "<source>" in body and "<output>" not in body  # source always, output only if printed
    finally: stop_kernel(proc)

    (xdg/"clikernel"/"startup.py").write_text("raise RuntimeError('boom')\n")
    proc = start_kernel(tmp_path, {"XDG_CONFIG_HOME": str(xdg)})
    try:
        read_until_ready(proc)                                          # broken startup.py doesn't stop the kernel
        assert send(proc, "1+1\n")[0] == "2\n"
    finally: stop_kernel(proc)


def test_cli_profile(tmp_path):
    "The IPython profile (extensions + startup files) is loaded by default, like ipykernel"
    ipd = tmp_path/"ipython"
    pd = ipd/"profile_default"
    (pd/"startup").mkdir(parents=True)
    (pd/"startup"/"00-prof.py").write_text("prof_ran = 7\n")
    (pd/"ipython_kernel_config.py").write_text("c.InteractiveShellApp.extensions.append('_ck_ext')\n")
    (tmp_path/"_ck_ext.py").write_text("def load_ipython_extension(ip): ip.user_ns['ck_ext'] = 1\n")
    proc = start_kernel(tmp_path, {"IPYTHONDIR": str(ipd), "PYTHONPATH": str(tmp_path)})
    try:
        read_until_ready(proc)
        assert send(proc, "prof_ran\n")[0] == "7\n"
        assert send(proc, "ck_ext\n")[0] == "1\n"
    finally: stop_kernel(proc)
