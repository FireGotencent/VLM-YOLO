"""
语音合成 (TTS) 引擎模块
提供文本到语音的转换功能
"""

import queue
import threading
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger()


class TTSEngine:
    """语音合成引擎"""
    
    def __init__(
        self,
        rate: int = 180,
        volume: float = 0.9,
        language: str = "zh"
    ):
        """
        初始化 TTS 引擎
        
        Args:
            rate: 语速（词/分钟）
            volume: 音量 (0.0-1.0)
            language: 语言
        """
        self.rate = rate
        self.volume = volume
        self.language = language
        
        self._engine = None
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def initialize(self) -> bool:
        """
        初始化引擎
        
        Returns:
            bool: 是否成功初始化
        """
        try:
            import pyttsx3
            
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', self.rate)
            self._engine.setProperty('volume', self.volume)
            
            # 尝试设置中文语音
            voices = self._engine.getProperty('voices')
            for voice in voices:
                if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                    self._engine.setProperty('voice', voice.id)
                    logger.info(f"使用语音: {voice.name}")
                    break
            
            logger.info("TTS 引擎初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"TTS 引擎初始化失败: {e}")
            return False
    
    def start(self) -> None:
        """启动后台播放线程"""
        if self._running:
            return
        
        if self._engine is None:
            if not self.initialize():
                return
        
        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()
        logger.info("TTS 播放线程已启动")
    
    def stop(self) -> None:
        """停止播放线程"""
        self._running = False
        
        # 清空队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        
        # 添加停止信号
        self._queue.put(None)
        
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        logger.info("TTS 播放线程已停止")
    
    def speak(self, text: str, priority: int = 0) -> None:
        """
        添加文本到播放队列
        
        Args:
            text: 要朗读的文本
            priority: 优先级（数值越小优先级越高）
        """
        if not text:
            return
        
        self._queue.put((priority, text))
        logger.debug(f"添加到播放队列: {text[:30]}...")
    
    def speak_now(self, text: str) -> None:
        """
        立即播放（清空队列后插入）
        
        Args:
            text: 要朗读的文本
        """
        # 清空当前队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        
        # 停止当前播放
        if self._engine is not None:
            with self._lock:
                self._engine.stop()
        
        # 添加新文本
        self.speak(text, priority=-1)
    
    def speak_sync(self, text: str) -> None:
        """
        同步播放（阻塞直到完成）
        
        Args:
            text: 要朗读的文本
        """
        if self._engine is None:
            if not self.initialize():
                return
        
        with self._lock:
            self._engine.say(text)
            self._engine.runAndWait()
    
    def _playback_loop(self) -> None:
        """播放循环（后台线程）"""
        while self._running:
            try:
                item = self._queue.get(timeout=0.5)
                
                if item is None:  # 停止信号
                    break
                
                _, text = item
                
                with self._lock:
                    if self._engine is not None:
                        self._engine.say(text)
                        self._engine.runAndWait()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS 播放错误: {e}")
    
    def set_rate(self, rate: int) -> None:
        """设置语速"""
        self.rate = rate
        if self._engine is not None:
            with self._lock:
                self._engine.setProperty('rate', rate)
    
    def set_volume(self, volume: float) -> None:
        """设置音量"""
        self.volume = max(0.0, min(1.0, volume))
        if self._engine is not None:
            with self._lock:
                self._engine.setProperty('volume', self.volume)
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
    
    @property
    def queue_size(self) -> int:
        """队列中待播放的项目数"""
        return self._queue.qsize()
