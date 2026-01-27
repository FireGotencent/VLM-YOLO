"""
TTS 语音播报客户端
跨平台语音合成
"""

import threading
import queue
from typing import Optional

# 尝试导入 plyer (跨平台)
try:
    from plyer import tts as plyer_tts
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

# 尝试导入 pyttsx3 (桌面平台)
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False


class TTSClient:
    """TTS 语音播报客户端"""
    
    def __init__(self, rate: int = 180, volume: float = 0.9):
        """
        初始化 TTS 客户端
        
        Args:
            rate: 语速
            volume: 音量 (0.0-1.0)
        """
        self.rate = rate
        self.volume = volume
        
        self._engine = None
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_text: str = ""
        self._platform = "unknown"
        
        self._initialize()
    
    def _initialize(self) -> None:
        """初始化 TTS 引擎"""
        if HAS_PLYER:
            # 使用 plyer（Android/iOS）
            self._platform = "plyer"
            print("使用 plyer TTS")
        elif HAS_PYTTSX3:
            # 使用 pyttsx3（桌面）
            self._platform = "pyttsx3"
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', self.rate)
            self._engine.setProperty('volume', self.volume)
            print("使用 pyttsx3 TTS")
        else:
            print("警告: 没有可用的 TTS 引擎")
    
    def start(self) -> None:
        """启动播报线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """停止播报"""
        self._running = False
        
        # 清空队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        
        if self._thread:
            self._thread.join(timeout=1.0)
    
    def speak(self, text: str, interrupt: bool = False) -> None:
        """
        播报文本
        
        Args:
            text: 要播报的文本
            interrupt: 是否打断当前播报
        """
        if not text or text == self._last_text:
            return
        
        if interrupt:
            # 清空队列
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
        
        self._queue.put(text)
        self._last_text = text
    
    def _playback_loop(self) -> None:
        """播报循环"""
        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                self._speak_sync(text)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS 错误: {e}")
    
    def _speak_sync(self, text: str) -> None:
        """同步播报"""
        try:
            if self._platform == "plyer":
                plyer_tts.speak(text)
            elif self._platform == "pyttsx3" and self._engine:
                self._engine.say(text)
                self._engine.runAndWait()
            else:
                print(f"[TTS] {text}")
        except Exception as e:
            print(f"播报失败: {e}")
    
    def clear_last(self) -> None:
        """清除上次播报记录（允许重复播报）"""
        self._last_text = ""
