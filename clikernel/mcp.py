"MCP server supervising a persistent `clikernel` CLI worker subprocess."
from pathlib import Path
from clikernel import INSTRUCTIONS
from clikernel.base import run_mcp


def main(): run_mcp(instructions=INSTRUCTIONS, eager=Path('pyproject.toml').exists())


if __name__ == "__main__": main()
