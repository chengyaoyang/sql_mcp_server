"""执行 SQL 查询的工具定义。"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import mcp.types as types

from ..config import Settings
from ..db import execute_sqlite, ExecutionError

logger = logging.getLogger("sql-mcp-server")
settings = Settings()

run_query_tool = types.Tool(
    name="run_query",
    description="执行 SQL 语句并返回查询结果，可通过数据库文件路径连接 SQLite。",
    inputSchema={
        "type": "object",
        "properties": {
            "statement": {
                "type": "string",
                "description": "要执行的 SQL 语句。",
            },
            "max_rows": {
                "type": "integer",
                "description": "覆盖默认最大返回行数。",
            },
            "database_path": {
                "type": "string",
                "description": "SQLite 数据库文件路径，留空时使用默认配置。",
            },
        },
        "required": ["statement"],
    },
)


def _resolve_db_path(arguments: Dict[str, Any]) -> Optional[Path]:
    if db_arg := arguments.get("database_path"):
        return Path(db_arg).expanduser().resolve()
    return settings.database_path


def _format_result(columns: List[str], rows: List[Dict[str, Any]]) -> str:
    if not columns:
        return "_No result rows._"

    header = " | ".join(columns)
    separator = " | ".join("---" for _ in columns)
    lines = [f"| {header} |", f"| {separator} |"]

    for row in rows:
        values: List[str] = []
        for col in columns:
            value = row.get(col, "")
            if value is None:
                value_str = ""
            else:
                value_str = str(value)
            value_str = value_str.replace("|", "\\|").replace("\n", "<br>")
            values.append(value_str)
        lines.append(f"| {' | '.join(values)} |")
    return "\n".join(lines)


async def handle_run_query(arguments: Dict[str, Any]) -> List[types.TextContent]:
    statement = arguments["statement"]
    max_rows_arg = arguments.get("max_rows")
    max_rows = settings.MAX_ROWS
    if isinstance(max_rows_arg, int) and max_rows_arg > 0:
        max_rows = min(max_rows_arg, settings.MAX_ROWS)

    db_path = _resolve_db_path(arguments)
    if not db_path:
        error_msg = "未配置数据库路径，请在参数中提供 `database_path` 或设置默认路径。"
        logger.error(error_msg)
        return [types.TextContent(type="text", text=error_msg)]

    try:
        result = await execute_sqlite(
            db_path,
            statement,
            max_rows,
            settings.READ_ONLY,
        )
        output = _format_result(result.columns, result.rows)
        if result.truncated:
            output = f"{output}\n\n_其余部分已截断..._"
        return [types.TextContent(type="text", text=output)]
    except ExecutionError as exc:
        logger.error("执行 SQL 失败: %s", exc)
        return [types.TextContent(type="text", text=str(exc))]
    except Exception as exc:  # noqa: BLE001
        logger.exception("未预期的执行异常")
        return [types.TextContent(type="text", text=f"unexpected error: {exc}")]
