"""
网络摄像头采集模块
支持 IP Webcam、RTSP 流等网络摄像头源
"""

import threading
import time
from typing import Optional, Tuple, Union
from enum import Enum

import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger()


class CameraType(Enum):
    """摄像头类型"""
    LOCAL = "local"           # 本地摄像头
    IP_WEBCAM = "ip_webcam"   # IP Webcam (Android App)
    RTSP = "rtsp"             # RTSP 流
    HTTP = "http"             # HTTP 流
    DROIDCAM = "droidcam"     # DroidCam


class NetworkCamera:
    """
    网络摄像头类
    
    支持多种网络摄像头源:
    1. IP Webcam (Android): http://<phone_ip>:8080/video
    2. DroidCam: http://<phone_ip>:4747/video
    3. RTSP: rtsp://<ip>:<port>/stream
    4. HTTP MJPEG: http://<ip>/mjpeg
    """
    
    # 常用 App 的默认端口和路径
    APP_CONFIGS = {
        CameraType.IP_WEBCAM: {
            "port": 8080,
            "video_path": "/video",
            "shot_path": "/shot.jpg",
            "focus_path": "/focus",
        },
        CameraType.DROIDCAM: {
            "port": 4747,
            "video_path": "/video",
        },
    }
    
    def __init__(
        self,
        source: Union[int, str] = 0,
        camera_type: CameraType = CameraType.LOCAL,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        reconnect_delay: float = 3.0
    ):
        """
        初始化网络摄像头
        
        Args:
            source: 摄像头源
                - 本地摄像头: 设备ID (int)
                - IP Webcam: 手机IP地址 (str), 如 "192.168.1.100"
                - RTSP: 完整 RTSP URL
                - HTTP: 完整 HTTP URL
            camera_type: 摄像头类型
            width: 期望分辨率宽度
            height: 期望分辨率高度
            fps: 期望帧率
            reconnect_delay: 断线重连延迟（秒）
        """
        self.source = source
        self.camera_type = camera_type
        self.width = width
        self.height = height
        self.fps = fps
        self.reconnect_delay = reconnect_delay
        
        self._url: str = ""
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._reconnect_count = 0
        
        # 构建 URL
        self._build_url()
    
    def _build_url(self) -> None:
        """根据配置构建视频流 URL"""
        if self.camera_type == CameraType.LOCAL:
            self._url = str(self.source)
            return
        
        if self.camera_type in (CameraType.RTSP, CameraType.HTTP):
            # 完整 URL，直接使用
            self._url = str(self.source)
            return
        
        # IP Webcam 或 DroidCam
        ip = str(self.source)
        config = self.APP_CONFIGS.get(self.camera_type, {})
        port = config.get("port", 8080)
        video_path = config.get("video_path", "/video")
        
        self._url = f"http://{ip}:{port}{video_path}"
    
    @classmethod
    def from_ip_webcam(
        cls,
        phone_ip: str,
        port: int = 8080,
        **kwargs
    ) -> "NetworkCamera":
        """
        从 IP Webcam App 创建摄像头
        
        Args:
            phone_ip: 手机 IP 地址
            port: 端口号（默认 8080）
            
        Returns:
            NetworkCamera: 摄像头实例
            
        使用方法:
            1. 在 Android 手机上安装 "IP Webcam" App
            2. 打开 App，点击 "Start server"
            3. 记下显示的 IP 地址（如 192.168.1.100:8080）
            4. 在代码中调用:
               camera = NetworkCamera.from_ip_webcam("192.168.1.100")
        """
        url = f"http://{phone_ip}:{port}/video"
        return cls(source=url, camera_type=CameraType.HTTP, **kwargs)
    
    @classmethod
    def from_droidcam(
        cls,
        phone_ip: str,
        port: int = 4747,
        **kwargs
    ) -> "NetworkCamera":
        """
        从 DroidCam App 创建摄像头
        
        Args:
            phone_ip: 手机 IP 地址
            port: 端口号（默认 4747）
            
        Returns:
            NetworkCamera: 摄像头实例
            
        使用方法:
            1. 在手机上安装 "DroidCam" App
            2. 打开 App，记下显示的 IP 地址
            3. 在代码中调用:
               camera = NetworkCamera.from_droidcam("192.168.1.100")
        """
        url = f"http://{phone_ip}:{port}/video"
        return cls(source=url, camera_type=CameraType.HTTP, **kwargs)
    
    @classmethod
    def from_rtsp(
        cls,
        rtsp_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ) -> "NetworkCamera":
        """
        从 RTSP 流创建摄像头
        
        Args:
            rtsp_url: RTSP URL
            username: 用户名（可选）
            password: 密码（可选）
            
        Returns:
            NetworkCamera: 摄像头实例
            
        示例 RTSP URL:
            - rtsp://192.168.1.100:554/stream
            - rtsp://admin:password@192.168.1.100:554/h264
        """
        if username and password:
            # 插入认证信息
            rtsp_url = rtsp_url.replace("rtsp://", f"rtsp://{username}:{password}@")
        return cls(source=rtsp_url, camera_type=CameraType.RTSP, **kwargs)
    
    def open(self) -> bool:
        """
        打开摄像头连接
        
        Returns:
            bool: 是否成功打开
        """
        try:
            if self.camera_type == CameraType.LOCAL:
                self._cap = cv2.VideoCapture(int(self.source))
            else:
                # 网络流使用 FFMPEG 后端
                self._cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
                
                # 设置缓冲区大小（减少延迟）
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not self._cap.isOpened():
                logger.error(f"无法打开摄像头: {self._url}")
                return False
            
            # 设置分辨率（仅本地摄像头有效）
            if self.camera_type == CameraType.LOCAL:
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self._cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # 读取一帧测试连接
            ret, frame = self._cap.read()
            if not ret:
                logger.error("无法读取视频帧")
                return False
            
            self._connected = True
            self._reconnect_count = 0
            
            actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.info(f"摄像头已连接: {self._url}")
            logger.info(f"分辨率: {actual_width}x{actual_height}")
            
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
        self._connected = False
        logger.info("摄像头已关闭")
    
    def start(self) -> None:
        """启动后台采集线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("网络摄像头采集线程已启动")
    
    def stop(self) -> None:
        """停止后台采集线程"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("网络摄像头采集线程已停止")
    
    def _capture_loop(self) -> None:
        """采集循环（后台线程）"""
        frame_interval = 1.0 / self.fps
        consecutive_failures = 0
        max_failures = 10
        
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self._try_reconnect()
                continue
            
            start_time = time.time()
            
            try:
                ret, frame = self._cap.read()
                
                if ret and frame is not None:
                    with self._frame_lock:
                        self._frame = frame
                    consecutive_failures = 0
                    self._connected = True
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.warning("连续读取失败，尝试重连...")
                        self._connected = False
                        self._try_reconnect()
                        consecutive_failures = 0
                
            except Exception as e:
                logger.error(f"采集错误: {e}")
                consecutive_failures += 1
            
            # 控制帧率
            elapsed = time.time() - start_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)
    
    def _try_reconnect(self) -> None:
        """尝试重新连接"""
        self._reconnect_count += 1
        logger.info(f"尝试重新连接... (第 {self._reconnect_count} 次)")
        
        if self._cap is not None:
            self._cap.release()
        
        time.sleep(self.reconnect_delay)
        
        if self.open():
            logger.info("重新连接成功")
        else:
            logger.warning("重新连接失败")
    
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
        """同步读取一帧"""
        if self._cap is None:
            return False, None
        return self._cap.read()
    
    @property
    def url(self) -> str:
        """获取视频流 URL"""
        return self._url
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
    
    def get_frame_size(self) -> Tuple[int, int]:
        """获取帧尺寸"""
        if self._cap is None:
            return 0, 0
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height


# 便捷函数
def create_phone_camera(
    phone_ip: str,
    app: str = "ip_webcam",
    **kwargs
) -> NetworkCamera:
    """
    创建手机摄像头的便捷函数
    
    Args:
        phone_ip: 手机 IP 地址
        app: 使用的 App ("ip_webcam" 或 "droidcam")
        
    Returns:
        NetworkCamera: 摄像头实例
        
    示例:
        # 使用 IP Webcam App
        camera = create_phone_camera("192.168.1.100", app="ip_webcam")
        
        # 使用 DroidCam App  
        camera = create_phone_camera("192.168.1.100", app="droidcam")
    """
    if app.lower() == "ip_webcam":
        return NetworkCamera.from_ip_webcam(phone_ip, **kwargs)
    elif app.lower() == "droidcam":
        return NetworkCamera.from_droidcam(phone_ip, **kwargs)
    else:
        raise ValueError(f"不支持的 App: {app}")
