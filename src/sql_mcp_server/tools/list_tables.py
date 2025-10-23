"""列出数据库表的工具定义。"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import mcp.types as types

from ..config import Settings
from ..db import execute_sqlite, ExecutionError
from .run_query import _format_result  # reuse formatting

logger = logging.getLogger("sql-mcp-server")
settings = Settings()

list_tables_tool = types.Tool(
    name="list_tables",
    description="列出当前 SQLite 数据库中的表、视图等对象。",
    inputSchema={
        "type": "object",
        "properties": {
            "database_path": {
                "type": "string",
                "description": "SQLite 数据库文件路径，留空时使用默认配置。",
            }
        },
        "required": [],
    },
)


def _resolve_db_path(arguments: Optional[Dict[str, Any]]) -> Optional[Path]:
    if arguments and arguments.get("database_path"):
        return Path(arguments["database_path"]).expanduser().resolve()
    return settings.database_path


async def handle_list_tables(arguments: Optional[Dict[str, Any]] = None) -> List[types.TextContent]:
    db_path = _resolve_db_path(arguments)
    if not db_path:
        error_msg = "未配置数据库路径，请在参数中提供 `database_path` 或设置默认路径。"
        return [types.TextContent(type="text", text=error_msg)]

    statement = """
    SELECT
        name,
        type,
        COALESCE(tbl_name, name) AS table_name
    FROM sqlite_master
    WHERE type IN ('table', 'view')
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name;
    """

    try:
        result = await execute_sqlite(
            db_path,
            statement,
            settings.MAX_ROWS,
            settings.READ_ONLY,
        )
        output = _format_result(result.columns, result.rows)
        if result.truncated:
            output = f"{output}\n\n_其余部分已截断..._"
        return [types.TextContent(type="text", text=output)]
    except ExecutionError as exc:
        logger.error("列出表失败: %s", exc)
        return [types.TextContent(type="text", text=str(exc))]
    except Exception as exc:  # noqa: BLE001
        logger.exception("未预期的异常")
        return [types.TextContent(type="text", text=f"unexpected error: {exc}")]
