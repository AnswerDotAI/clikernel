"MCP server supervising a persistent `clikernel` CLI worker subprocess."
import asyncio,atexit,os,signal,sys,traceback

_MARKER = "loading complete. first delimiter:"
_DIED = "NOTE: the kernel process had died; a fresh one was started, and all previous session state (imports, variables, monkeypatches) is gone.\n"
_MULTILINE = "--"


class _Worker:
    def __init__(self):
        self.proc,self.delim,self.started,self.busy,self.desynced = None,None,False,False,False
        self.startup_info = ""
        self.lock = asyncio.Lock()

    def alive(self): return self.proc is not None and self.proc.returncode is None

    async def start(self):
        PIPE = asyncio.subprocess.PIPE
        self.proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "clikernel.cli", limit=2**24, stdin=PIPE, stdout=PIPE)
        banner = []
        while True:
            line = (await self.proc.stdout.readline()).decode()
            if not line: raise RuntimeError("clikernel worker failed to start")
            if line.rstrip("\n") == _MARKER: break
            banner.append(line)
        self.delim = (await self.proc.stdout.readline()).decode().rstrip("\n")
        # banner[0] is "please wait, loading..."; the rest is the server info block (INSTRUCTIONS + any
        # startup.py output), forwarded verbatim to the mcp `instructions` field.
        self.startup_info = "".join(banner[1:]).strip()
        self.started,self.busy,self.desynced = True,False,False

    async def kill(self):
        if self.alive():
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


def _kill_worker(w):
    "Reap the worker child so it can never outlive the supervisor (signal-handler safe: no await)"
    p = w.proc
    if p is not None and p.returncode is None:
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


def main():
    w = _Worker()
    _install_signal_guards(w)
    asyncio.run(_serve(w))


async def _serve(w):
    from mcp.server.fastmcp import FastMCP
    # Start the worker before building the server so startup.py output is captured and forwarded as the
    # `instructions` field. It's read once, at initialize; a later restart won't refresh what the client sees.
    try: await w.start()
    except Exception:
        print("clikernel-mcp: worker failed to start eagerly; retrying on first call\n" + traceback.format_exc(), file=sys.stderr, flush=True)
    mcp = FastMCP("clikernel", instructions=w.startup_info or None)

    @mcp.tool(structured_output=False)
    async def execute(code:str  # IPython-compatible code to run in the persistent session
                     )->str:   # Rendered outputs (stdout, display data, last-expression result, errors)
        "Run `code` in the persistent IPython session, keeping state across calls (imports, variables, monkeypatches, cached objects). If the kernel process has died since the last call, a fresh one is started automatically and the response notes that session state was lost."
        try:
            async with w.lock:
                note = ""
                if w.desynced: await w.kill()
                if not w.alive():
                    if w.started: note = _DIED
                    await w.start()
                acked, body = await w.run(code)
                if body is None and not acked:  # died before accepting the request: safe to retry on a fresh worker
                    note = _DIED
                    await w.start()
                    acked, body = await w.run(code)
                if body is None:
                    return note + "<internal-error>\nkernel process died while executing this request; a fresh kernel will be started on the next call, with all session state lost\n</internal-error>"
                return note + body
        except Exception:
            w.desynced = True
            return _errbox()

    @mcp.tool(structured_output=False)
    async def restart()->str:
        "Kill the kernel process and start a fresh one: new pid, `sys.modules` genuinely reset, all session state (imports, variables, monkeypatches, cached objects) discarded. Use for a clean slate, after rebuilding a native extension, or after reloading a module that other already-imported modules had patched (symptoms: a stale-class bug where `isinstance`/`is` checks mysteriously fail, or a class is missing a method you know it has). Also works when `execute` is stuck: the stuck call returns an error and the kernel comes back fresh. After restarting, redo any imports/setup the task still needs."
        try:
            await w.kill()
            async with w.lock: await w.start()
            return "restarted"
        except Exception: return _errbox()

    @mcp.tool(structured_output=False)
    async def interrupt()->str:
        "Interrupt the code the kernel is currently running (SIGINT, i.e. KeyboardInterrupt): the in-flight `execute` call returns with a KeyboardInterrupt traceback, and session state survives. Prefer this over `restart` when a call is merely taking too long. Only meaningful while an `execute` call is running."
        try:
            if not (w.alive() and w.busy): return "nothing is running"
            w.proc.send_signal(signal.SIGINT)
            return "interrupt sent; the running `execute` call will return with a KeyboardInterrupt"
        except Exception: return _errbox()

    await mcp.run_stdio_async()


if __name__ == "__main__": main()
