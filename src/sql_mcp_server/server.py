"""SQL MCP Server 主模块，参照 `arxiv_mcp_server.server`。"""

from typing import Any, Dict, List
import logging
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions
from mcp.server.stdio import stdio_server

from .config import Settings
from .tools import (
    run_query_tool,
    handle_run_query,
    list_tables_tool,
    handle_list_tables,
    describe_table_tool,
    handle_describe_table,
)
from .prompts import list_prompts as prompt_list_handler
from .prompts import get_prompt as prompt_get_handler

settings = Settings()
logger = logging.getLogger("sql-mcp-server")
logger.setLevel(logging.INFO)
server = Server(settings.APP_NAME)


@server.list_prompts()
async def list_prompts() -> List[types.Prompt]:
    """返回可用 Prompt。"""
    return await prompt_list_handler()


@server.get_prompt()
async def get_prompt(
    name: str, arguments: Dict[str, str] | None = None
) -> types.GetPromptResult:
    """返回指定 Prompt 的内容。"""
    return await prompt_get_handler(name, arguments)


@server.list_tools()
async def list_tools() -> List[types.Tool]:
    """注册 SQL 工具合集。"""
    return [run_query_tool, list_tables_tool, describe_table_tool]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """根据工具名称分发调用逻辑，结构与 `arxiv_mcp_server.server.call_tool` 相同。"""
    logger.debug("调用工具 %s，参数 %s", name, arguments)
    try:
        if name == run_query_tool.name:
            return await handle_run_query(arguments)
        if name == list_tables_tool.name:
            return await handle_list_tables(arguments)
        if name == describe_table_tool.name:
            return await handle_describe_table(arguments)
        return [
            types.TextContent(
                type="text",
                text=f'Error: Unknown tool "{name}"',
            )
        ]
    except Exception as exc:
        logger.exception("工具执行异常: %s", exc)
        return [
            types.TextContent(
                type="text",
                text=f"Error: {exc}",
            )
        ]


async def main() -> None:
    """STDIO 模式运行 MCP Server，完全复用参考项目结构。"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=settings.APP_NAME,
                server_version=settings.APP_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(resources_changed=True),
                    experimental_capabilities={},
                ),
            ),
        )
