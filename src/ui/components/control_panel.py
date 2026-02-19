"""
控制面板组件
提供系统控制按钮和状态显示
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, 
    QVBoxLayout, QWidget, QComboBox, QSlider,
    QGroupBox, QTextEdit
)

from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger()


class ControlPanel(QWidget):
    """控制面板组件"""
    
    # 信号
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    voice_toggled = pyqtSignal(bool)
    provider_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
        self._is_running = False
        self._voice_enabled = True
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("🎯 VisionGuide 控制中心")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #e94560;
                padding: 10px;
            }
        """)
        layout.addWidget(title)
        
        # 控制按钮组
        control_group = QGroupBox("系统控制")
        control_group.setStyleSheet(self._get_group_style())
        control_layout = QHBoxLayout(control_group)
        
        self.start_btn = QPushButton("▶ 启动")
        self.start_btn.setStyleSheet(self._get_button_style("#4ecca3"))
        self.start_btn.clicked.connect(self._on_start_clicked)
        
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setStyleSheet(self._get_button_style("#e94560"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        layout.addWidget(control_group)
        
        # LLM 配置组
        llm_group = QGroupBox("LLM 配置")
        llm_group.setStyleSheet(self._get_group_style())
        llm_layout = QVBoxLayout(llm_group)
        
        provider_label = QLabel("提供商:")
        provider_label.setStyleSheet("color: #a0a0a0;")
        self.provider_combo = QComboBox()
        providers = ["ollama", "openai", "claude", "gemini"]
        self.provider_combo.addItems(providers)
        self.provider_combo.setStyleSheet(self._get_combo_style())

        # 初始化默认 provider（避免 UI 与 config 不一致）
        try:
            current_provider = get_config().llm.provider
            idx = self.provider_combo.findText(current_provider)
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
        except Exception:
            pass

        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        
        llm_layout.addWidget(provider_label)
        llm_layout.addWidget(self.provider_combo)
        layout.addWidget(llm_group)
        
        # 语音控制组
        voice_group = QGroupBox("语音设置")
        voice_group.setStyleSheet(self._get_group_style())
        voice_layout = QVBoxLayout(voice_group)
        
        self.voice_btn = QPushButton("🔊 语音提醒: 开启")
        self.voice_btn.setStyleSheet(self._get_button_style("#16213e", "#4ecca3"))
        self.voice_btn.clicked.connect(self._on_voice_toggled)
        
        voice_layout.addWidget(self.voice_btn)
        layout.addWidget(voice_group)
        
        # 状态显示
        status_group = QGroupBox("系统状态")
        status_group.setStyleSheet(self._get_group_style())
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("color: #4ecca3; font-size: 14px;")
        
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("color: #a0a0a0;")
        
        self.detection_label = QLabel("检测: 0 个物体")
        self.detection_label.setStyleSheet("color: #a0a0a0;")
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.fps_label)
        status_layout.addWidget(self.detection_label)
        layout.addWidget(status_group)
        
        # 日志显示
        log_group = QGroupBox("系统日志")
        log_group.setStyleSheet(self._get_group_style())
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a2e;
                color: #a0a0a0;
                border: 1px solid #16213e;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)
        
        layout.addStretch()
    
    def _get_group_style(self) -> str:
        return """
            QGroupBox {
                font-weight: bold;
                color: #eeeeee;
                border: 1px solid #16213e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """
    
    def _get_button_style(self, bg_color: str, text_color: str = "#ffffff") -> str:
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background-color: #333333;
                color: #666666;
            }}
        """
    
    def _get_combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #1a1a2e;
                color: #eeeeee;
                border: 1px solid #16213e;
                border-radius: 4px;
                padding: 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a2e;
                color: #eeeeee;
                selection-background-color: #4ecca3;
            }
        """
    
    def _on_start_clicked(self):
        self._is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("状态: 运行中")
        self.status_label.setStyleSheet("color: #4ecca3; font-size: 14px;")
        self.start_clicked.emit()
    
    def _on_stop_clicked(self):
        self._is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("状态: 已停止")
        self.status_label.setStyleSheet("color: #e94560; font-size: 14px;")
        self.stop_clicked.emit()
    
    def _on_voice_toggled(self):
        self._voice_enabled = not self._voice_enabled
        if self._voice_enabled:
            self.voice_btn.setText("🔊 语音提醒: 开启")
        else:
            self.voice_btn.setText("🔇 语音提醒: 关闭")
        self.voice_toggled.emit(self._voice_enabled)
    
    def _on_provider_changed(self, provider: str):
        self.provider_changed.emit(provider)
        self.add_log(f"LLM 提供商切换为: {provider}")
    
    def update_fps(self, fps: float):
        """更新 FPS 显示"""
        self.fps_label.setText(f"FPS: {fps:.1f}")
    
    def update_detection_count(self, count: int):
        """更新检测数量"""
        self.detection_label.setText(f"检测: {count} 个物体")
    
    def add_log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def voice_enabled(self) -> bool:
        return self._voice_enabled
