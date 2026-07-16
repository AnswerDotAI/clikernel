"Kernel-agnostic core of clikernel: the stdin/stdout stream protocol, and the MCP supervisor for any worker speaking it."
import asyncio,atexit,os,re,secrets,signal,string,sys,termios,time,traceback,tty

_ALPHANUM = string.ascii_letters + string.digits
_MULTILINE = "--"
_MARKER = "loading complete. session delimiter:"


class RuleBlock(Exception):
    "Raised by an inspector to deliberately block a cell; any other inspector exception is a bug, and fails open"


def _new_delim(): return "--" + ''.join(secrets.choice(_ALPHANUM) for _ in range(5))


def _read_block(stdin, delim):
    lines = []
    for line in stdin:
        if line.rstrip("\n") == delim: return "".join(lines), None
        lines.append(line)
    return "", f"missing block terminator: {delim}"


def fmt_error(tag, text):
    nl = '' if text.endswith('\n') else '\n'
    return f"<{tag}>\n{text}{nl}</{tag}>"


def _write_response(delim, body=None):
    if body: print(body, end='' if body.endswith('\n') else '\n', flush=True)
    print(delim, flush=True)


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


def init_worker():
    "Set our own SIGINT disposition (a supervisor that ignores SIGINT would otherwise pass SIG_IGN down, leaving the worker uninterruptible) and announce loading"
    signal.signal(signal.SIGINT, signal.default_int_handler)
    print("please wait, loading...", flush=True)


def run_startup(
    path,   # Startup file to run in the persistent session, if it exists
    runner  # Callable `src -> (stdout, err)`: runs `src`, returning captured output and an error report (or None)
):
    "Run the startup file at `path` via `runner`, returning a `<startup file=...>` element with a `<source>` child and, when it printed anything, an `<output>` child; '' when the file is absent. Errors (returned or raised) are reported on stderr and don't stop the kernel."
    if not path.exists(): return ""
    src = path.read_text()
    try: out,err = runner(src)
    except Exception: out,err = "",traceback.format_exc()
    if err: print(f"clikernel: error running {path}:\n{err}", file=sys.stderr, flush=True)
    def _child(tag, body): return f'<{tag}>\n{body if body.endswith(chr(10)) else body+chr(10)}</{tag}>'
    children = _child("source", src) + ("\n" + _child("output", out) if out else "")
    return f'<startup file="{path}">\n{children}\n</startup>'


def serve_stream(
    execute,          # Callable `code -> str`: run one request, returning the rendered response body
    info="",          # Server info announced between the loading lines (forwarded to mcp `instructions`)
    should_exit=None  # Callable checked after each request; truthy stops the worker
):
    "Run the stream protocol on stdin/stdout: announce `info` and the session delimiter, then ack each request with '.', respond with `execute(code)`, and end each response with the delimiter"
    # ONLCR off so protocol output stays bare LF; ECHO off (echoed input corrupts the protocol) and ICANON
    # off (canonical mode drops bytes past MAX_CANON with BEL spam; VMIN/VTIME make non-canonical reads
    # return per byte; ISIG stays on so ^C still interrupts)
    output_state = _tty_clear(sys.__stdout__, tty.OFLAG, termios.ONLCR)
    echo_state = _tty_clear(sys.stdin, tty.LFLAG, termios.ECHO | termios.ICANON, {termios.VMIN: 1, termios.VTIME: 0})
    delim = _new_delim()
    print(info, flush=True)
    print(f"<stream-protocol>\nOne-line request: send the line; every response ends with the session delimiter line.\n"
        f"Multiline request (any multi-line cell, including %% cell magics), shown indented -- send it flush-left:\n"
        f"    --\n    <complete cell>\n    {delim}\ndoc(clikernel.skill) documents the full protocol.\n</stream-protocol>", flush=True)
    print(_MARKER, flush=True)
    _write_response(delim)
    try:
        while True:
            line = _next_line(sys.stdin)
            if not line: break
            line = line.rstrip("\n")
            if line == delim:
                _write_response(delim, fmt_error("protocol-error", "no multiline request is open: start one with a bare `--` line"))
                continue
            if line == _MULTILINE:
                code, err = _read_block(sys.stdin, delim)
                if err:
                    _write_response(delim, fmt_error("protocol-error", err))
                    continue
            elif line.startswith('%%'):
                _write_response(delim, fmt_error("protocol-error",
                    f"a %% cell magic needs a multiline request; send it as (flush-left):\n    --\n    {line}\n    <rest of cell>\n    {delim}"))
                continue
            else: code = line
            print(".", flush=True)
            try: body = execute(code)
            except BaseException: body = fmt_error("internal-error", traceback.format_exc())
            _write_response(delim, body)
            if should_exit and should_exit(): break
    finally:
        _restore_termios(echo_state)
        _restore_termios(output_state)


