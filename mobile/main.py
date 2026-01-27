"""
VisionGuide Mobile - Kivy App 主程序
盲人导航系统手机客户端
"""

import io
import sys
import time
from pathlib import Path
from typing import Optional

# 添加当前目录和父目录到路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

# Kivy 配置（必须在导入其他 Kivy 模块前设置）
from kivy.config import Config
Config.set('graphics', 'width', '480')
Config.set('graphics', 'height', '800')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window

# 注册中文字体
from kivy.core.text import LabelBase
import platform

# 获取当前脚本所在目录（用于查找内置字体）
APP_DIR = Path(__file__).parent

# 根据系统选择中文字体（优先使用内置字体）
# 内置字体路径（适用于所有平台，打包后可用）
bundled_font_paths = [
    str(APP_DIR / 'simhei.ttf'),          # 项目内置黑体
]

if platform.system() == 'Windows':
    # Windows 系统字体
    system_font_paths = [
        'C:/Windows/Fonts/msyh.ttc',      # 微软雅黑
        'C:/Windows/Fonts/simhei.ttf',    # 黑体
        'C:/Windows/Fonts/simsun.ttc',    # 宋体
    ]
elif platform.system() == 'Linux':
    # Linux/Android 系统字体
    system_font_paths = [
        '/system/fonts/NotoSansCJK-Regular.ttc',  # Android
        '/system/fonts/NotoSansSC-Regular.otf',   # Android 新版
        '/system/fonts/DroidSansFallback.ttf',    # Android 备用
        '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
    ]
else:
    system_font_paths = []

# 合并字体路径：内置字体优先于系统字体
font_paths = bundled_font_paths + system_font_paths

# 尝试注册中文字体
chinese_font_registered = False
for font_path in font_paths:
    if Path(font_path).exists():
        try:
            LabelBase.register(name='ChineseFont', fn_regular=font_path)
            chinese_font_registered = True
            print(f"已注册中文字体: {font_path}")
            break
        except Exception as e:
            print(f"注册字体失败: {e}")

# 如果没有找到中文字体，打印警告
if not chinese_font_registered:
    print("警告: 未找到中文字体，中文可能无法正确显示")

# 检测 Android 平台
try:
    from android.permissions import request_permissions, Permission, check_permission
    from android import mActivity
    IS_ANDROID = True
    print("检测到 Android 平台")
except ImportError:
    IS_ANDROID = False
    print("非 Android 平台")

# Android 权限请求函数
def request_android_permissions():
    """请求 Android 运行时权限"""
    if IS_ANDROID:
        request_permissions([
            Permission.CAMERA,
            Permission.INTERNET,
            Permission.RECORD_AUDIO,
        ])

# 摄像头支持
HAS_CAMERA = False
try:
    from kivy.uix.camera import Camera
    HAS_CAMERA = True
except Exception as e:
    print(f"Kivy Camera 不可用: {e}")

from PIL import Image as PILImage

# 使用相对导入
from websocket_client import WebSocketClient
from tts_client import TTSClient

# 默认字体名称
DEFAULT_FONT = 'ChineseFont' if chinese_font_registered else None


