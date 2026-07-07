import asyncio, json, os, shutil, signal, sys, tempfile
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from clikernel.mcp import _Worker, _install_signal_guards, _kill_worker


def _server_params(**extra_env):
    cmd = shutil.which("clikernel-mcp")
    args = [] if cmd else ["-m", "clikernel.mcp"]
    cmd = cmd or sys.executable
    env = dict(os.environ, CLIKERNEL_STATE_DIR=tempfile.mkdtemp(prefix="clikernel-mcp-test-"), **extra_env)
    return StdioServerParameters(command=cmd, args=args, env=env)


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
        await _text(s, "execute", code=f"%nbopen {nb}")
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
    "A startup.py's captured stdout is forwarded into the mcp `instructions` field as a <startup> block."
    xdg = tmp_path/"xdg"
    (xdg/"clikernel").mkdir(parents=True)
    sp = xdg/"clikernel"/"startup.py"
    sp.write_text("import os  # SRC-ONLY-TOKEN\nprint('STARTUP-STDOUT-MARKER')\n")
    async with stdio_client(_server_params(XDG_CONFIG_HOME=str(xdg))) as (r, w), ClientSession(r, w) as s:
        init = await s.initialize()
        instr = init.instructions or ""
        assert "persistent IPython session" in instr
        assert f'<startup file="{sp}">' in instr and "</startup>" in instr
        assert "<source>" in instr and "SRC-ONLY-TOKEN" in instr             # source forwarded
        assert "<output>" in instr and "STARTUP-STDOUT-MARKER" in instr       # stdout forwarded


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
