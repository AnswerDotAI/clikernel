import os,shutil,sys,tempfile

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
async def test_state_persists_across_calls():
    assert (await _drive(["x = 41", "x + 1"]))[1] == "42"


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
async def test_restart_clears_state():
    r = await _drive_ops([("execute","x = 1"), ("restart",), ("execute","x")])
    assert "NameError" in r[2]


@pytest.mark.anyio
async def test_restart_leaves_kernel_usable():
    r = await _drive_ops([("execute","x = 1"), ("restart",), ("execute","40+2")])
    assert r[2] == "42"


@pytest.fixture
def anyio_backend(): return "asyncio"
