"""数据库访问层，当前支持通过文件路径连接 SQLite。"""

from __future__ import annotations

import sqlite3
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote


class QueryResult:
    """封装查询结果。"""

    def __init__(
        self,
        columns: List[str],
        rows: List[Dict[str, Any]],
        rowcount: int,
        truncated: bool = False,
    ):
        self.columns = columns
        self.rows = rows
        self.rowcount = rowcount
        self.truncated = truncated

    def to_payload(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.rowcount,
            "truncated": self.truncated,
        }


class ExecutionError(Exception):
    """统一的执行异常。"""


def _execute_sqlite(
    db_path: Path,
    statement: str,
    max_rows: int,
    read_only: bool = False,
) -> QueryResult:
    """在线程池中执行 SQLite 查询。"""
    if not db_path.exists():
        raise ExecutionError(f"数据库文件不存在: {db_path}")

    path_str = db_path.resolve().as_posix()
    if read_only:
        uri = f"file:{quote(path_str, safe='/')}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(path_str, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(statement)

        columns: List[str] = []
        rows: List[Dict[str, Any]] = []

        truncated = False
        if cur.description:
            columns = [col[0] for col in cur.description]
            for idx, item in enumerate(cur.fetchmany(max_rows + 1)):
                row_dict = {col: item[col] for col in columns}
                rows.append(row_dict)
                if idx + 1 >= max_rows:
                    truncated = True
                    rows = rows[:max_rows]
                    break

        # 对于非查询语句，提交事务
        if not cur.description:
            if not read_only:
                conn.commit()
            return QueryResult(columns=[], rows=[], rowcount=cur.rowcount)

        return QueryResult(
            columns=columns,
            rows=rows,
            rowcount=len(rows),
            truncated=truncated,
        )
    except sqlite3.Error as exc:
        if not read_only:
            conn.rollback()
        raise ExecutionError(str(exc)) from exc
    finally:
        conn.close()


async def execute_sqlite(
    db_path: Path,
    statement: str,
    max_rows: int,
    read_only: bool = False,
) -> QueryResult:
    """异步包装 SQLite 执行。"""
    return await asyncio.to_thread(
        _execute_sqlite,
        db_path,
        statement,
        max_rows,
        read_only,
    )
