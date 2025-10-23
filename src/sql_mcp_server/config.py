"""SQL MCP Server 配置定义。"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys


class Settings(BaseSettings):
    """服务器配置项，与 `arxiv_mcp_server.config.Settings` 保持相似接口。"""

    APP_NAME: str = "sql-mcp-server"
    APP_VERSION: str = "0.1.0"
    MAX_ROWS: int = 1000
    DEFAULT_TIMEOUT_SECONDS: int = 60

    DATABASE_URL: Optional[str] = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None

    RESULT_STORAGE: Optional[Path] = None
    DEFAULT_DB_PATH: Optional[Path] = None
    READ_ONLY: bool = False

    model_config = SettingsConfigDict(env_prefix="SQL_MCP_", extra="allow")

    @property
    def storage_path(self) -> Path:
        """解析查询结果缓存目录，参考 `arxiv_mcp_server.config.Settings.STORAGE_PATH`。"""
        path = (
            self.RESULT_STORAGE
            or self._get_path_from_args("--storage-path")
            or Path.home() / ".sql-mcp-server" / "results"
        )
        path = Path(path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Optional[Path]:
        """解析默认数据库文件路径，支持环境变量与 `--db-path` 参数。"""
        path = (
            self.DEFAULT_DB_PATH
            or self._get_path_from_args("--db-path")
        )
        if not path:
            return None
        resolved = Path(path).expanduser().resolve()
        return resolved

    def _get_path_from_args(self, flag: str) -> Optional[Path]:
        """从命令行读取路径类参数。"""
        args = sys.argv[1:]
        if len(args) < 2:
            return None

        try:
            idx = args.index(flag)
        except ValueError:
            return None

        if idx + 1 >= len(args):
            return None

        try:
            return Path(args[idx + 1]).resolve()
        except (TypeError, ValueError, OSError):
            return None
