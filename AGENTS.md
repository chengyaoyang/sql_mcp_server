# SQL MCP Server Agent 指南

## 目标与范围

本文档总结 `sql_mcp_server` 的核心结构，归纳 MCP 服务器的关键组件，并给出在现有实现之上扩展 SQL 查询代理时可复用的架构要点。阅读后应能快速理解 STDIO 传输层的工作方式，并在保持 MCP 客户端兼容性的前提下添加新功能。

## 固定技术栈

- **语言与运行时**：Python 3.12，使用 `uv` 作为包管理与运行入口。
- **依赖管理**：`pyproject.toml` + `uv.lock`，禁止混用 `pip` 或 `poetry`。
- **核心库**：`mcp`（STDIO server）、`pydantic-settings`（配置）、`sqlite3` 标准库驱动，必要时通过 `asyncio.to_thread` 处理同步数据库调用。
- **数据库支持**：默认内置 SQLite 文件访问，扩展后端需保持同一抽象层（`db.py` 中的 `QueryResult` / `execute_*` 接口）。
- **测试数据**：`test_data/` 下维护示例 SQLite 库，新增用例需同步更新该目录并编写说明。

## 项目架构模式

- **启动入口一致化**  
  `src/sql_mcp_server/__init__.py` 通过 `asyncio.run(server.main())` 启动事件循环，而 `src/sql_mcp_server/__main__.py` 仅导入并调用 `main()`。因此 `python -m sql_mcp_server` 会直接启动 STDIO 服务器，无需额外脚手架。

- **配置管理**  
  `src/sql_mcp_server/config.py` 使用 `pydantic-settings` 定义 `Settings`，集中管理应用名称、版本、最大返回行数、默认超时以及数据库连接参数。`storage_path` 和 `database_path` 属性会在首次访问时解析命令行或环境变量，同时确保目录存在。

- **MCP Server 注册与运行**  
  `src/sql_mcp_server/server.py` 通过 `Server(settings.APP_NAME)` 创建实例，并使用装饰器注册 `list_prompts`、`get_prompt`、`list_tools` 与 `call_tool`。`main()` 中依赖 `mcp.server.stdio.stdio_server()` 建立标准输入输出流，然后传入 `InitializationOptions` 声明能力：

  ```python
  async def main() -> None:
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
  ```

- **Prompt 管理**  
  `src/sql_mcp_server/prompts/handlers.py` 维护一个轻量的 `SQL_PROMPTS` 字典，并在 `list_prompts()` 与 `get_prompt()` 中执行参数校验与提示内容拼装。需要扩展 Prompt 时只需在该模块注册新的 `Prompt` 实例。

- **Tool 定义模式**  
  `src/sql_mcp_server/tools/run_query.py`, `list_tables.py` 与 `describe_table.py` 均暴露 `types.Tool` 声明输入 Schema，并提供对应的 `handle_*` 异步函数。服务器端在 `call_tool` 内按名称分发，实现声明式输入与业务逻辑分离：

  ```python
  if name == run_query_tool.name:
      return await handle_run_query(arguments)
  if name == list_tables_tool.name:
      return await handle_list_tables(arguments)
  if name == describe_table_tool.name:
      return await handle_describe_table(arguments)
  ```

- **统一的返回格式**  
  `_format_result`（定义于 `tools/run_query.py`）将查询结果渲染为 Markdown 表格：首行标题、第二行分隔线、随后为数据行，并对竖线和换行进行转义。超出行数上限时追加 `_其余部分已截断..._` 的提示。其他工具直接复用该函数确保输出一致性。

- **长任务处理**  
  `src/sql_mcp_server/db.py` 通过 `asyncio.to_thread` 包装 SQLite 同步调用，避免阻塞事件循环。若未来需要执行长时间任务，可沿用该模式：在工具层发起调用，数据访问层使用线程池或后台任务维护状态并允许轮询。

- **资源抽象**  
  `src/sql_mcp_server/resources/results.py` 定义 `ResultManager`，把本地 JSON 结果包装为 MCP `Resource`，包含 `uri`、`name`、`description` 与 `mimeType` 元数据。通知客户端资源更新时，保持使用 `NotificationOptions(resources_changed=True)`。

## SQL MCP Server 架构蓝图

- **核心配置项**
  - 数据库连接：`DATABASE_URL` 或拆分为主机、端口、用户名、密码、数据库名等。
  - 查询限制：默认最大返回行数、是否允许多语句、默认事务隔离级别。
  - 超时设置：执行超时、空闲超时、连接重试次数。
  - 执行权限：通过 `READ_ONLY` 环境变量（如 `SQL_MCP_READ_ONLY=true`）限制为只读查询。
  - 结果格式：默认输出 Markdown 表格，可按需扩展 JSON、CSV 等。

