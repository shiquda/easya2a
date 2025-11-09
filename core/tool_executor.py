"""
工具执行器 - 管理和执行LLM工具调用

功能：
- 注册工具函数
- 执行工具调用
- 处理工具调用参数解析
- 错误处理和日志记录
"""

import json
import logging
import traceback
from typing import Any, Callable, Awaitable


logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    工具调用执行器

    负责管理和执行LLM的工具调用请求。

    使用示例:
        # 创建执行器
        executor = ToolExecutor()

        # 注册工具函数
        @executor.register_tool
        async def get_weather(location: str) -> dict:
            return {"temperature": "20°C", "location": location}

        # 或者手动注册
        executor.register_tool("get_time", get_current_time)

        # 执行工具调用
        result = await executor.execute(tool_call)
    """

    def __init__(self):
        """初始化工具执行器"""
        self._tools: dict[str, Callable] = {}
        logger.info("ToolExecutor initialized")

    def register_tool(
        self,
        name: str | None = None,
        func: Callable | None = None
    ) -> Callable:
        """
        注册工具函数

        可以作为装饰器使用或直接调用。

        Args:
            name: 工具名称（可选，默认使用函数名）
            func: 工具函数（可选，装饰器模式下为None）

        Returns:
            注册的函数（用于装饰器模式）

        使用示例:
            # 作为装饰器
            @executor.register_tool
            async def my_tool(...):
                pass

            # 指定名称
            @executor.register_tool("custom_name")
            async def my_tool(...):
                pass

            # 直接调用
            executor.register_tool("tool_name", my_function)
        """
        def decorator(f: Callable) -> Callable:
            tool_name = name if name else f.__name__
            self._tools[tool_name] = f
            logger.info(f"Registered tool: {tool_name}")
            return f

        # 如果提供了func，直接注册
        if func is not None:
            tool_name = name if name else func.__name__
            self._tools[tool_name] = func
            logger.info(f"Registered tool: {tool_name}")
            return func

        # 如果name是函数（装饰器不带括号调用）
        if callable(name):
            func = name
            tool_name = func.__name__
            self._tools[tool_name] = func
            logger.info(f"Registered tool: {tool_name}")
            return func

        # 装饰器模式
        return decorator

    def unregister_tool(self, name: str) -> bool:
        """
        注销工具函数

        Args:
            name: 工具名称

        Returns:
            是否成功注销
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        logger.warning(f"Tool not found for unregistration: {name}")
        return False

    def get_tool(self, name: str) -> Callable | None:
        """
        获取工具函数

        Args:
            name: 工具名称

        Returns:
            工具函数，如果不存在则返回None
        """
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """
        检查工具是否存在

        Args:
            name: 工具名称

        Returns:
            工具是否存在
        """
        return name in self._tools

    def list_tools(self) -> list[str]:
        """
        列出所有已注册的工具

        Returns:
            工具名称列表
        """
        return list(self._tools.keys())

    async def execute(self, tool_call: Any) -> str:
        """
        执行工具调用

        Args:
            tool_call: OpenAI tool_call 对象，包含：
                - function.name: 函数名
                - function.arguments: JSON字符串格式的参数
                - id: 工具调用ID

        Returns:
            工具执行结果（JSON字符串格式）
        """
        tool_name = tool_call.function.name

        logger.debug(
            f"Executing tool call:\n"
            f"  Tool: {tool_name}\n"
            f"  Call ID: {tool_call.id}\n"
            f"  Arguments: {tool_call.function.arguments}"
        )

        # 检查工具是否存在
        if tool_name not in self._tools:
            error_msg = f"Tool '{tool_name}' not found. Available tools: {list(self._tools.keys())}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

        try:
            # 解析参数
            args_dict = json.loads(tool_call.function.arguments)
            logger.debug(f"Parsed arguments: {args_dict}")

            # 执行工具函数
            tool_func = self._tools[tool_name]

            # 判断是否是异步函数
            import inspect
            if inspect.iscoroutinefunction(tool_func):
                result = await tool_func(**args_dict)
            else:
                result = tool_func(**args_dict)

            logger.info(f"Tool '{tool_name}' executed successfully")
            logger.debug(f"Tool result: {result}")

            # 将结果转换为JSON字符串
            if isinstance(result, str):
                # 如果已经是字符串，检查是否是有效JSON
                try:
                    json.loads(result)
                    return result
                except json.JSONDecodeError:
                    # 不是有效JSON，包装一下
                    return json.dumps({"result": result})
            else:
                return json.dumps(result)

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse tool arguments: {e}"
            logger.error(
                f"Tool '{tool_name}' JSON parsing error:\n"
                f"  Error: {e}\n"
                f"  Arguments: {tool_call.function.arguments}\n"
                f"  Traceback:\n{traceback.format_exc()}"
            )
            return json.dumps({"error": error_msg})

        except TypeError as e:
            error_msg = f"Invalid arguments for tool '{tool_name}': {e}"
            logger.error(
                f"Tool '{tool_name}' argument error:\n"
                f"  Error: {e}\n"
                f"  Expected signature: {inspect.signature(self._tools[tool_name])}\n"
                f"  Provided arguments: {args_dict}\n"
                f"  Traceback:\n{traceback.format_exc()}"
            )
            return json.dumps({"error": error_msg})

        except Exception as e:
            error_msg = f"Tool execution error: {str(e)}"
            logger.error(
                f"Tool '{tool_name}' execution error:\n"
                f"  Error: {e}\n"
                f"  Error Type: {type(e).__name__}\n"
                f"  Traceback:\n{traceback.format_exc()}"
            )
            return json.dumps({"error": error_msg})

    async def execute_all(self, tool_calls: list[Any]) -> list[dict[str, str]]:
        """
        批量执行多个工具调用

        Args:
            tool_calls: OpenAI tool_calls 列表

        Returns:
            工具调用结果列表，格式为：
            [
                {
                    "role": "tool",
                    "tool_call_id": "call_xxx",
                    "content": "result"
                },
                ...
            ]
        """
        results = []

        for tool_call in tool_calls:
            result = await self.execute(tool_call)
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

        logger.info(f"Executed {len(tool_calls)} tool calls")
        return results

    def clear(self):
        """清空所有已注册的工具"""
        count = len(self._tools)
        self._tools.clear()
        logger.info(f"Cleared {count} registered tools")
