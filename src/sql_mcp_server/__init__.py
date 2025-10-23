"""SQL MCP Server 包初始化。"""

from . import server
import asyncio


def main() -> None:
    """包入口，参照 `arxiv_mcp_server.__init__.py`。"""
    asyncio.run(server.main())


__all__ = ["main", "server"]