TOOL_DOCS = dict(
    execute="Run `code` in the persistent IPython session, keeping state across calls (imports, variables, monkeypatches, cached objects). If the kernel process has died since the last call, a fresh one is started automatically and the response notes that session state was lost.",
    restart="Kill the kernel process and start a fresh one: new pid, `sys.modules` genuinely reset, all session state (imports, variables, monkeypatches, cached objects) discarded. Use for a clean slate, after rebuilding a native extension, or after reloading a module that other already-imported modules had patched (symptoms: a stale-class bug where `isinstance`/`is` checks mysteriously fail, or a class is missing a method you know it has). Also works when `execute` is stuck: the stuck call returns an error and the kernel comes back fresh. After restarting, redo any imports/setup the task still needs.",
    interrupt="Interrupt the code the kernel is currently running (SIGINT, i.e. KeyboardInterrupt): the in-flight `execute` call returns with a KeyboardInterrupt traceback, and session state survives. Prefer this over `restart` when a call is merely taking too long. Only meaningful while an `execute` call is running.",
    died="NOTE: the kernel process had died; a fresh one was started, and all previous session state (imports, variables, monkeypatches) is gone.\n")


class _Worker:
    def __init__(self, argv=None, media=False):
        self.argv = argv or [sys.executable, "-m", "clikernel.cli"] + (["--media"] if media else [])
        self.proc,self.delim,self.started,self.busy,self.desynced = None,None,False,False,False
        self.startup_info = ""
        self.lock = asyncio.Lock()

    def alive(self): return self.proc is not None and self.proc.returncode is None

    async def start(self):
        PIPE = asyncio.subprocess.PIPE
        self.proc = await asyncio.create_subprocess_exec(*self.argv, limit=2**24, stdin=PIPE, stdout=PIPE)
        banner = []
        while True:
            line = (await self.proc.stdout.readline()).decode()
            if not line: raise RuntimeError("worker failed to start")
            if line.rstrip("\n") == _MARKER: break
            banner.append(line)
        self.delim = (await self.proc.stdout.readline()).decode().rstrip("\n")
        # banner[0] is "please wait, loading..."; the rest is the server info block (instructions + any
        # startup output), forwarded to the mcp `instructions` field minus the CLI-only <stream-protocol> element.
        info = "".join(banner[1:])
        self.startup_info = re.sub(r'<stream-protocol>.*?</stream-protocol>\n?', '', info, flags=re.S).strip()
        self.started,self.busy,self.desynced = True,False,False

    async def kill(self, grace=3):
        "SIGTERM first so the worker can clean up (e.g. shut down an interpreter it manages), SIGKILL if it lingers"
        if not self.alive(): return
        self.proc.terminate()
        try: await asyncio.wait_for(self.proc.wait(), grace)
        except asyncio.TimeoutError:
            self.proc.kill()
            await self.proc.wait()

    async def run(self, code):
        "Send `code`; return `(acked, body)`. `body` None means the worker died; retry is only safe if it never acked."
        msg = f"{_MULTILINE}\n{code}\n{self.delim}\n" if "\n" in code or code == _MULTILINE else code + "\n"
        try:
            self.proc.stdin.write(msg.encode())
            await self.proc.stdin.drain()
        except Exception: return False, None  # write failed before the worker accepted anything: safe to retry
        self.busy = True
        try:
            if not (await self.proc.stdout.readline()): return False, None  # "." ack
            lines = []
            while True:
                line = (await self.proc.stdout.readline()).decode()
                if not line: return True, None
                if line.rstrip("\n") == self.delim: return True, "".join(lines).removesuffix("\n")
                lines.append(line)
        except asyncio.CancelledError:
            self.desynced = True
            raise
        except Exception:
            self.desynced = True  # unexpected read failure (e.g. a line past the buffer limit): rebuild on the next call
            return True, None
        finally: self.busy = False


def _errbox(): return "<internal-error>\n" + traceback.format_exc() + "</internal-error>"


_MEDIA_RE = re.compile(r'\n?<media mime="([^"]+)">\n(.*?)\n</media>', re.S)
_IMG_MIMES = ('image/png','image/jpeg','image/gif','image/webp')  # preference order for choosing one image per output

