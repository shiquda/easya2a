"""
配置管理模块

功能：
- 从YAML文件加载Agent配置
- 支持环境变量替换
- 类型安全的配置访问
- 验证配置完整性
"""

import os
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from core.llm_manager import LLMProvider


logger = logging.getLogger(__name__)


class LLMConfigModel(BaseModel):
    """LLM配置模型"""
    provider: LLMProvider = Field(default=LLMProvider.OPENAI)
    model: str = Field(...)
    api_key: str | None = Field(default=None)
    base_url: str | None = Field(default=None)
    api_version: str | None = Field(default=None)  # Azure OpenAI 需要
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    timeout: float = Field(default=60.0)
    max_retries: int = Field(default=3)

    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def expand_env_vars(cls, v: str | None) -> str | None:
        """展开环境变量，支持 ${VAR_NAME} 格式"""
        if v is None:
            return v
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            var_name = v[2:-1]
            return os.getenv(var_name)
        return v

    class Config:
        use_enum_values = True


class ProviderInfo(BaseModel):
    """Agent提供者信息"""
    organization: str = Field(...)
    url: str | None = Field(default=None)
    email: str | None = Field(default=None)


class AgentConfigModel(BaseModel):
    """单个Agent的配置模型"""
    name: str = Field(...)
    description: str = Field(...)
    type: str = Field(...)  # echo, llm, custom等
    host: str = Field(default="0.0.0.0")
    port: int = Field(..., gt=0, lt=65536)
    url: str | None = Field(default=None)

    # Provider信息（可选）
    provider: ProviderInfo | None = Field(default=None)

    # LLM Provider引用（可选，引用全局llm_providers中的配置名称）
    llm_provider: str | None = Field(default=None)

    # 额外配置
    extra: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context):
        """初始化后自动生成URL"""
        if not self.url:
            # 如果host是0.0.0.0，使用localhost
            display_host = 'localhost' if self.host == '0.0.0.0' else self.host
            self.url = f"http://{display_host}:{self.port}"


class SystemConfigModel(BaseModel):
    """系统级配置"""
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class AppConfigModel(BaseModel):
    """应用总配置模型"""
    system: SystemConfigModel = Field(default_factory=SystemConfigModel)

    # 全局LLM Providers配置
    llm_providers: dict[str, LLMConfigModel] = Field(default_factory=dict)

    # Agent配置列表
    agents: list[AgentConfigModel] = Field(...)

    @field_validator("agents")
    @classmethod
    def validate_unique_names(cls, v: list[AgentConfigModel]) -> list[AgentConfigModel]:
        """验证Agent名称唯一性"""
        names = [agent.name for agent in v]
        if len(names) != len(set(names)):
            raise ValueError("Agent names must be unique")
        return v

    @field_validator("agents")
    @classmethod
    def validate_unique_ports(cls, v: list[AgentConfigModel]) -> list[AgentConfigModel]:
        """验证端口唯一性"""
        ports = [agent.port for agent in v]
        if len(ports) != len(set(ports)):
            raise ValueError("Agent ports must be unique")
        return v


class ConfigManager:
    """
    配置管理器

    使用示例:
        # 加载配置
        config = ConfigManager.load_from_file("config/agents.yaml")

        # 获取所有agent配置
        agents = config.get_all_agents()

        # 获取特定agent配置
        echo_agent = config.get_agent("echo")

        # 获取系统配置
        system = config.get_system_config()
    """

    def __init__(self, config: AppConfigModel):
        self._config = config
        self._agents_by_name = {agent.name: agent for agent in config.agents}
        logger.info(f"Loaded configuration with {len(config.agents)} agents")

    @classmethod
    def load_from_file(cls, config_path: str | Path) -> "ConfigManager":
        """
        从YAML文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            ConfigManager实例

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置验证失败
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        # 读取YAML
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)

        # 验证并创建配置对象
        try:
            config = AppConfigModel(**raw_config)
        except Exception as e:
            logger.error(f"Failed to validate config: {e}")
            raise ValueError(f"Invalid configuration: {e}") from e

        logger.info(f"Successfully loaded config from {config_path}")
        return cls(config)

    @classmethod
    def load_from_dict(cls, config_dict: dict) -> "ConfigManager":
        """
        从字典加载配置（用于测试）

        Args:
            config_dict: 配置字典

        Returns:
            ConfigManager实例
        """
        config = AppConfigModel(**config_dict)
        return cls(config)

    def get_all_agents(self) -> list[AgentConfigModel]:
        """获取所有Agent配置"""
        return self._config.agents

    def get_agent(self, name: str) -> AgentConfigModel:
        """
        根据名称获取Agent配置

        Args:
            name: Agent名称

        Returns:
            AgentConfigModel

        Raises:
            KeyError: Agent不存在
        """
        if name not in self._agents_by_name:
            raise KeyError(f"Agent '{name}' not found in configuration")
        return self._agents_by_name[name]

    def has_agent(self, name: str) -> bool:
        """检查Agent是否存在"""
        return name in self._agents_by_name

    def get_system_config(self) -> SystemConfigModel:
        """获取系统配置"""
        return self._config.system

    def get_agents_by_type(self, agent_type: str) -> list[AgentConfigModel]:
        """
        根据类型获取Agent配置列表

        Args:
            agent_type: Agent类型（echo, llm, custom等）

        Returns:
            匹配的Agent配置列表
        """
        return [agent for agent in self._config.agents if agent.type == agent_type]

    def get_llm_provider(self, name: str) -> LLMConfigModel:
        """
        获取LLM Provider配置

        Args:
            name: Provider名称

        Returns:
            LLMConfigModel

        Raises:
            KeyError: Provider不存在
        """
        if name not in self._config.llm_providers:
            raise KeyError(f"LLM provider '{name}' not found in configuration")
        return self._config.llm_providers[name]

    def get_all_llm_providers(self) -> dict[str, LLMConfigModel]:
        """获取所有LLM Provider配置"""
        return self._config.llm_providers


# 全局配置管理器实例
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器

    Returns:
        ConfigManager实例

    Raises:
        RuntimeError: 配置未初始化
    """
    if _config_manager is None:
        raise RuntimeError("Config manager not initialized. Call initialize_config() first.")
    return _config_manager


def initialize_config(config_path: str | Path) -> ConfigManager:
    """
    初始化全局配置管理器

    Args:
        config_path: 配置文件路径

    Returns:
        ConfigManager实例
    """
    global _config_manager
    _config_manager = ConfigManager.load_from_file(config_path)
    logger.info("Global config manager initialized")
    return _config_manager


def is_config_initialized() -> bool:
    """检查配置是否已初始化"""
    return _config_manager is not None
