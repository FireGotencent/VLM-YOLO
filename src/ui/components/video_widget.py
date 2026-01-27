"""
视频显示组件
用于显示摄像头画面和检测结果
"""

from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger()


class VideoWidget(QWidget):
    """视频显示组件"""
    
    # 信号：帧更新
    frame_updated = pyqtSignal(np.ndarray)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
        self._last_frame: Optional[np.ndarray] = None
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 视频显示标签
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 2px solid #16213e;
                border-radius: 8px;
            }
        """)
        self.video_label.setText("等待视频信号...")
        
        layout.addWidget(self.video_label)
    
    def update_frame(self, frame: np.ndarray) -> None:
        """
        更新显示的帧
        
        Args:
            frame: BGR 格式的图像
        """
        try:
            self._last_frame = frame.copy()
            
            # 转换颜色空间
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 调整大小以适应显示区域
            h, w = rgb_frame.shape[:2]
            label_size = self.video_label.size()
            scale = min(label_size.width() / w, label_size.height() / h)
            
            if scale < 1:
                new_w = int(w * scale)
                new_h = int(h * scale)
                rgb_frame = cv2.resize(rgb_frame, (new_w, new_h))
            
            # 转换为 QImage
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            q_image = QImage(
                rgb_frame.data,
                w, h,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )
            
            # 显示
            pixmap = QPixmap.fromImage(q_image)
            self.video_label.setPixmap(pixmap)
            
            # 发射信号
            self.frame_updated.emit(frame)
            
        except Exception as e:
            logger.error(f"更新帧失败: {e}")
    
    def clear(self) -> None:
        """清空显示"""
        self.video_label.clear()
        self.video_label.setText("等待视频信号...")
        self._last_frame = None
    
    def get_last_frame(self) -> Optional[np.ndarray]:
        """获取最后一帧"""
        return self._last_frame.copy() if self._last_frame is not None else None
