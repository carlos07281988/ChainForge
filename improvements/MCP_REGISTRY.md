# MCP Tool Registry — Discover, Install, Manage MCP Servers

> 为 ChainForge Agent 提供 MCP 工具的注册、发现和管理能力

## Motivation

MCP (Model Context Protocol) 服务器是 Agent 获取外部工具的标准方式。
但当前用户需要手动配置 MCP 服务器连接。需要一个注册表来：
1. 管理已安装的 MCP 服务器配置
2. 发现可用的 MCP 服务器
3. 一键安装内置的 MCP 服务器

## Design

### Registry

本地 JSON 文件存储在 `~/.chainforge/mcp_servers.json`：

```json
[
  {
    "name": "filesystem",
    "description": "Filesystem access",
    "command": "npx -y @modelcontextprotocol/server-filesystem",
    "transport": "stdio",
    "tags": ["files", "system"],
    "tools": ["read_file", "write_file"],
    "installed": true
  }
]
```

### Built-in Servers

| Server | Description | Tools |
|--------|-------------|-------|
| `filesystem` | 文件读写操作 | read_file, write_file, list_files |
| `github` | GitHub API | create_repository, get_repository |
| `sqlite` | SQLite 数据库 | query, list_tables |
| `web_search` | 网络搜索 | web_search |
| `playwright` | 浏览器自动化 | navigate, screenshot, click |
| `memory` | 持久化记忆 | remember, recall |
| `slack` | Slack 消息 | send_message, list_channels |
| `fetch` | 网页抓取 | fetch, fetch_markdown |

### CLI Commands

```bash
# List registered servers
chainforge mcp list

# Install a built-in server
chainforge mcp install filesystem

# Add a custom server
chainforge mcp add my-api --command "node server.js" --desc "My API"

# Remove a server
chainforge mcp remove my-api

# Search servers
chainforge mcp search database

# Show server details
chainforge mcp info filesystem

# List built-in servers
chainforge mcp builtins
```

## Files

| File | Description |
|------|-------------|
| `chainforge/mcp/registry.py` | MCPRegistry, MCPServerInfo, built-in definitions |
| `chainforge/cli/__init__.py` | `mcp` subcommand |
| `tests/test_mcp_registry.py` | Tests |
