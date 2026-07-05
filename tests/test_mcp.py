import asyncio,os,shutil,signal,sys,tempfile

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_params():
    cmd = shutil.which("clikernel-mcp")
    args = [] if cmd else ["-m", "clikernel.mcp"]
    cmd = cmd or sys.executable
    env = dict(os.environ, CLIKERNEL_STATE_DIR=tempfile.mkdtemp(prefix="clikernel-mcp-test-"))
    return StdioServerParameters(command=cmd, args=args, env=env)


async def _drive(codes):
    "Run each code string through the execute tool in one session; return result texts."
    async with stdio_client(_server_params()) as (r,w), ClientSession(r,w) as s:
        await s.initialize()
        out = []
        for c in codes:
            res = await s.call_tool("execute", {"code": c})
            out.append(res.content[0].text if res.content else "")
        return out


async def _drive_ops(ops):
    "Run a mix of ('execute', code) / ('restart',) ops in one session; return result texts."
    async with stdio_client(_server_params()) as (r,w), ClientSession(r,w) as s:
        await s.initialize()
        out = []
        for op in ops:
            name, args = (op[0], {"code": op[1]}) if op[0] == "execute" else (op[0], {})
            res = await s.call_tool(name, args)
            out.append(res.content[0].text if res.content else "")
        return out


@pytest.mark.anyio
async def test_execute_returns_result(): assert await _drive(["40+2"]) == ["42"]


@pytest.mark.anyio
async def test_execute_supports_top_level_await():
    r = await _drive(["import asyncio\nawait asyncio.sleep(0)\n42"])
    assert r == ["42"]


@pytest.mark.anyio
async def test_state_persists_across_calls(): assert (await _drive(["x = 41", "x + 1"]))[1] == "42"


@pytest.mark.anyio
async def test_multiple_outputs_use_xmlish_blocks():
    r = (await _drive(["print('hi'); 99"]))[0]
    assert "<stdout>\nhi\n</stdout>" in r
    assert "<execute_result>\n99\n</execute_result>" in r


@pytest.mark.anyio
async def test_error_is_clean():
    r = (await _drive(["1/0"]))[0]
    assert "ZeroDivisionError" in r
    assert "\x1b[" not in r
    assert r.count("ZeroDivisionError") == 1


@pytest.mark.anyio
async def test_tools_are_execute_restart_interrupt():
    async with stdio_client(_server_params()) as (r,w), ClientSession(r,w) as s:
        await s.initialize()
        assert {t.name for t in (await s.list_tools()).tools} == {"execute","restart","interrupt"}


@pytest.mark.anyio
async def test_restart_gives_fresh_process():
    r = await _drive_ops([("execute","import os; os.getpid()"), ("restart",), ("execute","import os; os.getpid()")])
    assert r[1] == "restarted"
    assert r[0] != r[2]


@pytest.mark.anyio
async def test_restart_resets_sys_modules():
    r = await _drive_ops([("execute","import sys; sys.modules['fakemod'] = sys"), ("restart",),
                          ("execute","import sys; 'fakemod' in sys.modules")])
    assert r[2] == "False"


@pytest.mark.anyio
async def test_interrupt_stops_running_code():
    async with stdio_client(_server_params()) as (r,w), ClientSession(r,w) as s:
        await s.initialize()
        await s.call_tool("execute", {"code": "import time"})
        task = asyncio.create_task(s.call_tool("execute", {"code": "time.sleep(30); 'fin'+'ished'"}))
        await asyncio.sleep(1)
        ir = (await s.call_tool("interrupt", {})).content[0].text
        assert "interrupt" in ir.lower()
        out = (await task).content[0].text
        assert "KeyboardInterrupt" in out and "finished" not in out
        res = await s.call_tool("execute", {"code": "40+2"})
        assert res.content[0].text == "42"


@pytest.mark.anyio
async def test_interrupt_when_idle():
    r = await _drive_ops([("execute","1"), ("interrupt",)])
    assert "nothing" in r[1].lower()


@pytest.mark.anyio
async def test_recovers_from_killed_worker():
    async with stdio_client(_server_params()) as (r,w), ClientSession(r,w) as s:
        await s.initialize()
        pid = int((await s.call_tool("execute", {"code": "import os; os.getpid()"})).content[0].text)
        os.kill(pid, signal.SIGKILL)
        res = (await s.call_tool("execute", {"code": "40+2"})).content[0].text
        assert "42" in res and "state" in res


@pytest.mark.anyio
async def test_exit_code_recovers_with_note():
    r = await _drive(["exit()", "40+2"])
    assert "42" in r[1] and "state" in r[1]


@pytest.mark.anyio
async def test_worker_killed_mid_execute_reports_death():
    async with stdio_client(_server_params()) as (r,w), ClientSession(r,w) as s:
        await s.initialize()
        pid = int((await s.call_tool("execute", {"code": "import os; os.getpid()"})).content[0].text)
        task = asyncio.create_task(s.call_tool("execute", {"code": "import time; time.sleep(30)"}))
        await asyncio.sleep(1)
        os.kill(pid, signal.SIGKILL)
        out = (await task).content[0].text
        assert "died" in out
        res = (await s.call_tool("execute", {"code": "40+2"})).content[0].text
        assert "42" in res


@pytest.mark.anyio
async def test_restart_clears_state():
    r = await _drive_ops([("execute","x = 1"), ("restart",), ("execute","x")])
    assert "NameError" in r[2]


@pytest.mark.anyio
async def test_restart_leaves_kernel_usable():
    r = await _drive_ops([("execute","x = 1"), ("restart",), ("execute","40+2")])
    assert r[2] == "42"


@pytest.mark.anyio
async def test_nb_magics(tmp_path):
    import json
    cells = [dict(cell_type="code", id="aaa111", metadata={}, outputs=[], execution_count=None, source="print('one')")]
    nb = tmp_path/"t.ipynb"
    nb.write_text(json.dumps(dict(cells=cells, metadata={}, nbformat=4, nbformat_minor=5)))
    r = await _drive([f"%nbopen {nb}", "%nbrun aaa"])
    assert "--- aaa111 ---" in r[1] and "one" in r[1]


@pytest.fixture
def anyio_backend(): return "asyncio"
