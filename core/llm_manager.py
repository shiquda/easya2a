"""
LLM Manager - 统一的模型调用管理模块

功能：
- 支持多个LLM提供商（OpenAI, Anthropic等）
- 统一的异步调用接口
- 自动重试和错误处理
- Token计数和成本跟踪
- 配置管理
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Literal
from dataclasses import dataclass, field
from enum import Enum

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """支持的LLM提供商"""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"  # Ollama等本地模型


@dataclass
class LLMUsage:
    """LLM使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: 'LLMUsage') -> 'LLMUsage':
        return LLMUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class LLMResponse:
    """统一的LLM响应格式"""
    content: str
    model: str
    usage: LLMUsage
    finish_reason: str = "stop"
    raw_response: Any = None


class LLMConfig(BaseModel):
    """LLM配置"""
    provider: LLMProvider = Field(default=LLMProvider.OPENAI)
    model: str = Field(default="gpt-4")
    api_key: str | None = Field(default=None)
    base_url: str | None = Field(default=None)
    api_version: str | None = Field(default=None)  # Azure OpenAI需要
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    timeout: float = Field(default=60.0)
    max_retries: int = Field(default=3)

    class Config:
        use_enum_values = True


class LLMManager:
    """
    统一的LLM调用管理器

    使用示例:
        # 初始化
        manager = LLMManager(LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="sk-..."
        ))

        # 单次调用
        response = await manager.chat([
            {"role": "user", "content": "Hello"}
        ])

        # 流式调用
        async for chunk in manager.chat_stream([...]):
            print(chunk)
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._total_usage = LLMUsage()

    async def initialize(self):
        """初始化LLM客户端"""
        if self.config.provider == LLMProvider.OPENAI:
            kwargs = {
                "api_key": self.config.api_key,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
            }
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url

            self._client = AsyncOpenAI(**kwargs)
            logger.info(f"Initialized OpenAI client with model: {self.config.model}")

        elif self.config.provider == LLMProvider.AZURE_OPENAI:
            # Azure OpenAI 需要特殊配置
            from openai import AsyncAzureOpenAI

            if not self.config.base_url:
                raise ValueError("Azure OpenAI requires base_url (azure_endpoint)")
            if not self.config.api_version:
                raise ValueError("Azure OpenAI requires api_version")

            kwargs = {
                "api_key": self.config.api_key,
                "azure_endpoint": self.config.base_url,
                "api_version": self.config.api_version,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
            }

            self._client = AsyncAzureOpenAI(**kwargs)
            logger.info(f"Initialized Azure OpenAI client with deployment: {self.config.model}")

        elif self.config.provider == LLMProvider.ANTHROPIC:
            # TODO: 实现Anthropic客户端
            raise NotImplementedError("Anthropic provider not implemented yet")

        elif self.config.provider == LLMProvider.LOCAL:
            # TODO: 实现本地模型客户端
            raise NotImplementedError("Local provider not implemented yet")

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        发送聊天请求并获取完整响应

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            **kwargs: 额外参数覆盖配置

        Returns:
            LLMResponse对象
        """
        if not self._client:
            await self.initialize()

        # 准备请求参数
        params = {
            "model": kwargs.get("model", self.config.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        if self.config.max_tokens:
            params["max_tokens"] = kwargs.get("max_tokens", self.config.max_tokens)

        try:
            # 调用OpenAI API
            response = await self._client.chat.completions.create(**params)

            # 提取响应
            choice = response.choices[0]
            content = choice.message.content or ""

            # 统计使用情况
            usage = LLMUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            self._total_usage += usage

            logger.info(
                f"LLM call completed: {usage.total_tokens} tokens "
                f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
            )

            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=choice.finish_reason,
                raw_response=response,
            )

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs
    ) -> AsyncIterator[str]:
        """
        发送聊天请求并流式返回响应

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Yields:
            响应文本的增量块
        """
        if not self._client:
            await self.initialize()

        params = {
            "model": kwargs.get("model", self.config.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True,
        }

        if self.config.max_tokens:
            params["max_tokens"] = kwargs.get("max_tokens", self.config.max_tokens)

        try:
            stream = await self._client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except openai.APIError as e:
            logger.error(f"OpenAI API error in stream: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in LLM stream: {e}")
            raise

    def get_total_usage(self) -> LLMUsage:
        """获取总使用统计"""
        return self._total_usage

    def reset_usage(self):
        """重置使用统计"""
        self._total_usage = LLMUsage()

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.close()


# 全局LLM管理器实例
_managers: dict[str, LLMManager] = {}


def get_llm_manager(name: str = "default") -> LLMManager:
    """
    获取指定名称的LLM管理器

    Args:
        name: 管理器名称

    Returns:
        LLM管理器实例
    """
    if name not in _managers:
        raise ValueError(f"LLM manager '{name}' not found. Please register it first.")
    return _managers[name]


def register_llm_manager(name: str, config: LLMConfig) -> LLMManager:
    """
    注册一个新的LLM管理器

    Args:
        name: 管理器名称
        config: LLM配置

    Returns:
        创建的LLM管理器实例
    """
    manager = LLMManager(config)
    _managers[name] = manager
    logger.info(f"Registered LLM manager: {name} (provider: {config.provider}, model: {config.model})")
    return manager


async def cleanup_all_managers():
    """清理所有LLM管理器"""
    for name, manager in _managers.items():
        await manager.close()
        logger.info(f"Closed LLM manager: {name}")
    _managers.clear()
