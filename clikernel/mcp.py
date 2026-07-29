"MCP server supervising a persistent `clikernel` CLI worker subprocess."
from pathlib import Path
from fastcore.script import call_parse
from clikernel import INSTRUCTIONS
from clikernel.base import run_mcp


@call_parse
def main(
    transport:str='stdio', # 'stdio', or 'streamable-http' to serve over HTTP (needs `$CLIKERNEL_TOKEN`)
    host:str='127.0.0.1',  # Interface to bind, for `streamable-http`
    port:int=8000,         # Port to bind, for `streamable-http`
):
    "Run the clikernel MCP server"
    run_mcp(instructions=INSTRUCTIONS, eager=Path('pyproject.toml').exists(), transport=transport, host=host, port=port)


if __name__ == "__main__": main()