def _split_media(body):
    "Split `<media>` elements out of a worker response into `(text, content blocks)`; images only, the rest is dropped"
    from mcp.types import ImageContent
    parts = _MEDIA_RE.findall(body)
    blocks = [ImageContent(type='image', data=d, mimeType=m) for m,d in parts if m in _IMG_MIMES]
    return (_MEDIA_RE.sub('', body) if parts else body), blocks


def _kill_worker(w, grace=3):
    "Reap the worker child so it can never outlive the supervisor (signal-handler safe: no await); SIGTERM first so it can clean up, SIGKILL if it lingers"
    p = w.proc
    if p is None or p.returncode is not None: return
    try: os.kill(p.pid, signal.SIGTERM)
    except OSError: return
    end = time.monotonic() + grace
    while time.monotonic() < end:
        try:
            if os.waitpid(p.pid, os.WNOHANG)[0]: return
        except ChildProcessError: return  # already reaped (e.g. by the event loop's child watcher)
        time.sleep(0.05)
    try: os.kill(p.pid, signal.SIGKILL)
    except OSError: pass


def _install_signal_guards(w):
    "A stray group SIGINT must not fell the supervisor; SIGTERM/SIGHUP shut down cleanly, always taking the worker with us (never orphan it)"
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    def _shutdown(signum, frame):
        _kill_worker(w)
        os._exit(0)
    for s in (signal.SIGTERM, signal.SIGHUP):
        try: signal.signal(s, _shutdown)
        except (ValueError, OSError): pass  # platform lacks the signal, or not on the main thread
    atexit.register(_kill_worker, w)


async def _serve(w, name, docs, instructions=None, eager=False):
    from mcp.server.fastmcp import FastMCP
    # When `eager`, start the worker before building the server so its banner (including startup output) is
    # forwarded as the `instructions` field -- read once, at initialize; a later restart won't refresh what the
    # client sees. Otherwise the worker stays unlaunched until first use and `instructions` is the static text.
    if eager:
        try: await w.start()
        except Exception:
            print(f"{name}: worker failed to start eagerly; retrying on first call\n" + traceback.format_exc(), file=sys.stderr, flush=True)
    mcp = FastMCP(name, instructions=(w.startup_info or instructions) or None)
    died = docs['died']

    async def execute(code:str  # Code to run in the persistent session
                     ):        # Rendered outputs (stdout, display data, last-expression result, errors), plus any rich media blocks
        try:
            async with w.lock:
                note = ""
                if w.desynced: await w.kill()
                if not w.alive():
                    if w.started: note = died
                    await w.start()
                acked, body = await w.run(code)
                if body is None and not acked:  # died before accepting the request: safe to retry on a fresh worker
                    note = died
                    await w.start()
                    acked, body = await w.run(code)
                if body is None:
                    return note + "<internal-error>\nkernel process died while executing this request; a fresh kernel will be started on the next call, with all session state lost\n</internal-error>"
                text, blocks = _split_media(note + body)
                return [text, *blocks] if blocks else text
        except Exception:
            w.desynced = True
            return _errbox()

    async def restart()->str:
        try:
            await w.kill()
            async with w.lock: await w.start()
            return "restarted"
        except Exception: return _errbox()

    async def interrupt()->str:
        try:
            if not (w.alive() and w.busy): return "nothing is running"
            w.proc.send_signal(signal.SIGINT)
            return "interrupt sent; the running `execute` call will return with a KeyboardInterrupt"
        except Exception: return _errbox()

    for f in (execute, restart, interrupt):
        f.__doc__ = docs[f.__name__]
        mcp.tool(structured_output=False)(f)
    await mcp.run_stdio_async()


def run_mcp(
    argv=None,         # Worker command line (default: the Python clikernel worker)
    name='clikernel',  # MCP server name
    docs=None,         # Overrides for `TOOL_DOCS` entries (tool descriptions and the state-lost note)
    instructions=None, # Static MCP `instructions` text, for when the worker isn't started eagerly
    eager=False,       # Start the worker at server startup, forwarding its banner (with startup output) as `instructions`?
    media=True,        # Forward rich display outputs (images) from the worker as MCP content blocks?
):
    "Run an MCP server supervising a persistent stream-protocol worker subprocess."
    w = _Worker(argv, media=media)
    _install_signal_guards(w)
    asyncio.run(_serve(w, name, {**TOOL_DOCS, **(docs or {})}, instructions, eager))
