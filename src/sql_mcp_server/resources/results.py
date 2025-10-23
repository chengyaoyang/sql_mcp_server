"""查询结果资源管理，实现思路仿照 `resources/papers.py`。"""

from pathlib import Path
from typing import List
import logging
import json
from pydantic import AnyUrl
import mcp.types as types
from ..config import Settings

logger = logging.getLogger("sql-mcp-server")


class ResultManager:
    """管理查询结果文件并暴露为 MCP Resource。"""

    def __init__(self) -> None:
        settings = Settings()
        self.storage_path = Path(settings.storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _result_path(self, identifier: str) -> Path:
        """构造结果文件路径。"""
        safe_id = identifier.replace("/", "_")
        return self.storage_path / f"{safe_id}.json"

    async def list_results(self) -> List[str]:
        """列出存储的结果标识。"""
        identifiers = [p.stem for p in self.storage_path.glob("*.json")]
        logger.debug("发现结果文件数量: %d", len(identifiers))
        return identifiers

    async def list_resources(self) -> List[types.Resource]:
        """将本地文件映射为 MCP Resource，参照 `resources/papers.py:70`。"""
        resources: List[types.Resource] = []
        for identifier in await self.list_results():
            path = self._result_path(identifier)
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"file://{path}"),
                    name=f"SQL Result {identifier}",
                    description="缓存的 SQL 查询结果。",
                    mimeType="application/json",
                )
            )
        return resources

    async def store_result(self, identifier: str, payload: dict) -> None:
        """将查询结果写入 JSON 文件。"""
        path = self._result_path(identifier)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
