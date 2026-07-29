import asyncio, json, os, shutil, signal, socket, subprocess, sys, tempfile, urllib.error, urllib.request
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from clikernel.base import _Worker, _install_signal_guards, _kill_worker


def _server_params(cwd=None, **extra_env):
    cmd = shutil.which("clikernel-mcp")
    args = [] if cmd else ["-m", "clikernel.mcp"]
    cmd = cmd or sys.executable
    env = dict(os.environ, CLIKERNEL_STATE_DIR=tempfile.mkdtemp(prefix="clikernel-mcp-test-"), **extra_env)
    return StdioServerParameters(command=cmd, args=args, env=env, cwd=cwd)


async def _text(s, name, **args):
    res = await s.call_tool(name, args)
    return res.content[0].text if res.content else ""


async def test_mcp(tmp_path):
    "One server through everything: execute semantics, magics, restart, interrupt, and worker-death recovery."
    async with stdio_client(_server_params()) as (r, w), ClientSession(r, w) as s:
        init = await s.initialize()
        assert "persistent IPython session" in (init.instructions or "")   # server info forwarded to instructions
        assert {t.name for t in (await s.list_tools()).tools} == {"execute", "restart", "interrupt"}

        # execute: results, top-level await, state, xmlish outputs, clean errors
        assert await _text(s, "execute", code="40+2") == "42"
        assert await _text(s, "execute", code="import asyncio\nawait asyncio.sleep(0)\n42") == "42"
        await _text(s, "execute", code="x = 41")
        assert await _text(s, "execute", code="x + 1") == "42"
        r_ = await _text(s, "execute", code="print('hi'); 99")
        assert "<stdout>\nhi\n</stdout>" in r_ and "<execute_result>\n99\n</execute_result>" in r_
        r_ = await _text(s, "execute", code="1/0")
        assert "ZeroDivisionError" in r_ and "\x1b[" not in r_ and r_.count("ZeroDivisionError") == 1

        # notebook magics
        cells = [dict(cell_type="code", id="aaa111", metadata={}, outputs=[], execution_count=None, source="print('one')")]
        nb = tmp_path/"t.ipynb"
        nb.write_text(json.dumps(dict(cells=cells, metadata={}, nbformat=4, nbformat_minor=5)))
        await _text(s, "execute", code=f"from aidialog.dlgskill import set_dlg; set_dlg('{nb}')")
        r_ = await _text(s, "execute", code="%nbrun aaa")
        assert "--- aaa111 ---" in r_ and "one" in r_

        # restart: clean return, fresh pid, sys.modules genuinely reset, kernel usable
        pid1 = int(await _text(s, "execute", code="import os, sys; sys.modules['fakemod'] = sys; os.getpid()"))
        assert await _text(s, "restart") == "restarted"
        pid2 = int(await _text(s, "execute", code="import os; os.getpid()"))
        assert pid2 != pid1
        assert await _text(s, "execute", code="import sys; 'fakemod' in sys.modules") == "False"
        assert "NameError" in await _text(s, "execute", code="x")

        # interrupt: idle reports so; a running execute returns KeyboardInterrupt and state survives
        assert "nothing" in (await _text(s, "interrupt")).lower()
        task = asyncio.create_task(s.call_tool("execute", {"code": "import time; time.sleep(30); 'fin'+'ished'"}))
        await asyncio.sleep(1)
        assert "interrupt" in (await _text(s, "interrupt")).lower()
        out = (await task).content[0].text
        assert "KeyboardInterrupt" in out and "finished" not in out
        assert await _text(s, "execute", code="40+2") == "42"

        # exit() run as code recycles the worker: next call notes lost state
        await _text(s, "execute", code="exit()")
        r_ = await _text(s, "execute", code="40+2")
        assert "42" in r_ and "state" in r_

        # externally killed while idle: next call self-heals with a note
        pid3 = int(await _text(s, "execute", code="import os; os.getpid()"))
        os.kill(pid3, signal.SIGKILL)
        r_ = await _text(s, "execute", code="40+2")
        assert "42" in r_ and "state" in r_

        # killed mid-execute: that call reports the death; the next one recovers
        pid4 = int(await _text(s, "execute", code="import os; os.getpid()"))
        task = asyncio.create_task(s.call_tool("execute", {"code": "import time; time.sleep(30)"}))
        await asyncio.sleep(1)
        os.kill(pid4, signal.SIGKILL)
        assert "died" in (await task).content[0].text
        r_ = await _text(s, "execute", code="40+2")
        assert "42" in r_


async def test_mcp_startup_instructions(tmp_path):
    "In a python-project cwd the worker starts eagerly: startup.py's captured stdout is forwarded into the mcp `instructions` field as a <startup> block."
    xdg = tmp_path/"xdg"
    (xdg/"clikernel").mkdir(parents=True)
    sp = xdg/"clikernel"/"startup.py"
    sp.write_text("import os  # SRC-ONLY-TOKEN\nprint('STARTUP-STDOUT-MARKER')\n")
    proj = tmp_path/"proj"
    proj.mkdir()
    (proj/"pyproject.toml").write_text("[project]\nname = 't'\n")
    async with stdio_client(_server_params(cwd=proj, XDG_CONFIG_HOME=str(xdg))) as (r, w), ClientSession(r, w) as s:
        init = await s.initialize()
        instr = init.instructions or ""
        assert "persistent IPython session" in instr
        assert f'<startup file="{sp}">' in instr and "</startup>" in instr
        assert "<source>" in instr and "SRC-ONLY-TOKEN" in instr             # source forwarded
        assert "<output>" in instr and "STARTUP-STDOUT-MARKER" in instr       # stdout forwarded
        assert "<stream-protocol>" not in instr                                  # CLI framing help is CLI-only


