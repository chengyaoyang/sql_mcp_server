"""SQL MCP Server 工具注册。"""

from .run_query import run_query_tool, handle_run_query
from .list_tables import list_tables_tool, handle_list_tables
from .describe_table import describe_table_tool, handle_describe_table

__all__ = [
    "run_query_tool",
    "handle_run_query",
    "list_tables_tool",
    "handle_list_tables",
    "describe_table_tool",
    "handle_describe_table",
]
