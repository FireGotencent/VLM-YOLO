"""
LLM API 提供商抽象模块
支持多种 LLM 服务提供商的统一接口
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional

from src.utils.logger import get_logger

logger = get_logger()


class LLMProvider(ABC):
    """LLM 提供商抽象基类"""
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        """
        执行对话
        
        Args:
            messages: 消息列表 [{"role": "user/assistant", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            
        Returns:
            str: 模型回复
        """
        pass
    
    @abstractmethod
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        流式对话
        
        Yields:
            str: 增量文本
        """
        pass
    
    def chat_with_vision(
        self,
        messages: List[Dict[str, Any]],
        images: List[str],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        """
        带图像的对话（多模态）
        
        Args:
            messages: 消息列表
            images: 图像路径或 base64 编码列表
            
        Returns:
            str: 模型回复
        """
        raise NotImplementedError("该提供商不支持多模态对话")


class OllamaProvider(LLMProvider):
    """Ollama 本地提供商"""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b"
    ):
        self.base_url = base_url
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            import ollama
            self._client = ollama.Client(host=self.base_url)
        return self._client
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        try:
            client = self._get_client()
            response = client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama 调用失败: {e}")
            raise
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> Generator[str, None, None]:
        try:
            client = self._get_client()
            stream = client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens
                },
                stream=True
            )
            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama 流式调用失败: {e}")
            raise


class OpenAIProvider(LLMProvider):
    """OpenAI 提供商"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini"
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("未设置 OpenAI API Key，请在环境变量 OPENAI_API_KEY（或复制 .env.example 为 .env）中配置。")
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI 调用失败: {e}")
            raise
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> Generator[str, None, None]:
        try:
            client = self._get_client()
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI 流式调用失败: {e}")
            raise
    
    def chat_with_vision(
        self,
        messages: List[Dict[str, Any]],
        images: List[str],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        """支持 GPT-4V 的多模态对话"""
        import base64
        
        # 构建带图像的消息
        vision_messages = []
        for msg in messages:
            if msg["role"] == "user" and images:
                content = [{"type": "text", "text": msg["content"]}]
                for img_path in images:
                    with open(img_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}
                    })
                vision_messages.append({"role": "user", "content": content})
            else:
                vision_messages.append(msg)
        
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=vision_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI Vision 调用失败: {e}")
            raise


class ClaudeProvider(LLMProvider):
    """Anthropic Claude 提供商"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-haiku-20240307"
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        try:
            client = self._get_client()
            
            # 提取 system 消息
            system = ""
            chat_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system = msg["content"]
                else:
                    chat_messages.append(msg)
            
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system if system else None,
                messages=chat_messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude 调用失败: {e}")
            raise
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> Generator[str, None, None]:
        try:
            client = self._get_client()
            
            system = ""
            chat_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system = msg["content"]
                else:
                    chat_messages.append(msg)
            
            with client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system if system else None,
                messages=chat_messages
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Claude 流式调用失败: {e}")
            raise


class GeminiProvider(LLMProvider):
    """Google Gemini 提供商"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash"
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        try:
            client = self._get_client()
            
            # 转换消息格式
            history = []
            for msg in messages[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                history.append({"role": role, "parts": [msg["content"]]})
            
            chat = client.start_chat(history=history)
            response = chat.send_message(
                messages[-1]["content"],
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens
                }
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini 调用失败: {e}")
            raise
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> Generator[str, None, None]:
        try:
            client = self._get_client()
            
            history = []
            for msg in messages[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                history.append({"role": role, "parts": [msg["content"]]})
            
            chat = client.start_chat(history=history)
            response = chat.send_message(
                messages[-1]["content"],
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens
                },
                stream=True
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini 流式调用失败: {e}")
            raise


# 提供商注册表
_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
}


def get_provider(provider_name: str, **kwargs) -> LLMProvider:
    """
    获取 LLM 提供商实例
    
    Args:
        provider_name: 提供商名称 (ollama/openai/claude/gemini)
        **kwargs: 提供商特定参数
        
    Returns:
        LLMProvider: 提供商实例
    """
    if provider_name not in _PROVIDERS:
        raise ValueError(f"不支持的提供商: {provider_name}")
    
    return _PROVIDERS[provider_name](**kwargs)


def list_providers() -> List[str]:
    """获取支持的提供商列表"""
    return list(_PROVIDERS.keys())
