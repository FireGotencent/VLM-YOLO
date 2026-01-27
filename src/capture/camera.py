"""
摄像头采集模块
负责从摄像头捕获视频帧
"""

import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger()


class CameraCapture:
    """摄像头采集类"""
    
    def __init__(
        self,
        device_id: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30
    ):
        """
        初始化摄像头
        
        Args:
            device_id: 摄像头设备ID
            width: 分辨率宽度
            height: 分辨率高度
            fps: 帧率
        """
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def open(self) -> bool:
        """
        打开摄像头
        
        Returns:
            bool: 是否成功打开
        """
        try:
            self._cap = cv2.VideoCapture(self.device_id)
            
            if not self._cap.isOpened():
                logger.error(f"无法打开摄像头 {self.device_id}")
                return False
            
            # 设置分辨率和帧率
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # 获取实际参数
            actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self._cap.get(cv2.CAP_PROP_FPS))
            
            logger.info(f"摄像头已打开: {actual_width}x{actual_height} @ {actual_fps}fps")
            return True
            
        except Exception as e:
            logger.error(f"打开摄像头失败: {e}")
            return False
    
    def close(self) -> None:
        """关闭摄像头"""
        self.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("摄像头已关闭")
    
    def start(self) -> None:
        """启动后台采集线程"""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("摄像头采集线程已启动")
    
    def stop(self) -> None:
        """停止后台采集线程"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
            logger.info("摄像头采集线程已停止")
    
    def _capture_loop(self) -> None:
        """采集循环（后台线程）"""
        frame_interval = 1.0 / self.fps
        
        while self._running and self._cap is not None:
            start_time = time.time()
            
            ret, frame = self._cap.read()
            if ret:
                with self._frame_lock:
                    self._frame = frame
            
            # 控制帧率
            elapsed = time.time() - start_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)
    
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        读取当前帧
        
        Returns:
            Tuple[bool, Optional[np.ndarray]]: (是否成功, 帧图像)
        """
        with self._frame_lock:
            if self._frame is None:
                return False, None
            return True, self._frame.copy()
    
    def read_sync(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        同步读取一帧（不使用后台线程）
        
        Returns:
            Tuple[bool, Optional[np.ndarray]]: (是否成功, 帧图像)
        """
        if self._cap is None:
            return False, None
        return self._cap.read()
    
    @property
    def is_opened(self) -> bool:
        """是否已打开"""
        return self._cap is not None and self._cap.isOpened()
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
    
    def get_frame_size(self) -> Tuple[int, int]:
        """
        获取帧尺寸
        
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        if self._cap is None:
            return 0, 0
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height