- **工具清单建议**
  - `run_query`：执行 SQL 字符串，返回查询结果并在触发行数上限时提示截断。支持通过 `database_path` 指定 SQLite 文件路径。
  - `list_tables`：列举当前连接下的表、视图及其模式。
  - `describe_table`：查看指定表的列信息、约束、索引与外键。

- **执行流程**
  1. 在 `server.py` 中通过 `Server(Settings.APP_NAME)` 构建实例。
  2. 使用装饰器注册 `list_prompts`, `get_prompt`, `list_tools`, `call_tool` 等方法。
  3. 在工具处理函数内，通过 `db.execute_sqlite` 或未来扩展的驱动执行数据库操作，必要时使用 `asyncio.to_thread` 包装同步调用。
  4. 统一构造文本响应，确保行列输出一致并在截断时追加提示。
  5. 捕获异常时输出简洁明了的错误信息，避免泄露敏感连接信息。

- **Prompt 策略**
  - 在 `prompts/handlers.py` 中维护 SQL 模板、性能调优指南或安全提示。
  - 返回 `GetPromptResult` 时，结合 `PromptMessage` 和 `TextContent` 提供结构化上下文。

- **资源管理**
  - 使用 `ResultManager` 将常用查询结果或模式信息保存为 JSON 文件，并转换为 `types.Resource`。
  - 如需暴露更多元数据，可扩展 `description` 或 `mimeType` 并在资源目录内存放对应文件。

## 实施清单

1. **配置层**：在 `sql_mcp_server/config.py` 中扩展或修改 `Settings`，支持环境变量与命令行参数。
2. **服务器入口**：在 `server.py` 调整工具注册或能力声明，确保 `main()` 使用 STDIO 运行。
3. **工具模块**：在 `tools/` 目录下为每个功能建立独立模块，导出 `types.Tool` 和 `handle_*`。示例：

   ```python
   hello_tool = types.Tool(
       name="Hello World",
       description="Return Hello World",
       inputSchema={...},
   )

   async def handle_hello(arguments: Dict[str, Any]) -> List[types.TextContent]:
       ...
       return [types.TextContent(type="text", text="Hello World")]
   ```

   SQL 工具只需实现数据库查询逻辑，并按照约定返回文本。`describe_table` 的实现位于 `src/sql_mcp_server/tools/describe_table.py`，通过多条 SQLite `PRAGMA` 指令汇总基本信息、列、索引与外键，并借助 `_format_result` 统一输出 Markdown 表格。

4. **资源管理**：如需持久化查询结果，扩展 `resources/results.py`，并在 `server.py` 中通过 MCP 的 `NotificationOptions(resources_changed=True)` 通知客户端资源更新。
5. **入口封装**：保持 `__init__.py` 与 `__main__.py` 的包级入口，确保 `python -m sql_mcp_server` 可直接启动。
6. **测试编排**：编写集成测试，模拟数据库或使用内存数据库（SQLite in-memory）验证每个工具的行为，确保 Markdown 输出与截断逻辑稳定。

## 新功能开发流程

1. **需求评审**：在 PR 或 Issue 中明确功能范围、数据库影响、Markdown 输出变化及配置需求。
2. **设计同步**：更新 `AGENTS.md` 的相关架构段落或新增子节，必要时在 `README.md` 补充用户向说明。
3. **实现阶段**：
   - 仅在 `src/sql_mcp_server` 内新增/修改模块，保持工具声明与处理函数分离。
   - 若扩展数据库后端，先在 `db.py` 中定义统一接口，再实现具体驱动。
   - 所有文本结果必须通过现有或新增的 Markdown 格式化辅助函数。
4. **测试与验证**：编写/更新集成测试，使用 `uv run` + `test_data` 库验证；如引入新依赖，更新 `pyproject.toml` 与 `uv.lock`。
5. **文档更新**：同步修改 `README.md`、`AGENTS.md` 及必要的示例配置；确保新增工具在文档中说明输入、输出与限制。
6. **代码合规检查**：运行格式化/静态检查（若有），确保日志、错误信息无敏感信息泄漏，并在 PR 中附带示例调用结果。

## 运维提示

- 保持与 `server.py` 中一致的日志配置方式，统一使用模块级 `logging.getLogger`。
- 对长时间运行的查询设置超时，并提供状态查询或取消机制，可复用 `db.execute_sqlite` 的线程池调用模式。
- 确保仅通过 STDIO 与 MCP 客户端通信，不启动额外的 HTTP 服务。
- 在 `README.md` 中记录支持的数据库类型、依赖驱动及安装说明，方便使用者快速上手。
