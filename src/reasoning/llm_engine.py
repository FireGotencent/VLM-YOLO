"""
LLM 推理引擎模块
提供统一的大模型推理接口
"""

from typing import Dict, Generator, List, Optional

from src.reasoning.api_provider import LLMProvider, get_provider
from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger()


class LLMEngine:
    """LLM 推理引擎"""
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        """
        初始化推理引擎
        
        Args:
            provider: 提供商名称，默认从配置读取
            model: 模型名称，默认从配置读取
            **kwargs: 其他提供商参数
        """
        config = get_config()
        
        self.provider_name = provider or config.llm.provider
        self.temperature = config.llm.temperature
        self.max_tokens = config.llm.max_tokens
        self.timeout = config.llm.timeout
        
        # 根据提供商获取配置
        provider_config = self._get_provider_config(self.provider_name)
        provider_config.update(kwargs)
        
        if model:
            provider_config["model"] = model
        
        # 创建提供商实例
        self._provider: LLMProvider = get_provider(self.provider_name, **provider_config)
        
        # 对话历史
        self._history: List[Dict[str, str]] = []
        self._system_prompt: Optional[str] = None
        
        logger.info(f"LLM 引擎初始化完成 (提供商: {self.provider_name})")
    
    def _get_provider_config(self, provider_name: str) -> dict:
        """获取提供商配置"""
        config = get_config()
        
        if provider_name == "ollama":
            return {
                "base_url": config.llm.ollama.base_url,
                "model": config.llm.ollama.model
            }
        elif provider_name == "openai":
            return {
                "base_url": config.llm.openai.base_url,
                "model": config.llm.openai.model,
                "api_key": config.llm.openai.api_key
            }
        elif provider_name == "claude":
            return {
                "model": config.llm.claude.model,
                "api_key": config.llm.claude.api_key
            }
        elif provider_name == "gemini":
            return {
                "model": config.llm.gemini.model,
                "api_key": config.llm.gemini.api_key
            }
        else:
            return {}
    
    def set_system_prompt(self, prompt: str) -> None:
        """
        设置系统提示词
        
        Args:
            prompt: 系统提示词
        """
        self._system_prompt = prompt
        logger.debug(f"设置系统提示词: {prompt[:50]}...")
    
    def chat(
        self,
        message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_history: bool = True
    ) -> str:
        """
        执行对话
        
        Args:
            message: 用户消息
            temperature: 温度参数
            max_tokens: 最大 token 数
            use_history: 是否使用历史记录
            
        Returns:
            str: 模型回复
        """
        messages = self._build_messages(message, use_history)
        
        response = self._provider.chat(
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens
        )
        
        # 更新历史
        if use_history:
            self._history.append({"role": "user", "content": message})
            self._history.append({"role": "assistant", "content": response})
        
        return response
    
    def chat_stream(
        self,
        message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_history: bool = True
    ) -> Generator[str, None, None]:
        """
        流式对话
        
        Yields:
            str: 增量文本
        """
        messages = self._build_messages(message, use_history)
        
        full_response = ""
        for chunk in self._provider.chat_stream(
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens
        ):
            full_response += chunk
            yield chunk
        
        # 更新历史
        if use_history:
            self._history.append({"role": "user", "content": message})
            self._history.append({"role": "assistant", "content": full_response})
    
    def _build_messages(self, message: str, use_history: bool) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []
        
        # 添加系统提示词
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        
        # 添加历史记录
        if use_history:
            messages.extend(self._history)
        
        # 添加当前消息
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self._history.clear()
        logger.debug("对话历史已清空")
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self._history.copy()
    
    @property
    def provider(self) -> LLMProvider:
        """获取当前提供商实例"""
        return self._provider
