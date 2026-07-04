"MCP server exposing a persistent IPython `CaptureShell` as an `execute` tool."
import asyncio

from clikernel.cli import _set_default_dirs, _make_shell


def main():
    _set_default_dirs()
    from mcp.server.fastmcp import FastMCP
    from fastcore.nbio import render_text
    mcp = FastMCP("clikernel")
    state = {"shell": _make_shell(), "lock": asyncio.Lock()}

    @mcp.tool(structured_output=False)
    async def execute(code:str  # IPython-compatible code to run in the persistent session
                     )->str:   # Rendered outputs (stdout, display data, last-expression result, errors)
        "Run `code` in the persistent IPython session, keeping state across calls (imports, variables, monkeypatches, cached objects)."
        async with state["lock"]:
            outputs = await asyncio.to_thread(state["shell"].run, code)
            return render_text(outputs)

    @mcp.tool(structured_output=False)
    async def restart()->str:
        "Discard all session state (imports, variables, monkeypatches, cached objects) and start a fresh IPython shell inside the same server process. Use this for the common case: a bad variable, a half-finished experiment to abandon, or a user-requested clean slate. Note: this does NOT touch `sys.modules` or anything already monkeypatched (e.g. via fastcore's `@patch`) -- those live at the process level, not the shell level, and survive `restart` untouched. If you need a genuinely fresh interpreter (e.g. after reloading a module that other already-imported modules had patched -- symptoms: a stale-class bug where `isinstance`/`is` checks mysteriously fail, or a class is missing a method you know it has), use `exit` instead. After restarting, redo any imports/setup the task still needs."
        async with state["lock"]: state["shell"] = _make_shell()
        return "restarted"

    @mcp.tool(structured_output=False)
    async def exit()->str:
        "Terminate this MCP server process immediately, for when `restart` isn't enough (see its docstring). This call itself will error (\"Connection closed\") since the process dies before it can respond -- that's expected, not a failure. The next `execute` call transparently reconnects to a freshly-spawned process with `sys.modules` genuinely reset (confirmed via a new pid), no manual reconnect needed. After reconnecting, redo any imports/setup the task still needs."
        import os
        os._exit(0)

    mcp.run()


if __name__ == "__main__": main()
