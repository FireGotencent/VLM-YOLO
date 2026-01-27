"""
语音识别 (ASR) 引擎模块
提供语音到文本的转换功能
"""

import threading
from typing import Callable, Optional

from src.utils.logger import get_logger

logger = get_logger()


class ASREngine:
    """语音识别引擎"""
    
    def __init__(
        self,
        language: str = "zh-CN",
        timeout: int = 5
    ):
        """
        初始化 ASR 引擎
        
        Args:
            language: 识别语言
            timeout: 监听超时时间（秒）
        """
        self.language = language
        self.timeout = timeout
        
        self._recognizer = None
        self._microphone = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[str], None]] = None
    
    def initialize(self) -> bool:
        """
        初始化引擎
        
        Returns:
            bool: 是否成功初始化
        """
        try:
            import speech_recognition as sr
            
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            
            # 调整环境噪音
            with self._microphone as source:
                logger.info("正在调整环境噪音...")
                self._recognizer.adjust_for_ambient_noise(source, duration=1)
            
            logger.info("ASR 引擎初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"ASR 引擎初始化失败: {e}")
            return False
    
    def listen_once(self) -> Optional[str]:
        """
        监听一次语音输入
        
        Returns:
            Optional[str]: 识别的文本，失败返回 None
        """
        if self._recognizer is None or self._microphone is None:
            if not self.initialize():
                return None
        
        try:
            import speech_recognition as sr
            
            with self._microphone as source:
                logger.info("正在监听...")
                audio = self._recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=10
                )
            
            logger.info("正在识别...")
            text = self._recognizer.recognize_google(
                audio,
                language=self.language
            )
            
            logger.info(f"识别结果: {text}")
            return text
            
        except Exception as e:
            logger.warning(f"语音识别失败: {e}")
            return None
    
    def start_continuous(self, callback: Callable[[str], None]) -> None:
        """
        启动连续监听模式
        
        Args:
            callback: 识别结果回调函数
        """
        if self._running:
            return
        
        if self._recognizer is None:
            if not self.initialize():
                return
        
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("ASR 连续监听已启动")
    
    def stop_continuous(self) -> None:
        """停止连续监听"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("ASR 连续监听已停止")
    
    def _listen_loop(self) -> None:
        """监听循环（后台线程）"""
        import speech_recognition as sr
        
        while self._running:
            try:
                with self._microphone as source:
                    audio = self._recognizer.listen(
                        source,
                        timeout=self.timeout,
                        phrase_time_limit=10
                    )
                
                text = self._recognizer.recognize_google(
                    audio,
                    language=self.language
                )
                
                if text and self._callback:
                    self._callback(text)
                    
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                logger.debug("无法识别语音")
            except Exception as e:
                logger.warning(f"监听错误: {e}")
    
    def set_language(self, language: str) -> None:
        """设置识别语言"""
        self.language = language
    
    def set_timeout(self, timeout: int) -> None:
        """设置监听超时"""
        self.timeout = max(1, timeout)
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
