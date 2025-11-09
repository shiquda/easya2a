"""
MCP客户端管理器

功能：
- 管理多个MCP服务器连接
- 提供统一的工具调用接口
- 连接池管理和生命周期管理
"""

import asyncio
import logging
from typing import Any
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool, CallToolResult

from core.config import MCPServerConfigModel, MCPTransport


logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    MCP客户端管理器

    管理与单个MCP服务器的连接
    """

    def __init__(self, name: str, config: MCPServerConfigModel):
        """
        初始化MCP客户端管理器

        Args:
            name: 服务器名称
            config: MCP服务器配置
        """
        self.name = name
        self.config = config
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []
        self._initialized = False

        # 用于维护stdio连接的后台任务
        self._read_stream = None
        self._write_stream = None
        self._stdio_context = None

    async def initialize(self):
        """初始化连接到MCP服务器"""
        if self._initialized:
            logger.debug(f"MCP client '{self.name}' already initialized")
            return

        logger.info(f"Initializing MCP client '{self.name}'...")

        if self.config.transport == MCPTransport.STDIO:
            await self._initialize_stdio()
        elif self.config.transport in (MCPTransport.SSE, MCPTransport.STREAMABLE_HTTP):
            await self._initialize_streamable_http()
        else:
            raise ValueError(f"Unknown transport type: {self.config.transport}")

        self._initialized = True
        logger.info(f"MCP client '{self.name}' initialized successfully")

    async def _initialize_stdio(self):
        """初始化stdio传输连接"""
        # 构建服务器参数
        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env or {},
            cwd=self.config.cwd,
        )

        logger.info(
            f"MCP client '{self.name}' connecting via stdio "
            f"(command: {self.config.command} {' '.join(self.config.args)})"
        )

        # 建立连接
        # 注意：stdio_client 是 async context manager，需要在整个生命周期内保持
        self._stdio_context = stdio_client(server_params)
        read_stream, write_stream = await self._stdio_context.__aenter__()

        self._read_stream = read_stream
        self._write_stream = write_stream

        # 创建会话
        self._session = ClientSession(read_stream, write_stream)

        # 初始化会话
        await self._session.__aenter__()
        await self._session.initialize()

        logger.debug(f"MCP client '{self.name}' stdio connection established")

    async def _initialize_streamable_http(self):
        """初始化 Streamable HTTP/SSE 传输连接"""
        if not self.config.url:
            raise ValueError(f"MCP server '{self.name}' requires 'url' for {self.config.transport} transport")

        logger.info(
            f"MCP client '{self.name}' connecting via {self.config.transport} "
            f"(url: {self.config.url})"
        )

        # 建立连接
        self._stdio_context = streamablehttp_client(self.config.url)
        read_stream, write_stream, _ = await self._stdio_context.__aenter__()

        self._read_stream = read_stream
        self._write_stream = write_stream

        # 创建会话
        self._session = ClientSession(read_stream, write_stream)

        # 初始化会话
        await self._session.__aenter__()
        await self._session.initialize()

        logger.debug(f"MCP client '{self.name}' streamable HTTP connection established")

    async def list_tools(self) -> list[Tool]:
        """
        列出可用工具

        Returns:
            工具列表

        Raises:
            RuntimeError: 客户端未连接
        """
        if not self._session:
            raise RuntimeError(f"MCP client '{self.name}' not connected")

        logger.debug(f"MCP client '{self.name}' listing tools...")
        result = await self._session.list_tools()
        self._tools = result.tools

        logger.info(
            f"MCP client '{self.name}' found {len(self._tools)} tools: "
            f"{[t.name for t in self._tools]}"
        )

        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> CallToolResult:
        """
        调用工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具调用结果

        Raises:
            RuntimeError: 客户端未连接
        """
        if not self._session:
            raise RuntimeError(f"MCP client '{self.name}' not connected")

        logger.debug(
            f"MCP client '{self.name}' calling tool '{tool_name}' "
            f"with args: {arguments}"
        )

        result = await self._session.call_tool(tool_name, arguments)

        logger.debug(f"MCP client '{self.name}' tool '{tool_name}' call completed")

        return result

    async def cleanup(self):
        """清理资源"""
        if not self._initialized:
            return

        logger.info(f"Cleaning up MCP client '{self.name}'...")

        try:
            # 关闭会话
            if self._session:
                await self._session.__aexit__(None, None, None)
                self._session = None

            # 关闭stdio连接
            if self._stdio_context:
                await self._stdio_context.__aexit__(None, None, None)
                self._stdio_context = None

            self._read_stream = None
            self._write_stream = None

        except Exception as e:
            logger.error(f"Error during cleanup of MCP client '{self.name}': {e}")

        self._initialized = False
        logger.info(f"MCP client '{self.name}' cleaned up")


class MCPManagerPool:
    """
    MCP管理器池

    管理多个MCP客户端连接
    """

    def __init__(self):
        self._clients: dict[str, MCPClientManager] = {}
        self._initialized = False

    def register_server(self, name: str, config: MCPServerConfigModel):
        """
        注册MCP服务器

        Args:
            name: 服务器名称
            config: 服务器配置
        """
        if name in self._clients:
            logger.warning(f"MCP server '{name}' already registered, skipping")
            return

        client = MCPClientManager(name, config)
        self._clients[name] = client
        logger.info(f"Registered MCP server '{name}' ({config.description or 'no description'})")

    async def initialize_all(self):
        """初始化所有客户端"""
        if self._initialized:
            logger.debug("MCP pool already initialized")
            return

        logger.info(f"Initializing MCP pool with {len(self._clients)} servers...")

        # 并行初始化所有客户端
        tasks = [client.initialize() for client in self._clients.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查是否有初始化失败的
        failed = []
        for name, result in zip(self._clients.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to initialize MCP server '{name}': {result}")
                failed.append(name)

        if failed:
            logger.warning(
                f"MCP pool initialized with {len(failed)} failed servers: {failed}"
            )
        else:
            logger.info("MCP pool initialized successfully")

        self._initialized = True

    def get_client(self, name: str) -> MCPClientManager:
        """
        获取MCP客户端

        Args:
            name: 服务器名称

        Returns:
            MCP客户端管理器

        Raises:
            KeyError: 服务器未注册
        """
        if name not in self._clients:
            raise KeyError(f"MCP server '{name}' not found in pool")
        return self._clients[name]

    async def get_all_tools(self, server_names: list[str]) -> dict[str, list[Tool]]:
        """
        获取指定服务器的所有工具

        Args:
            server_names: 服务器名称列表

        Returns:
            服务器名 -> 工具列表的映射
        """
        tools_by_server = {}

        for name in server_names:
            try:
                client = self.get_client(name)
                tools = await client.list_tools()
                tools_by_server[name] = tools
            except Exception as e:
                logger.error(f"Failed to get tools from MCP server '{name}': {e}")
                tools_by_server[name] = []

        return tools_by_server

    async def cleanup_all(self):
        """清理所有客户端"""
        if not self._initialized:
            return

        logger.info("Cleaning up MCP pool...")

        # 并行清理所有客户端
        tasks = [client.cleanup() for client in self._clients.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        self._initialized = False
        logger.info("MCP pool cleaned up")


# 全局MCP管理器池
_mcp_pool: MCPManagerPool | None = None


def get_mcp_pool() -> MCPManagerPool:
    """
    获取全局MCP管理器池

    Returns:
        MCP管理器池实例
    """
    global _mcp_pool
    if _mcp_pool is None:
        _mcp_pool = MCPManagerPool()
    return _mcp_pool


def reset_mcp_pool():
    """
    重置全局MCP管理器池（主要用于测试）
    """
    global _mcp_pool
    _mcp_pool = None