class VisionGuideApp(App):
    """VisionGuide 手机客户端"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 默认服务器地址
        self.server_ip = "100.98.158.25"
        self.server_port = 8765
        
        # 组件
        self._ws_client: Optional[WebSocketClient] = None
        self._tts: Optional[TTSClient] = None
        self._camera = None
        
        # 状态
        self._connected = False
        self._last_tts_time = 0
        self._tts_interval = 2.0  # 最小播报间隔
        
    def build(self):
        """构建 UI"""
        # 请求 Android 权限
        if IS_ANDROID:
            request_android_permissions()
        
        # 主布局
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 标题
        title = Label(
            text='VisionGuide',
            font_size='28sp',
            size_hint=(1, 0.08),
            bold=True,
            font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
        )
        layout.add_widget(title)
        
        # 服务器配置
        config_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.08), spacing=5)
        
        self.ip_input = TextInput(
            text=self.server_ip,
            hint_text='Server IP',
            multiline=False,
            size_hint=(0.6, 1),
            font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
        )
        config_layout.add_widget(self.ip_input)
        
        self.port_input = TextInput(
            text=str(self.server_port),
            hint_text='Port',
            multiline=False,
            size_hint=(0.2, 1),
            input_filter='int',
            font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
        )
        config_layout.add_widget(self.port_input)
        
        layout.add_widget(config_layout)
        
        # 摄像头预览区域
        self._camera = None
        self._camera_available = False
        
        if HAS_CAMERA:
            try:
                self._camera = Camera(
                    resolution=(640, 480),
                    play=False,
                    size_hint=(1, 0.5)
                )
                layout.add_widget(self._camera)
                self._camera_available = True
            except Exception as e:
                print(f"摄像头初始化失败: {e}")
                self._camera = None
        
        if not self._camera_available:
            # 无摄像头时显示占位
            self._camera_placeholder = Label(
                text='Camera Not Available\n(Desktop Test Mode)',
                size_hint=(1, 0.5),
                halign='center',
                font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
            )
            layout.add_widget(self._camera_placeholder)
        
        # 状态显示
        self.status_label = Label(
            text='Status: Disconnected',
            font_size='18sp',
            size_hint=(1, 0.08),
            font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
        )
        layout.add_widget(self.status_label)
        
        # 检测结果
        self.result_label = Label(
            text='Detection results will appear here',
            font_size='16sp',
            size_hint=(1, 0.12),
            text_size=(Window.width - 20, None),
            halign='center',
            font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
        )
        layout.add_widget(self.result_label)
        
        # 控制按钮
        btn_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.1), spacing=10)
        
        self.connect_btn = Button(
            text='Connect',
            font_size='18sp',
            on_press=self._on_connect,
            font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
        )
        btn_layout.add_widget(self.connect_btn)
        
        self.disconnect_btn = Button(
            text='Disconnect',
            font_size='18sp',
            on_press=self._on_disconnect,
            disabled=True,
            font_name=DEFAULT_FONT if DEFAULT_FONT else 'Roboto'
        )
        btn_layout.add_widget(self.disconnect_btn)
        
        layout.add_widget(btn_layout)
        
        # 初始化 TTS
        self._tts = TTSClient()
        self._tts.start()
        
        return layout
    
    def _on_connect(self, instance):
        """连接按钮点击"""
        self.server_ip = self.ip_input.text
        self.server_port = int(self.port_input.text)
        
        server_url = f"ws://{self.server_ip}:{self.server_port}"
        
        self._ws_client = WebSocketClient(
            server_url=server_url,
            on_result=self._on_detection_result,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected
        )
        
        self._ws_client.connect()
        self.status_label.text = '状态: 连接中...'
        self.connect_btn.disabled = True
    
    def _on_disconnect(self, instance):
        """断开按钮点击"""
        if self._ws_client:
            self._ws_client.disconnect()
        
        self._stop_camera()
        self._connected = False
        
        self.status_label.text = '状态: 已断开'
        self.connect_btn.disabled = False
        self.disconnect_btn.disabled = True
    
    def _on_connected(self):
        """连接成功回调"""
        def update(dt):
            self._connected = True
            self.status_label.text = '状态: 已连接 ✅'
            self.connect_btn.disabled = True
            self.disconnect_btn.disabled = False
            
            self._start_camera()
            self._tts.speak('已连接服务器')
        
        Clock.schedule_once(update, 0)
    
    def _on_disconnected(self):
        """断开连接回调"""
        def update(dt):
            self._connected = False
            self.status_label.text = '状态: 连接断开 ❌'
            self.connect_btn.disabled = False
            self.disconnect_btn.disabled = True
            
            self._stop_camera()
        
        Clock.schedule_once(update, 0)
    
    def _on_detection_result(self, data: dict):
        """收到检测结果回调"""
        def update(dt):
            # 更新显示
            objects = data.get('objects', [])
            total_count = data.get('total_count', 0)
            tts_text = data.get('tts_text', '')
            process_time = data.get('process_time_ms', 0)
            
            if total_count > 0:
                # 显示检测到的物体
                display_text = f"检测到 {total_count} 个物体:\n"
                for obj in objects[:3]:  # 最多显示3个
                    display_text += f"• {obj['class_zh']} ({obj['position']})\n"
                self.result_label.text = display_text
                
                # 语音播报（控制频率）
                current_time = time.time()
                if tts_text and (current_time - self._last_tts_time > self._tts_interval):
                    self._tts.speak(tts_text)
                    self._last_tts_time = current_time
            else:
                self.result_label.text = '前方畅通'
        
        Clock.schedule_once(update, 0)
    
    def _start_camera(self):
        """启动摄像头"""
        if self._camera_available and self._camera:
            try:
                self._camera.play = True
                # 定时发送帧
                Clock.schedule_interval(self._send_frame, 0.1)  # 10 FPS
            except Exception as e:
                print(f"启动摄像头失败: {e}")
    
    def _stop_camera(self):
        """停止摄像头"""
        if self._camera_available and self._camera:
            try:
                self._camera.play = False
            except:
                pass
        Clock.unschedule(self._send_frame)
    
    def _send_frame(self, dt):
        """发送摄像头帧"""
        if not self._connected or not self._ws_client:
            return
        
        if HAS_CAMERA and self._camera and self._camera.texture:
            # 从 Kivy 纹理获取图像数据
            texture = self._camera.texture
            pixels = texture.pixels
            
            # 转换为 PIL Image
            size = (texture.width, texture.height)
            pil_image = PILImage.frombytes('RGBA', size, pixels)
            pil_image = pil_image.convert('RGB')
            
            # 压缩为 JPEG
            buffer = io.BytesIO()
            pil_image.save(buffer, format='JPEG', quality=70)
            jpeg_data = buffer.getvalue()
            
            # 发送
            self._ws_client.send_frame(jpeg_data)
    
    def on_stop(self):
        """应用停止"""
        if self._ws_client:
            self._ws_client.disconnect()
        if self._tts:
            self._tts.stop()


def main():
    """主函数"""
    VisionGuideApp().run()


if __name__ == '__main__':
    main()
