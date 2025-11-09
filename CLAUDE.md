# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 A2A (Agent-to-Agent) 协议的多智能体系统，使用 Python 实现。系统支持在单进程中运行多个独立的 Agent，每个 Agent 监听不同端口，通过统一的配置文件管理。

## 开发环境

- **包管理器**: 使用 `uv` (不是 pip)
- **Python版本**: >= 3.13
- **运行命令**: `uv run <script.py>`
- **依赖安装**: `uv sync`

## 常用命令

### 开发运行
```bash
# 启动多Agent服务器
uv run main.py

# 配置文件路径：config/agents.yaml
# 如果不存在，复制 config/agents.example.yaml 为 config/agents.yaml
```

### 测试
```bash
# 测试Agent Card（需要服务器运行）
curl http://localhost:9001/api/v1/agent/card

# 使用官方调试工具
npx @a2aprotocol/inspector http://localhost:9001
```

## 核心架构

### 1. 配置驱动的多Agent系统

**配置文件结构** (`config/agents.yaml`):
- `system`: 系统级配置（日志等）
- `llm_providers`: 全局LLM提供商配置（OpenAI, Azure OpenAI等）
- `agents`: Agent列表配置

**重要原则**:
- 所有 Agent 配置集中在 `config/agents.yaml`
- LLM 配置统一在 `llm_providers` 管理，避免重复
- Agent 通过引用 `llm_provider` 名称使用 LLM
- 支持环境变量替换：`${VAR_NAME}` 格式

### 2. 三层架构

```
main.py (入口层)
   ↓
core/ (核心层)
├── config.py        # 配置管理和验证
├── llm_manager.py   # 统一LLM调用接口
└── server.py        # 多端口服务器管理
   ↓
agents/ (Agent层)
├── base/            # 抽象基类
│   ├── base_agent.py      # BaseAgent: 业务逻辑基类
│   └── base_executor.py   # BaseAgentExecutor: A2A协议执行器基类
├── echo/            # Echo Agent实现
└── llm/             # LLM Agent实现
```

**关键概念**:
- **Agent**: 业务逻辑实现（继承 `BaseAgent`）
- **Executor**: A2A协议适配器（继承 `BaseAgentExecutor` 或 `SimpleAgentExecutor`）
- **分离关注点**: Agent 专注业务逻辑，Executor 专注协议实现

### 3. LLM管理器系统

**核心特性**:
- 支持多provider: OpenAI, Azure OpenAI（Anthropic和Local待实现）
- 全局注册机制：`register_llm_manager(name, config)`
- 统一接口：`chat()` 和 `chat_stream()`
- 自动重试、错误处理、Token统计

**使用模式**（见 `main.py:96-119`）:
1. 从配置加载 LLMConfigModel
2. 转换为 LLMConfig 并注册
3. 传给 LLM Agent 使用

### 4. Agent独立性原则

**设计哲学**: 每个 Agent 完全独立，无内部依赖关系
- Agent 之间通过 A2A 协议通信（外部调用）
- 不在代码中硬编码 Agent 间的调用关系
- 依赖关系由外部系统（如 Coordinator）管理

## 添加新Agent类型

### 步骤1: 实现Agent业务逻辑

```python
# agents/custom/my_agent.py
from agents.base import BaseAgent

class MyAgent(BaseAgent):
    async def invoke(self, input_data=None):
        # 实现你的逻辑
        return "Response"

    async def initialize(self):
        # 可选：初始化资源
        pass

    async def cleanup(self):
        # 可选：清理资源
        pass
```

### 步骤2: 创建Executor

```python
# agents/custom/my_executor.py
from agents.base import SimpleAgentExecutor
from .my_agent import MyAgent

class MyAgentExecutor(SimpleAgentExecutor):
    def __init__(self, name="MyAgent"):
        agent = MyAgent(name=name)
        super().__init__(agent)
```

### 步骤3: 在main.py中注册

在 `build_agent_executor()` 函数中添加（main.py:79-123）:
```python
elif agent_config.type == "my_custom_type":
    return MyAgentExecutor(name=agent_config.name)
```

### 步骤4: 添加到配置文件

在 `config/agents.yaml` 中添加:
```yaml
agents:
  - name: my-agent
    description: "My custom agent"
    type: my_custom_type
    host: 0.0.0.0
    port: 9010
```

## 代码定位参考

### 配置相关
- 配置模型定义：`core/config.py:25-119`
- 配置加载逻辑：`core/config.py:144-176`
- 配置验证：`core/config.py:102-118`
- 环境变量展开：`core/config.py:38-47`

### LLM相关
- LLM配置和初始化：`core/llm_manager.py:105-174`
- Chat调用实现：`core/llm_manager.py:176-288`
- 流式调用实现：`core/llm_manager.py:290-360`
- 全局注册机制：`core/llm_manager.py:395-409`

### Agent实现
- LLM Agent核心逻辑：`agents/llm/llm_agent.py:58-98`
- 消息准备逻辑：`agents/llm/llm_agent.py:100-125`
- Echo Agent示例：`agents/echo/echo_agent.py`

### 启动流程
- 主入口：`main.py:169-204`
- Agent Card构建：`main.py:29-76`
- Agent Executor构建：`main.py:79-123`
- FastAPI应用构建：`main.py:125-166`

## 重要注意事项

### 环境变量
- API密钥**必须**通过环境变量配置
- 格式：`${OPENAI_API_KEY}` 在 YAML 中
- 在运行前设置：`export OPENAI_API_KEY=sk-...`

### 端口管理
- 每个 Agent 必须使用唯一端口
- 配置验证会检查端口冲突（config.py:111-118）
- 默认端口范围：9001-9004+

### SSL验证
- LLM管理器支持 `verify_ssl: false` 禁用SSL验证
- **仅用于开发/测试环境**
- 生产环境必须启用SSL验证

### 日志
- 使用Python标准logging模块
- 日志级别在 `config/agents.yaml` 的 `system.log_level` 配置
- 详细调试信息已在 LLM Manager 中实现

## A2A协议相关

### 已实现特性
- Agent Card元数据
- 文本消息交换
- 流式响应支持
- 多轮对话
- Provider信息

### 调试工具
- 官方Inspector: `npx @a2aprotocol/inspector <url>`
- 文档查询: 使用Context7工具查询A2A协议细节
- GitHub查询: 使用DeepWiki工具与a2a相关仓库对话

## 待实现功能

基于README中提到的改进方向（README.md:343-350）:
1. **Anthropic Provider**: 在 `core/llm_manager.py:168-170` 添加实现
2. **Local Model Provider**: 在 `core/llm_manager.py:172-174` 添加实现
3. **流式响应完善**: StreamingLLMAgent的executor集成
4. **Agent协作**: 实现Coordinator模式
5. **持久化存储**: 替换InMemoryTaskStore
6. **Docker支持**: 添加Dockerfile

## 配置示例参考

完整配置示例见 `config/agents.example.yaml`，包含：
- OpenAI标准配置
- Azure OpenAI配置
- 多种用途的LLM配置（通用/代码/快速）
- 不同类型Agent的配置示例

## Git提交规范

- 使用约定式提交（Conventional Commits）
- 类型：feat, fix, docs, refactor等
- **不包含** Claude Code Co-Author信息（根据用户配置）
