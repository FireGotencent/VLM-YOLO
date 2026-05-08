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
    """Google Gemini 提供商（google-genai 新版 SDK）"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash"
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("未设置 Google API Key，请在 .env 中配置 GOOGLE_API_KEY。")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _build_contents(self, messages: List[Dict[str, Any]]):
        """将统一格式消息转换为 Gemini contents 列表，返回 (system_instruction, contents)"""
        from google.genai import types
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=content)]))
            elif role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part(text=content)]))
        return system_instruction, contents

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        try:
            from google.genai import types
            client = self._get_client()
            system_instruction, contents = self._build_contents(messages)
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction,
            )
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
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
            from google.genai import types
            client = self._get_client()
            system_instruction, contents = self._build_contents(messages)
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction,
            )
            for chunk in client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini 流式调用失败: {e}")
            raise

    def chat_with_vision(
        self,
        messages: List[Dict[str, Any]],
        images: List[str],
        temperature: float = 0.7,
        max_tokens: int = 512,
        **kwargs
    ) -> str:
        """多模态对话，将图像附加到最后一条 user 消息"""
        try:
            from google.genai import types
            client = self._get_client()
            system_instruction, contents = self._build_contents(messages)

            # 把图像注入最后一条 user Content
            if images and contents:
                last_user_idx = next(
                    (i for i in range(len(contents) - 1, -1, -1)
                     if contents[i].role == "user"),
                    None
                )
                if last_user_idx is not None:
                    extra_parts = []
                    for img_path in images:
                        with open(img_path, "rb") as f:
                            img_bytes = f.read()
                        extra_parts.append(
                            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
                        )
                    contents[last_user_idx] = types.Content(
                        role="user",
                        parts=list(contents[last_user_idx].parts) + extra_parts,
                    )

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction,
            )
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini Vision 调用失败: {e}")
            raise


class Gemma4Provider(GeminiProvider):
    """Google Gemma 4 提供商（通过 Gemini API 调用，支持多模态）"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemma-4-26b-a4b-it"
    ):
        super().__init__(api_key=api_key, model=model)


# 提供商注册表
_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "gemma4": Gemma4Provider,
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
