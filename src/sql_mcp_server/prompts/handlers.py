"""SQL Prompt 处理逻辑，参考 `prompts/handlers.py`。"""

from typing import Dict, List, Optional
from mcp.types import Prompt, PromptMessage, TextContent, GetPromptResult


SQL_PROMPTS: Dict[str, Prompt] = {
    "sql-best-practices": Prompt(
        name="sql-best-practices",
        description="SQL 查询编写与优化建议。",
        arguments=[],
    )
}


async def list_prompts() -> List[Prompt]:
    """列出可用 prompt。"""
    return list(SQL_PROMPTS.values())


async def get_prompt(
    name: str,
    arguments: Dict[str, str] | None = None,
    session_id: Optional[str] = None,
) -> GetPromptResult:
    """返回指定 prompt 的内容。"""
    if name not in SQL_PROMPTS:
        raise ValueError(f"Prompt not found: {name}")

    content = (
        "使用具名参数并限制返回行数，合理利用索引和 EXPLAIN 诊断性能问题。"
    )
    return GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=content),
            )
        ]
    )
