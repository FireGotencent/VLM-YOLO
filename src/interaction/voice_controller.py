"""
语音交互控制器
整合 TTS 和 ASR，提供统一的语音交互接口
"""

from typing import Callable, Optional

from src.interaction.tts_engine import TTSEngine
from src.interaction.asr_engine import ASREngine
from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger()


class VoiceController:
    """语音交互控制器"""
    
    def __init__(self):
        """初始化语音控制器"""
        config = get_config()
        
        # 初始化 TTS
        self._tts = TTSEngine(
            rate=config.voice.tts.rate,
            volume=config.voice.tts.volume,
            language=config.voice.tts.language
        )
        
        # 初始化 ASR
        self._asr = ASREngine(
            language=config.voice.asr.language,
            timeout=config.voice.asr.timeout
        )
        
        self._command_callback: Optional[Callable[[str], None]] = None
    
    def initialize(self) -> bool:
        """
        初始化所有组件
        
        Returns:
            bool: 是否成功初始化
        """
        tts_ok = self._tts.initialize()
        asr_ok = self._asr.initialize()
        
        if tts_ok:
            self._tts.start()
        
        return tts_ok  # ASR 初始化失败不影响基本功能
    
    def speak(self, text: str, immediate: bool = False) -> None:
        """
        语音播报
        
        Args:
            text: 要播报的文本
            immediate: 是否立即播报（清空队列）
        """
        if immediate:
            self._tts.speak_now(text)
        else:
            self._tts.speak(text)
    
    def alert(self, message: str) -> None:
        """
        紧急警报（立即播报）
        
        Args:
            message: 警报信息
        """
        self._tts.speak_now(message)
    
    def listen(self) -> Optional[str]:
        """
        监听语音输入
        
        Returns:
            Optional[str]: 识别的文本
        """
        return self._asr.listen_once()
    
    def start_voice_commands(self, callback: Callable[[str], None]) -> None:
        """
        启动语音指令监听
        
        Args:
            callback: 指令回调函数
        """
        self._command_callback = callback
        self._asr.start_continuous(self._on_voice_command)
    
    def stop_voice_commands(self) -> None:
        """停止语音指令监听"""
        self._asr.stop_continuous()
        self._command_callback = None
    
    def _on_voice_command(self, text: str) -> None:
        """处理语音指令"""
        logger.info(f"收到语音指令: {text}")
        
        if self._command_callback:
            self._command_callback(text)
    
    def shutdown(self) -> None:
        """关闭所有组件"""
        self._tts.stop()
        self._asr.stop_continuous()
        logger.info("语音控制器已关闭")
    
    @property
    def tts(self) -> TTSEngine:
        """获取 TTS 引擎"""
        return self._tts
    
    @property
    def asr(self) -> ASREngine:
        """获取 ASR 引擎"""
        return self._asr
