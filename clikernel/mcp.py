"MCP server exposing a persistent IPython `CaptureShell` as an `execute` tool."
from clikernel.cli import _set_default_dirs, _make_shell


def main():
    _set_default_dirs()
    from mcp.server.fastmcp import FastMCP
    from fastcore.nbio import render_text
    mcp = FastMCP("clikernel")
    state = {"shell": _make_shell()}

    @mcp.tool()
    def execute(code:str  # IPython-compatible code to run in the persistent session
                )->str:   # Rendered outputs (stdout, display data, last-expression result, errors)
        "Run `code` in the persistent IPython session, keeping state across calls."
        return render_text(state["shell"].run(code))

    @mcp.tool()
    def restart()->str:
        "Discard all session state (imports, variables, monkeypatches) and start a fresh IPython session."
        state["shell"] = _make_shell()
        return "restarted"

    mcp.run()


if __name__ == "__main__": main()
