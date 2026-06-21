import os,pty,re,select,shutil,subprocess,tempfile,time

import pytest

DELIM_RE = re.compile(r"--[A-Za-z0-9]{5}")
TIMEOUT = 5


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


def start_kernel(tmp_path):
    cmd = shutil.which("clikernel")
    assert cmd, "clikernel console script is not on PATH"
    env = os.environ.copy()
    state = os.path.join(tempfile.gettempdir(), f"clikernel-{os.getuid()}")
    env["CLIKERNEL_STATE_DIR"] = str(tmp_path / "state")
    env.setdefault("IPYTHONDIR", os.path.join(state, "ipython"))
    env.setdefault("MPLCONFIGDIR", os.path.join(state, "matplotlib"))
    env.setdefault("MPLBACKEND", "Agg")
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen([cmd], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    proc._stdout_buffer = bytearray()
    return proc


def start_kernel_pty(tmp_path):
    cmd = shutil.which("clikernel")
    assert cmd, "clikernel console script is not on PATH"
    env = os.environ.copy()
    state = os.path.join(tempfile.gettempdir(), f"clikernel-{os.getuid()}")
    env["CLIKERNEL_STATE_DIR"] = str(tmp_path / "state")
    env.setdefault("IPYTHONDIR", os.path.join(state, "ipython"))
    env.setdefault("MPLCONFIGDIR", os.path.join(state, "matplotlib"))
    env.setdefault("MPLBACKEND", "Agg")
    env["PYTHONUNBUFFERED"] = "1"
    master, slave = pty.openpty()
    try: proc = subprocess.Popen([cmd], stdin=slave, stdout=slave, stderr=subprocess.PIPE, env=env, close_fds=True)
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


@pytest.fixture
def kernel(tmp_path):
    proc = start_kernel(tmp_path)
    try:
        body, delim = read_until_ready(proc)
        yield proc, body, delim
    finally: stop_kernel(proc)


def test_startup_prints_valid_ready_delimiter(kernel):
    _, body, delim = kernel
    assert body == "please wait, loading...\nloading complete. first delimiter:\n"
    assert DELIM_RE.fullmatch(delim)


def test_single_line_request_returns_result_and_same_delimiter(kernel):
    proc, _, delim = kernel
    body, next_delim = send(proc, "1+1\n")
    assert body == "2\n"
    assert DELIM_RE.fullmatch(next_delim)
    assert next_delim == delim


def test_tty_input_is_not_echoed_after_startup(tmp_path):
    proc = start_kernel_pty(tmp_path)
    try:
        body, delim = read_pty_until_ready(proc)
        assert body == "please wait, loading...\nloading complete. first delimiter:\n"
        os.write(proc._pty_master, b"1+1\n")
        assert _read_ptyline(proc, TIMEOUT) == ".\n"
        body, next_delim = read_pty_until_ready(proc)
        assert body == "2\n"
        assert next_delim == delim
    finally: stop_kernel(proc)

def test_tty_output_keeps_newlines_as_lf(tmp_path):
    proc = start_kernel_pty(tmp_path)
    try:
        _, delim = read_pty_until_ready(proc)
        os.write(proc._pty_master, b"print('hello')\n")
        body, next_delim, raw_delim = read_pty_raw_until_ready(proc)
        assert body == b".\nhello\n"
        assert raw_delim == next_delim.encode() + b"\n"
        assert b"\r" not in body + raw_delim
        assert next_delim == delim
    finally: stop_kernel(proc)


def test_request_ack_is_written_before_result(kernel):
    proc, _, delim = kernel
    assert proc.stdin is not None
    proc.stdin.write(b"1+1\n")
    proc.stdin.flush()
    assert _readline(proc, TIMEOUT) == ".\n"
    body, next_delim = read_until_ready(proc)
    assert body == "2\n"
    assert next_delim == delim


def test_state_persists_across_requests(kernel):
    proc, _, _ = kernel
    body, _ = send(proc, "x=41\n")
    assert body == ""
    body, _ = send(proc, "x+1\n")
    assert body == "42\n"


def test_multiline_request_uses_current_delimiter(kernel):
    proc, _, delim = kernel
    body, _ = send(proc, f"--\ndef f(x):\n    return x + 1\n\nf(41)\n{delim}\n")
    assert body == "42\n"


def test_multiple_outputs_use_xmlish_blocks(kernel):
    proc, _, delim = kernel
    code = (
        "--\n"
        "from IPython.display import Markdown, display\n"
        "print('hello')\n"
        "display(Markdown('**shown**'))\n"
        "42\n"
        f"{delim}\n")
    body, _ = send(proc, code)
    assert '<stdout>\nhello\n</stdout>\n' in body
    assert '<display_data mime="text/markdown">\n**shown**\n</display_data>\n' in body
    assert '<execute_result>\n42\n</execute_result>\n' in body


def test_runtime_errors_return_error_text_and_same_delimiter(kernel):
    proc, _, delim = kernel
    body, next_delim = send(proc, "1/0\n")
    assert "ZeroDivisionError" in body
    assert DELIM_RE.fullmatch(next_delim)
    assert next_delim == delim


@pytest.mark.parametrize("cmd", ["exit()", "quit()"])
def test_exit_request_returns_final_delimiter_and_stops_process(kernel, cmd):
    proc, _, start_delim = kernel
    body, delim = send(proc, f"{cmd}\n")
    assert body == ""
    assert DELIM_RE.fullmatch(delim)
    assert delim == start_delim
    proc.wait(timeout=TIMEOUT)
    assert proc.returncode == 0


def test_history_is_disabled(kernel):
    proc, _, _ = kernel
    body, _ = send(proc, "get_ipython().history_manager.enabled\n")
    assert body == "False\n"
