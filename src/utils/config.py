"""
配置加载器模块
负责加载和管理全局配置
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel
from dotenv import load_dotenv


class CameraConfig(BaseModel):
    """摄像头配置"""
    # 摄像头类型: local / ip_webcam / droidcam / rtsp / http
    type: str = "local"
    device_id: int = 0
    # 网络摄像头配置
    network_source: str = ""
    network_port: int = 8080
    # 通用参数
    width: int = 1280
    height: int = 720
    fps: int = 30


class DetectionConfig(BaseModel):
    """目标检测配置"""
    model: str = "yolo26n.pt"
    confidence: float = 0.5
    iou_threshold: float = 0.45
    device: str = "auto"
    classes: list[str] = []


class OllamaConfig(BaseModel):
    """Ollama 配置"""
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"


class OpenAIConfig(BaseModel):
    """OpenAI 配置"""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None


class ClaudeConfig(BaseModel):
    """Claude 配置"""
    model: str = "claude-3-haiku-20240307"
    api_key: Optional[str] = None


class GeminiConfig(BaseModel):
    """Gemini 配置"""
    model: str = "gemini-2.5-flash"
    api_key: Optional[str] = None


class Gemma4Config(BaseModel):
    """Gemma 4 配置（与 Gemini 共用 GOOGLE_API_KEY）"""
    model: str = "gemma-4-26b-a4b-it"
    api_key: Optional[str] = None


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str = "ollama"
    ollama: OllamaConfig = OllamaConfig()
    openai: OpenAIConfig = OpenAIConfig()
    claude: ClaudeConfig = ClaudeConfig()
    gemini: GeminiConfig = GeminiConfig()
    gemma4: Gemma4Config = Gemma4Config()
    temperature: float = 0.7
    max_tokens: int = 512
    timeout: int = 30


class TTSConfig(BaseModel):
    """TTS 配置"""
    rate: int = 180
    volume: float = 0.9
    language: str = "zh"


class ASRConfig(BaseModel):
    """ASR 配置"""
    language: str = "zh-CN"
    timeout: int = 5


class VoiceConfig(BaseModel):
    """语音配置"""
    tts: TTSConfig = TTSConfig()
    asr: ASRConfig = ASRConfig()


class NavigationConfig(BaseModel):
    """导航配置"""
    warning_distance: float = 2.0
    danger_distance: float = 1.0
    update_interval: float = 1.0


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    file: str = "logs/vgllm.log"
    rotation: str = "10 MB"


class AppConfig(BaseModel):
    """应用程序总配置"""
    camera: CameraConfig = CameraConfig()
    detection: DetectionConfig = DetectionConfig()
    llm: LLMConfig = LLMConfig()
    voice: VoiceConfig = VoiceConfig()
    navigation: NavigationConfig = NavigationConfig()
    logging: LoggingConfig = LoggingConfig()


# 全局配置实例
_config: Optional[AppConfig] = None


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，默认为项目根目录的 config.yaml
        
    Returns:
        AppConfig: 配置对象
    """
    global _config
    
    # 加载环境变量
    load_dotenv()
    
    # 确定配置文件路径
    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config.yaml"
    else:
        config_path = Path(config_path)
    
    # 读取 YAML 配置
    config_dict = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}
    
    # 创建配置对象
    _config = AppConfig(**config_dict)
    
    # 从环境变量加载 API Keys
    _config.llm.openai.api_key = os.getenv("OPENAI_API_KEY")
    _config.llm.claude.api_key = os.getenv("ANTHROPIC_API_KEY")
    _config.llm.gemini.api_key = os.getenv("GOOGLE_API_KEY")
    _config.llm.gemma4.api_key = os.getenv("GOOGLE_API_KEY")
    
    return _config


def get_config() -> AppConfig:
    """
    获取全局配置实例
    
    Returns:
        AppConfig: 配置对象
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_value(key: str, default: Any = None) -> Any:
    """
    获取配置值（支持点号分隔的路径）
    
    Args:
        key: 配置键，如 "llm.provider"
        default: 默认值
        
    Returns:
        配置值
    """
    config = get_config()
    keys = key.split(".")
    value = config
    
    for k in keys:
        if hasattr(value, k):
            value = getattr(value, k)
        else:
            return default
    
    return value
