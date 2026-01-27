"""
帧缓冲管理模块
提供线程安全的帧缓冲区
"""

import threading
from collections import deque
from typing import Optional

import numpy as np


class FrameBuffer:
    """帧缓冲区类"""
    
    def __init__(self, max_size: int = 5):
        """
        初始化帧缓冲区
        
        Args:
            max_size: 缓冲区最大容量
        """
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
    
    def put(self, frame: np.ndarray, timestamp: Optional[float] = None) -> None:
        """
        放入一帧
        
        Args:
            frame: 帧图像
            timestamp: 时间戳（可选）
        """
        import time
        if timestamp is None:
            timestamp = time.time()
            
        with self._lock:
            self._buffer.append((frame.copy(), timestamp))
    
    def get(self) -> Optional[tuple]:
        """
        获取最新一帧
        
        Returns:
            Optional[tuple]: (帧图像, 时间戳) 或 None
        """
        with self._lock:
            if len(self._buffer) == 0:
                return None
            return self._buffer[-1]
    
    def get_all(self) -> list:
        """
        获取所有帧
        
        Returns:
            list: [(帧图像, 时间戳), ...]
        """
        with self._lock:
            return list(self._buffer)
    
    def clear(self) -> None:
        """清空缓冲区"""
        with self._lock:
            self._buffer.clear()
    
    def __len__(self) -> int:
        """获取当前帧数"""
        with self._lock:
            return len(self._buffer)
    
    @property
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self) == 0
    
    @property
    def is_full(self) -> bool:
        """是否已满"""
        return len(self) >= self.max_size