async def test_mcp_lazy_outside_project(tmp_path):
    "Without a pyproject.toml in cwd the worker stays unlaunched at initialize: instructions fall back to the static text, with no startup block."
    xdg = tmp_path/"xdg"
    (xdg/"clikernel").mkdir(parents=True)
    (xdg/"clikernel"/"startup.py").write_text("print('STARTUP-STDOUT-MARKER')\n")
    plain = tmp_path/"plain"
    plain.mkdir()
    async with stdio_client(_server_params(cwd=plain, XDG_CONFIG_HOME=str(xdg))) as (r, w), ClientSession(r, w) as s:
        init = await s.initialize()
        instr = init.instructions or ""
        assert "persistent IPython session" in instr           # static fallback text
        assert "STARTUP-STDOUT-MARKER" not in instr and "<startup" not in instr
        assert await _text(s, "execute", code="40+2") == "42"  # worker launches on first use


async def test_supervisor_guards(monkeypatch, tmp_path):
    "SIGINT can't fell the supervisor, SIGTERM/SIGHUP get a clean-shutdown handler, and the worker child is reaped so it never outlives us."
    monkeypatch.setenv("CLIKERNEL_STATE_DIR", str(tmp_path))
    orig = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    w = _Worker()
    try:
        await w.start()
        pid = w.proc.pid
        _install_signal_guards(w)
        assert signal.getsignal(signal.SIGINT) is signal.SIG_IGN
        for s in (signal.SIGTERM, signal.SIGHUP):
            assert callable(signal.getsignal(s)) and signal.getsignal(s) not in (signal.SIG_DFL, signal.SIG_IGN)
        _kill_worker(w)
        await w.proc.wait()
        with pytest.raises(ProcessLookupError): os.kill(pid, 0)
    finally:
        for s, h in orig.items(): signal.signal(s, h)
        await w.kill()


FAKE_WORKER = """
import signal, sys, time
def bye(sig, frame):
    open(sys.argv[1], "w").write("cleaned")
    sys.exit(0)
signal.signal(signal.SIGTERM, bye)
print("please wait, loading...", flush=True)
print("loading complete. session delimiter:", flush=True)
print("--test1", flush=True)
while True: time.sleep(1)
"""

async def test_graceful_kill(tmp_path):
    "Killing the worker sends SIGTERM first so it can clean up (e.g. shut down an interpreter it manages), SIGKILL only if it lingers."
    script = tmp_path/"w.py"
    script.write_text(FAKE_WORKER)
    m1, m2 = tmp_path/"m1", tmp_path/"m2"
    w = _Worker([sys.executable, str(script), str(m1)])
    await w.start()
    await w.kill()                                   # async path (restart tool, desync recovery)
    assert m1.read_text() == "cleaned"
    w = _Worker([sys.executable, str(script), str(m2)])
    await w.start()
    _kill_worker(w)                                  # sync path (signal handler, atexit)
    await w.proc.wait()
    assert m2.read_text() == "cleaned"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url, token=None, host=None):
    "POST to `url`, returning the HTTP status (auth is checked before MCP parses anything)"
    hdrs = {"Content-Type": "application/json"}
    if token: hdrs["Authorization"] = f"Bearer {token}"
    if host: hdrs["Host"] = host
    req = urllib.request.Request(url, data=b"{}", headers=hdrs)
    try: return urllib.request.urlopen(req, timeout=10).status
    except urllib.error.HTTPError as e: return e.code


async def test_http_auth(tmp_path):
    "The streamable-http transport serves the same tools, behind a bearer token that unauthorized requests can't skip."
    from mcp.client.streamable_http import streamable_http_client, create_mcp_http_client
    port, tok = _free_port(), "test-token"
    cmd = shutil.which("clikernel-mcp")
    argv = ([cmd] if cmd else [sys.executable, "-m", "clikernel.mcp"]) + ["--transport", "streamable-http", "--port", str(port)]
    env = dict(os.environ, CLIKERNEL_TOKEN=tok, CLIKERNEL_STATE_DIR=str(tmp_path))
    proc = subprocess.Popen(argv, env=env, cwd=tmp_path)
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5): break
            except OSError: await asyncio.sleep(0.1)
        assert await asyncio.to_thread(_post, url) == 401                   # no token
        assert await asyncio.to_thread(_post, url, "wrong-token") == 401    # wrong token
        assert await asyncio.to_thread(_post, url, tok, "example.com") \
            == await asyncio.to_thread(_post, url, tok)                 # a foreign Host is not the server's business: it binds a public interface
        async with create_mcp_http_client(headers={"Authorization": f"Bearer {tok}"}) as hc, \
                streamable_http_client(url, http_client=hc) as streams, \
                ClientSession(*streams[:2]) as s:   # mcp 2.x drops the session-id callback from the tuple
            await s.initialize()
            assert {t.name for t in (await s.list_tools()).tools} == {"execute", "restart", "interrupt"}
            await _text(s, "execute", code="x = 41")
            assert await _text(s, "execute", code="x + 1") == "42"      # state persists across HTTP calls
    finally:
        proc.terminate()
        proc.wait(timeout=10)

