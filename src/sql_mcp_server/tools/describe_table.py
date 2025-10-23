"""表结构描述工具定义。"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import mcp.types as types

from ..config import Settings
from ..db import execute_sqlite, ExecutionError
from .run_query import _format_result

logger = logging.getLogger("sql-mcp-server")
settings = Settings()

describe_table_tool = types.Tool(
    name="describe_table",
    description="查看指定表或视图的列、索引与外键信息。",
    inputSchema={
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "要描述的表或视图名称。",
            },
            "database_path": {
                "type": "string",
                "description": "SQLite 数据库文件路径，留空时使用默认配置。",
            },
        },
        "required": ["table_name"],
    },
)


def _resolve_db_path(arguments: Dict[str, Any]) -> Optional[Path]:
    if db_arg := arguments.get("database_path"):
        return Path(db_arg).expanduser().resolve()
    return settings.database_path


def _escape_identifier(identifier: str) -> str:
    return identifier.replace("'", "''")


def _bool_to_yes_no(value: Any) -> str:
    return "yes" if value else "no"


async def handle_describe_table(arguments: Dict[str, Any]) -> List[types.TextContent]:
    raw_table_name = arguments.get("table_name")
    if not isinstance(raw_table_name, str) or not raw_table_name.strip():
        error_msg = "请提供有效的 `table_name`。"
        logger.error(error_msg)
        return [types.TextContent(type="text", text=error_msg)]

    table_name = raw_table_name.strip()
    db_path = _resolve_db_path(arguments)
    if not db_path:
        error_msg = "未配置数据库路径，请在参数中提供 `database_path` 或设置默认路径。"
        logger.error(error_msg)
        return [types.TextContent(type="text", text=error_msg)]

    escaped_table = _escape_identifier(table_name)

    metadata_stmt = f"""
    SELECT
        name,
        type,
        COALESCE(sql, '') AS definition
    FROM sqlite_master
    WHERE name = '{escaped_table}'
      AND type IN ('table', 'view')
    LIMIT 1;
    """

    try:
        metadata = await execute_sqlite(
            db_path,
            metadata_stmt,
            max_rows=1,
            read_only=settings.READ_ONLY,
        )
    except ExecutionError as exc:
        logger.error("查询表元数据失败: %s", exc)
        return [types.TextContent(type="text", text=str(exc))]
    except Exception as exc:  # noqa: BLE001
        logger.exception("未预期的元数据查询异常")
        return [types.TextContent(type="text", text=f"unexpected error: {exc}")]

    if not metadata.rows:
        error_msg = f"表或视图 `{table_name}` 不存在。"
        logger.warning(error_msg)
        return [types.TextContent(type="text", text=error_msg)]

    sections: List[str] = []

    sections.append(
        "**基本信息**\n"
        + _format_result(metadata.columns, metadata.rows)
    )

    # 列信息
    try:
        columns_result = await execute_sqlite(
            db_path,
            f"PRAGMA table_info('{escaped_table}');",
            settings.MAX_ROWS,
            settings.READ_ONLY,
        )
    except ExecutionError as exc:
        logger.error("查询列信息失败: %s", exc)
        columns_text = f"获取列信息失败: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("列信息查询异常")
        columns_text = f"unexpected error while fetching columns: {exc}"
    else:
        if columns_result.rows:
            columns_text = _format_result(columns_result.columns, columns_result.rows)
            if columns_result.truncated:
                columns_text = f"{columns_text}\n\n_列信息已截断..._"
        else:
            columns_text = "_未找到列信息。_"

    sections.append("**列信息**\n" + columns_text)

    # 索引信息
    index_rows: List[Dict[str, Any]] = []
    index_section_note: Optional[str] = None
    index_error: Optional[str] = None

    try:
        index_list = await execute_sqlite(
            db_path,
            f"PRAGMA index_list('{escaped_table}');",
            settings.MAX_ROWS,
            settings.READ_ONLY,
        )
        for index in index_list.rows:
            index_name = index.get("name")
            if not index_name:
                continue
            escaped_index = _escape_identifier(str(index_name))
            columns_desc = ""
            try:
                index_info = await execute_sqlite(
                    db_path,
                    f"PRAGMA index_info('{escaped_index}');",
                    settings.MAX_ROWS,
                    settings.READ_ONLY,
                )
                column_names = [
                    str(col.get("name", ""))
                    for col in index_info.rows
                    if col.get("name")
                ]
                if index_info.truncated:
                    column_names.append("...")
                columns_desc = ", ".join(column_names)
            except ExecutionError as exc:
                logger.error("查询索引列信息失败: %s", exc)
                columns_desc = f"error: {exc}"
            except Exception as exc:  # noqa: BLE001
                logger.exception("索引列查询异常")
                columns_desc = f"unexpected error: {exc}"

            index_rows.append(
                {
                    "name": str(index_name),
                    "unique": _bool_to_yes_no(index.get("unique")),
                    "origin": str(index.get("origin", "")),
                    "partial": _bool_to_yes_no(index.get("partial")),
                    "columns": columns_desc,
                }
            )

        if index_list.truncated:
            index_section_note = "_索引列表已截断..._"
    except ExecutionError as exc:
        logger.error("查询索引列表失败: %s", exc)
        index_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("索引列表查询异常")
        index_error = f"unexpected error: {exc}"

    if index_error:
        indexes_text = index_error
    elif index_rows:
        indexes_text = _format_result(
            ["name", "unique", "origin", "partial", "columns"],
            index_rows,
        )
        if index_section_note:
            indexes_text = f"{indexes_text}\n\n{index_section_note}"
    else:
        indexes_text = "_未找到索引。_"

    sections.append("**索引信息**\n" + indexes_text)

    # 外键信息
    try:
        fk_result = await execute_sqlite(
            db_path,
            f"PRAGMA foreign_key_list('{escaped_table}');",
            settings.MAX_ROWS,
            settings.READ_ONLY,
        )
    except ExecutionError as exc:
        logger.error("查询外键失败: %s", exc)
        fk_text = f"获取外键信息失败: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("外键查询异常")
        fk_text = f"unexpected error while fetching foreign keys: {exc}"
    else:
        if fk_result.rows:
            fk_text = _format_result(fk_result.columns, fk_result.rows)
            if fk_result.truncated:
                fk_text = f"{fk_text}\n\n_外键列表已截断..._"
        else:
            fk_text = "_未找到外键约束。_"

    sections.append("**外键信息**\n" + fk_text)

    output_text = "\n\n".join(sections)
    return [types.TextContent(type="text", text=output_text)]
