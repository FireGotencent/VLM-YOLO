"""
主窗口模块
VisionGuide LLM System 的主界面
"""

import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, 
    QSplitter, QVBoxLayout, QWidget
)

import numpy as np

from src.capture.camera import CameraCapture
from src.detection.yolo_detector import YOLODetector, Detection
from src.fusion.scene_encoder import SceneEncoder
from src.reasoning.navigation_advisor import NavigationAdvisor
from src.interaction.voice_controller import VoiceController
from src.ui.components.video_widget import VideoWidget
from src.ui.components.control_panel import ControlPanel
from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger()


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        self._config = get_config()
        self._camera: Optional[CameraCapture] = None
        self._detector: Optional[YOLODetector] = None
        self._advisor: Optional[NavigationAdvisor] = None
        self._voice: Optional[VoiceController] = None
        self._scene_encoder: Optional[SceneEncoder] = None
        
        self._timer: Optional[QTimer] = None
        self._last_time = time.time()
        self._frame_count = 0
        self._last_announcement_time = 0
        
        self._setup_ui()
        self._setup_modules()
        
        logger.info("主窗口初始化完成")
    
    def _setup_ui(self):
        """设置 UI"""
        self.setWindowTitle("VisionGuide LLM System - 盲人避障导航系统")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f0f1a;
            }
        """)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 布局
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 视频显示区域
        self.video_widget = VideoWidget()
        splitter.addWidget(self.video_widget)
        
        # 控制面板
        self.control_panel = ControlPanel()
        self.control_panel.setMaximumWidth(350)
        self.control_panel.start_clicked.connect(self._on_start)
        self.control_panel.stop_clicked.connect(self._on_stop)
        self.control_panel.voice_toggled.connect(self._on_voice_toggled)
        self.control_panel.provider_changed.connect(self._on_provider_changed)
        splitter.addWidget(self.control_panel)
        
        # 设置分割比例
        splitter.setSizes([900, 350])
        
        layout.addWidget(splitter)
        
        # 定时器
        self._timer = QTimer()
        self._timer.timeout.connect(self._process_frame)
    
    def _setup_modules(self):
        """初始化各模块"""
        try:
            # 根据配置创建摄像头
            camera_type = getattr(self._config.camera, 'type', 'local')
            
            if camera_type == 'local':
                # 本地摄像头
                self._camera = CameraCapture(
                    device_id=self._config.camera.device_id,
                    width=self._config.camera.width,
                    height=self._config.camera.height,
                    fps=self._config.camera.fps
                )
                self.control_panel.add_log("📷 使用本地摄像头")
            else:
                # 网络摄像头
                from src.capture.network_camera import NetworkCamera, CameraType
                
                network_source = getattr(self._config.camera, 'network_source', '')
                network_port = getattr(self._config.camera, 'network_port', 8080)
                
                if camera_type == 'ip_webcam':
                    self._camera = NetworkCamera.from_ip_webcam(
                        network_source, 
                        port=network_port,
                        width=self._config.camera.width,
                        height=self._config.camera.height,
                        fps=self._config.camera.fps
                    )
                    self.control_panel.add_log(f"📱 使用 IP Webcam: {network_source}")
                elif camera_type == 'droidcam':
                    self._camera = NetworkCamera.from_droidcam(
                        network_source,
                        port=network_port,
                        width=self._config.camera.width,
                        height=self._config.camera.height,
                        fps=self._config.camera.fps
                    )
                    self.control_panel.add_log(f"📱 使用 DroidCam: {network_source}")
                elif camera_type in ('rtsp', 'http'):
                    self._camera = NetworkCamera(
                        source=network_source,
                        camera_type=CameraType.RTSP if camera_type == 'rtsp' else CameraType.HTTP,
                        width=self._config.camera.width,
                        height=self._config.camera.height,
                        fps=self._config.camera.fps
                    )
                    self.control_panel.add_log(f"🌐 使用网络流: {network_source}")
                else:
                    raise ValueError(f"未知的摄像头类型: {camera_type}")
            
            # YOLO 检测器
            self._detector = YOLODetector(
                model_path=self._config.detection.model,
                confidence=self._config.detection.confidence,
                target_classes=self._config.detection.classes
            )
            
            # 场景编码器
            self._scene_encoder = SceneEncoder(self._detector)
            
            # 语音控制器
            self._voice = VoiceController()
            self._voice.initialize()
            
            self.control_panel.add_log("✅ 模块初始化完成")
            
        except Exception as e:
            logger.error(f"模块初始化失败: {e}")
            self.control_panel.add_log(f"❌ 初始化错误: {e}")
    
    def _on_start(self):
        """启动系统"""
        try:
            # 打开摄像头
            if self._camera and self._camera.open():
                self._camera.start()
                self.control_panel.add_log("📷 摄像头已启动")
            else:
                self.control_panel.add_log("❌ 摄像头打开失败")
                return
            
            # 加载检测模型
            if self._detector and not self._detector.is_loaded:
                if self._detector.load():
                    self.control_panel.add_log("🎯 YOLO 模型已加载")
                else:
                    self.control_panel.add_log("⚠️ YOLO 模型加载失败")
            
            # 初始化导航建议器
            try:
                self._advisor = NavigationAdvisor()
                self.control_panel.add_log("🧠 LLM 引擎已初始化")
            except Exception as e:
                self.control_panel.add_log(f"⚠️ LLM 初始化失败: {e}")
            
            # 启动定时器
            self._timer.start(33)  # ~30 FPS
            self._last_time = time.time()
            self._frame_count = 0
            
            # 语音提示
            if self._voice and self.control_panel.voice_enabled:
                self._voice.speak("系统已启动", immediate=True)
            
            self.control_panel.add_log("🚀 系统运行中...")
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
            self.control_panel.add_log(f"❌ 启动错误: {e}")
    
    def _on_stop(self):
        """停止系统"""
        try:
            self._timer.stop()
            
            if self._camera:
                self._camera.close()
            
            self.video_widget.clear()
            
            if self._voice and self.control_panel.voice_enabled:
                self._voice.speak("系统已停止", immediate=True)
            
            self.control_panel.add_log("⏹️ 系统已停止")
            
        except Exception as e:
            logger.error(f"停止失败: {e}")
    
    def _on_voice_toggled(self, enabled: bool):
        """语音开关切换"""
        status = "开启" if enabled else "关闭"
        self.control_panel.add_log(f"🔊 语音提醒已{status}")
    
    def _on_provider_changed(self, provider: str):
        """LLM 提供商切换"""
        try:
            from src.reasoning.llm_engine import LLMEngine
            self._advisor = NavigationAdvisor(LLMEngine(provider=provider))
            self.control_panel.add_log(f"🔄 已切换到 {provider}")
        except Exception as e:
            self.control_panel.add_log(f"❌ 切换失败: {e}")
    
    def _process_frame(self):
        """处理帧"""
        if self._camera is None:
            return
        
        # 读取帧
        ret, frame = self._camera.read()
        if not ret or frame is None:
            return
        
        detections = []
        
        # 执行检测
        if self._detector and self._detector.is_loaded:
            detections = self._detector.detect(frame)
            
            # 绘制检测结果
            frame = self._detector.draw_detections(frame, detections)
            
            # 更新检测数量
            self.control_panel.update_detection_count(len(detections))
        
        # 更新显示
        self.video_widget.update_frame(frame)
        
        # 更新 FPS
        self._frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_time
        if elapsed >= 1.0:
            fps = self._frame_count / elapsed
            self.control_panel.update_fps(fps)
            self._frame_count = 0
            self._last_time = current_time
        
        # 语音提醒（每秒最多一次）
        if detections and self.control_panel.voice_enabled and self._voice:
            if current_time - self._last_announcement_time >= self._config.navigation.update_interval:
                self._announce_obstacles(detections)
                self._last_announcement_time = current_time
    
    def _announce_obstacles(self, detections: list):
        """播报障碍物"""
        if not self._voice or not detections:
            return
        
        if self._advisor:
            # 使用快速警报
            alert = self._advisor.quick_alert(detections)
            if alert:
                self._voice.speak(alert)
        else:
            # 简单播报
            det = detections[0]
            self._voice.speak(f"注意{det.relative_position}有{det.class_name}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self._on_stop()
        
        if self._voice:
            self._voice.shutdown()
        
        event.accept()
