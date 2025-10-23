## SQL MCP Server

SQL 查询 MCP 服务器，基于 `sql_mcp_server` 自身的 STDIO 架构实现。目前支持通过 SQLite 数据库文件（路径配置或参数传入）执行查询，并逐步拓展更多 SQL 后端。所有查询结果默认以 Markdown 表格格式返回，更易于在大模型环境中阅读。

### 目录结构

- `src/sql_mcp_server/config.py`：基于 `pydantic-settings` 的配置管理。
- `src/sql_mcp_server/server.py`：MCP Server 注册与 STDIO 运行入口。
- `src/sql_mcp_server/tools/`：`run_query`、`list_tables`、`describe_table` 等工具定义，支持指定 SQLite 文件路径。
- `src/sql_mcp_server/resources/`：查询结果资源管理占位实现。
- `src/sql_mcp_server/prompts/`：示例 Prompt 处理逻辑。

### 安装与使用

1. 克隆仓库并进入目录：

   ```bash
   git clone git@github.com:chengyaoyang/sql_mcp_server.git
   cd sql_mcp_server
   ```

2. 安装依赖：

   ```bash
   uv sync
   ```

3. 在 MCP 客户端配置服务（示例见下节），根据需要修改数据库相关的环境变量或参数。

> 可通过环境变量或 `--storage-path` 自定义查询结果缓存目录。默认可使用环境变量 `SQL_MCP_DEFAULT_DB_PATH` 或命令行 `--db-path` 指定 SQLite 数据库文件，也可在工具调用参数里提供 `database_path`。

### SQLite 快速体验

1. 准备数据库文件，例如 `test_data/test.sqlite`。
2. 启动服务器时指定默认路径：

   ```bash
   uv run sql-mcp-server --db-path test_data/test.sqlite
   ```

3. 在 MCP 客户端中调用工具：
   - `run_query`：可执行 `SELECT * FROM your_table LIMIT 10` 等语句，结果会以 Markdown 表格返回。
   - `list_tables`：返回 `sqlite_master` 中的表和视图清单。
   - `describe_table`：展示指定表或视图的基本信息、列结构、索引与外键约束。

#### describe_table 示例

```json
{
  "name": "describe_table",
  "arguments": {
    "table_name": "users"
  }
}
```

典型返回将分段包含“基本信息”“列信息”“索引信息”和“外键信息”，全部采用 Markdown 表格呈现。当记录超出 `SQL_MCP_MAX_ROWS` 限制时会附带 `_...已截断..._` 提示。

### MCP 配置示例

以 Claude Desktop 或兼容 MCP 客户端为例，可在配置中添加（请将 `--directory` 的路径替换为你本机的仓库位置）：

```json
{
  "mcpServers": {
    "sql": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/cheng/sql_mcp_server",
        "run",
        "sql-mcp-server",
        "--db-path",
        "/home/cheng/sql_mcp_server/test_data/test.sqlite"
      ],
      "env": {
        "SQL_MCP_MAX_ROWS": "2000",
        "SQL_MCP_READ_ONLY": "true"
      }
    }
  }
}
```

- `command`/`args`：使用 `uv run` 启动 STDIO 服务。
- `--db-path`：指定默认 SQLite 数据库文件路径。
- `env`：按需传入其他配置（例如最大行数、结果存储目录，详见 `src/sql_mcp_server/config.py`）。设置 `SQL_MCP_READ_ONLY=true` 可以强制以只读模式执行 SQL。

### License

本项目采用 [MIT License](LICENSE) 授权。
