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
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Line

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


THEME = {
    "bg": (0.06, 0.07, 0.09, 1),
    "card": (0.11, 0.12, 0.16, 1),
    "card_border": (0.20, 0.22, 0.30, 1),
    "text": (0.95, 0.96, 0.98, 1),
    "muted": (0.70, 0.72, 0.80, 1),
    "primary": (0.30, 0.80, 0.70, 1),
    "danger": (0.91, 0.27, 0.38, 1),
    "warning": (0.95, 0.72, 0.25, 1),
}


class Card(BoxLayout):
    """轻量卡片容器（纯代码绘制背景，避免额外资源文件）"""

    def __init__(self, bg_color=None, radius=None, **kwargs):
        super().__init__(**kwargs)
        self._bg_color = bg_color or THEME["card"]
        self._radius = float(radius) if radius is not None else float(dp(16))

        with self.canvas.before:
            self._bg_color_instr = Color(*self._bg_color)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])
            self._border_color_instr = Color(*THEME["card_border"])
            self._border = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self._radius), width=1)

        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class StatusChip(Label):
    """状态胶囊（用于展示连接状态）"""

    def __init__(self, bg_color=None, **kwargs):
        super().__init__(**kwargs)
        self._bg_color = bg_color or THEME["card_border"]

        self.size_hint = (None, None)
        self.font_name = DEFAULT_FONT if DEFAULT_FONT else "Roboto"
        self.font_size = sp(13)
        self.color = THEME["text"]
        self.halign = "center"
        self.valign = "middle"

        with self.canvas.before:
            self._bg_color_instr = Color(*self._bg_color)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(999)])

        self.bind(pos=self._update_canvas, size=self._update_canvas, texture_size=self._update_size)
        self._update_size()

    def set(self, text: str, bg_color):
        self.text = text
        self._bg_color = bg_color
        self._bg_color_instr.rgba = bg_color
        self._update_size()

    def _update_size(self, *args):
        w = self.texture_size[0] + dp(24)
        h = max(dp(30), self.texture_size[1] + dp(10))
        self.size = (w, h)
        self._update_canvas()

    def _update_canvas(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size


def _style_text_input(ti: TextInput) -> None:
    ti.background_normal = ""
    ti.background_active = ""
    ti.background_color = (0.08, 0.09, 0.12, 1)
    ti.foreground_color = THEME["text"]
    ti.cursor_color = THEME["primary"]
    ti.hint_text_color = THEME["muted"]
    ti.padding = [dp(12), dp(10), dp(12), dp(10)]
    ti.font_size = sp(16)
    ti.font_name = DEFAULT_FONT if DEFAULT_FONT else "Roboto"


def _style_button(btn: Button, bg_color, text_color=None) -> None:
    btn.background_normal = ""
    btn.background_down = ""
    btn.background_color = bg_color
    btn.color = text_color or THEME["text"]
    btn.font_size = sp(16)
    btn.font_name = DEFAULT_FONT if DEFAULT_FONT else "Roboto"


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
        self._is_connecting = False
        self._last_tts_time = 0
        self._tts_interval = 2.0  # 最小播报间隔
        self._tts_enabled = True

        # UI 引用
        self.status_chip: Optional[StatusChip] = None
        self.subtitle_label: Optional[Label] = None
        self.stats_label: Optional[Label] = None
        
    def build(self):
        """构建 UI"""
        # 请求 Android 权限
        if IS_ANDROID:
            request_android_permissions()

        Window.clearcolor = THEME["bg"]

        # 主布局
        layout = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        # 顶部栏
        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(56), spacing=dp(10))

        title_box = BoxLayout(orientation="vertical", size_hint=(1, 1), spacing=dp(2))
        title = Label(
            text="VisionGuide",
            font_size=sp(26),
            bold=True,
            color=THEME["text"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        self.subtitle_label = Label(
            text="未连接",
            font_size=sp(13),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        self.subtitle_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        title_box.add_widget(title)
        title_box.add_widget(self.subtitle_label)

        self.status_chip = StatusChip(text="未连接", bg_color=THEME["card_border"])

        header.add_widget(title_box)
        header.add_widget(self.status_chip)
        layout.add_widget(header)

        # 连接卡片
        conn_card = Card(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(178),
            padding=dp(14),
            spacing=dp(10),
        )

        conn_title = Label(
            text="服务器连接",
            size_hint=(1, None),
            height=dp(20),
            font_size=sp(14),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        conn_title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        conn_card.add_widget(conn_title)

        inputs_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(46), spacing=dp(10))

        self.ip_input = TextInput(text=self.server_ip, hint_text="服务器 IP", multiline=False)
        _style_text_input(self.ip_input)

        self.port_input = TextInput(
            text=str(self.server_port),
            hint_text="端口",
            multiline=False,
            input_filter="int",
            size_hint=(None, 1),
            width=dp(110),
        )
        _style_text_input(self.port_input)

        inputs_row.add_widget(self.ip_input)
        inputs_row.add_widget(self.port_input)
        conn_card.add_widget(inputs_row)

        btn_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(46), spacing=dp(10))
        self.connect_btn = Button(text="连接", on_press=self._on_connect)
        _style_button(self.connect_btn, THEME["primary"], text_color=(0, 0, 0, 1))

        self.disconnect_btn = Button(text="断开", on_press=self._on_disconnect, disabled=True)
        _style_button(self.disconnect_btn, THEME["danger"], text_color=THEME["text"])

        btn_row.add_widget(self.connect_btn)
        btn_row.add_widget(self.disconnect_btn)
        conn_card.add_widget(btn_row)

        hint = Label(
            text="示例：100.98.158.25:8765（Tailscale）",
            size_hint=(1, None),
            height=dp(18),
            font_size=sp(12),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        hint.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        conn_card.add_widget(hint)

        layout.add_widget(conn_card)

        # 预览卡片
        preview_card = Card(orientation="vertical", padding=dp(14), spacing=dp(10), size_hint=(1, 0.52))
        preview_title = Label(
            text="摄像头预览",
            size_hint=(1, None),
            height=dp(20),
            font_size=sp(14),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        preview_title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        preview_card.add_widget(preview_title)

        # 摄像头预览区域
        self._camera = None
        self._camera_available = False

        if HAS_CAMERA:
            try:
                self._camera = Camera(resolution=(640, 480), play=False, size_hint=(1, 1))
                preview_card.add_widget(self._camera)
                self._camera_available = True
            except Exception as e:
                print(f"摄像头初始化失败: {e}")
                self._camera = None

        if not self._camera_available:
            self._camera_placeholder = Label(
                text="摄像头不可用\n（桌面测试模式）",
                size_hint=(1, 1),
                halign="center",
                valign="middle",
                color=THEME["muted"],
                font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            )
            self._camera_placeholder.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            preview_card.add_widget(self._camera_placeholder)

        layout.add_widget(preview_card)

        # 结果卡片
        result_card = Card(orientation="vertical", padding=dp(14), spacing=dp(10), size_hint=(1, 0.33))

        result_header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(22))
        result_title = Label(
            text="识别结果",
            font_size=sp(14),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        result_title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        self.stats_label = Label(
            text="-- ms",
            font_size=sp(12),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="right",
            valign="middle",
            size_hint=(None, 1),
            width=dp(90),
        )
        self.stats_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        result_header.add_widget(result_title)
        result_header.add_widget(self.stats_label)
        result_card.add_widget(result_header)

        result_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.result_label = Label(
            text="等待检测结果…",
            markup=True,
            color=THEME["text"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            font_size=sp(15),
            halign="left",
            valign="top",
            size_hint_y=None,
        )
        self.result_label.bind(texture_size=lambda inst, size: setattr(inst, "height", size[1]))
        result_scroll.bind(
            width=lambda inst, w: setattr(self.result_label, "text_size", (max(0, w - dp(10)), None))
        )
        result_scroll.add_widget(self.result_label)
        result_card.add_widget(result_scroll)

        layout.add_widget(result_card)

        # 设置卡片（仅放最关键的语音开关 + 播报间隔）
        settings_card = Card(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(10),
            size_hint=(1, None),
            height=dp(150),
        )
        settings_title = Label(
            text="语音设置",
            size_hint=(1, None),
            height=dp(20),
            font_size=sp(14),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        settings_title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        settings_card.add_widget(settings_title)

        tts_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(40), spacing=dp(10))
        toggle_bg = THEME["primary"] if self._tts_enabled else THEME["card_border"]
        toggle_text_color = (0, 0, 0, 1) if self._tts_enabled else THEME["text"]
        self.tts_toggle = ToggleButton(
            text="语音：开" if self._tts_enabled else "语音：关",
            state="down" if self._tts_enabled else "normal",
        )
        _style_button(self.tts_toggle, toggle_bg, text_color=toggle_text_color)
        self.tts_toggle.bind(on_press=self._on_tts_toggle)

        tts_test_btn = Button(text="测试语音")
        _style_button(tts_test_btn, THEME["primary"], text_color=(0, 0, 0, 1))
        tts_test_btn.bind(on_press=lambda *_: self._tts.speak("语音播报正常") if self._tts else None)

        tts_row.add_widget(self.tts_toggle)
        tts_row.add_widget(tts_test_btn)
        settings_card.add_widget(tts_row)

        interval_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(44), spacing=dp(10))
        interval_label = Label(
            text="播报间隔",
            size_hint=(None, 1),
            width=dp(90),
            font_size=sp(13),
            color=THEME["muted"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="left",
            valign="middle",
        )
        interval_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        self.interval_value_label = Label(
            text=f"{self._tts_interval:.1f}s",
            size_hint=(None, 1),
            width=dp(52),
            font_size=sp(13),
            color=THEME["text"],
            font_name=DEFAULT_FONT if DEFAULT_FONT else "Roboto",
            halign="right",
            valign="middle",
        )
        self.interval_value_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        self.tts_interval_slider = Slider(min=0.5, max=5.0, value=self._tts_interval, step=0.5)
        self.tts_interval_slider.bind(value=self._on_tts_interval_changed)

        interval_row.add_widget(interval_label)
        interval_row.add_widget(self.tts_interval_slider)
        interval_row.add_widget(self.interval_value_label)
        settings_card.add_widget(interval_row)

        layout.add_widget(settings_card)
        
        # 初始化 TTS
        try:
            self._tts = TTSClient()
            self._tts.start()
        except Exception as e:
            print(f"TTS 初始化失败: {e}")
            self._tts = None
        
        self._set_status("disconnected")
        return layout

    def _set_status(self, state: str, detail: str = "") -> None:
        if not self.status_chip or not self.subtitle_label:
            return

        if state == "connected":
            self.status_chip.set("已连接", THEME["primary"])
            self.subtitle_label.text = detail or "已连接"
        elif state == "connecting":
            self.status_chip.set("连接中", THEME["warning"])
            self.subtitle_label.text = detail or "连接中…"
        elif state == "error":
            self.status_chip.set("错误", THEME["danger"])
            self.subtitle_label.text = detail or "连接失败"
        else:
            self.status_chip.set("未连接", THEME["card_border"])
            self.subtitle_label.text = detail or "未连接"

    def _on_tts_toggle(self, instance):
        self._tts_enabled = instance.state == "down"
        instance.text = "语音：开" if self._tts_enabled else "语音：关"
        if self._tts_enabled:
            instance.background_color = THEME["primary"]
            instance.color = (0, 0, 0, 1)
            self._last_tts_time = 0
        else:
            instance.background_color = THEME["card_border"]
            instance.color = THEME["text"]

    def _on_tts_interval_changed(self, instance, value):
        self._tts_interval = float(value)
        if hasattr(self, "interval_value_label") and self.interval_value_label:
            self.interval_value_label.text = f"{self._tts_interval:.1f}s"
    
    def _set_buttons(self, connected: bool, connecting: bool = False) -> None:
        if self.connect_btn:
            self.connect_btn.disabled = connected or connecting
        if self.disconnect_btn:
            self.disconnect_btn.disabled = not (connected or connecting)
     
    def _on_connect(self, instance):
        """连接按钮点击"""
        ip = (self.ip_input.text or "").strip() if self.ip_input else ""
        port_text = (self.port_input.text or "").strip() if self.port_input else ""

        if not ip:
            self._set_status("error", "请输入服务器 IP")
            return

        try:
            port = int(port_text)
            if port < 1 or port > 65535:
                raise ValueError
        except Exception:
            self._set_status("error", "端口无效（1-65535）")
            if self._tts_enabled and self._tts:
                self._tts.speak("端口无效")
            return

        self.server_ip = ip
        self.server_port = port

        server_url = f"ws://{self.server_ip}:{self.server_port}"

        if self._ws_client:
            try:
                self._ws_client.disconnect()
            except Exception:
                pass
            self._ws_client = None

        self._is_connecting = True
        self._set_status("connecting", f"{self.server_ip}:{self.server_port}")
        self._set_buttons(connected=False, connecting=True)

        try:
            self._ws_client = WebSocketClient(
                server_url=server_url,
                on_result=self._on_detection_result,
                on_connected=self._on_connected,
                on_disconnected=self._on_disconnected,
            )
            self._ws_client.connect()
        except Exception as e:
            self._is_connecting = False
            self._set_status("error", f"连接失败：{e}")
            self._set_buttons(connected=False, connecting=False)
            if self._tts_enabled and self._tts:
                self._tts.speak("连接失败")
     
    def _on_disconnect(self, instance):
        """断开按钮点击"""
        if self._ws_client:
            try:
                self._ws_client.disconnect()
            except Exception:
                pass
            self._ws_client = None

        self._is_connecting = False
        self._connected = False
        self._stop_camera()

        self._set_status("disconnected")
        self._set_buttons(connected=False, connecting=False)

        if self._tts_enabled and self._tts:
            self._tts.speak("已断开连接")
     
    def _on_connected(self):
        """连接成功回调"""
        def update(dt):
            self._connected = True
            self._is_connecting = False
            self._set_status("connected", f"{self.server_ip}:{self.server_port}")
            self._set_buttons(connected=True, connecting=False)
            
            self._start_camera()
            if self._tts_enabled and self._tts:
                self._tts.speak("已连接服务器")
         
        Clock.schedule_once(update, 0)
     
    def _on_disconnected(self):
        """断开连接回调"""
        def update(dt):
            was_connected = self._connected
            was_connecting = getattr(self, "_is_connecting", False)

            self._connected = False
            self._is_connecting = False
            self._set_buttons(connected=False, connecting=False)
            
            self._stop_camera()

            if was_connecting and not was_connected:
                self._set_status("error", "连接失败")
                if self._tts_enabled and self._tts:
                    self._tts.speak("连接失败")
            else:
                self._set_status("disconnected")
                if was_connected and self._tts_enabled and self._tts:
                    self._tts.speak("连接已断开")
         
        Clock.schedule_once(update, 0)
     
    def _on_detection_result(self, data: dict):
        """收到检测结果回调"""
        def update(dt):
            # 更新显示
            objects = data.get('objects', [])
            total_count = data.get('total_count', 0)
            tts_text = data.get('tts_text', '')
            process_time = data.get('process_time_ms', 0)

            if self.stats_label:
                try:
                    self.stats_label.text = f"{float(process_time):.0f} ms"
                except Exception:
                    self.stats_label.text = "-- ms"
             
            if total_count > 0:
                # 显示检测到的物体（最多展示 5 项）
                lines = [f"[b]检测到 {total_count} 个物体[/b]"]
                for obj in (objects or [])[:5]:
                    name = obj.get("class_zh") or obj.get("class") or "未知"
                    pos = obj.get("position") or ""
                    conf = obj.get("confidence", None)
                    if isinstance(conf, (int, float)):
                        conf_text = f"  {int(float(conf) * 100)}%"
                    else:
                        conf_text = ""

                    if pos:
                        lines.append(f"• {name}（{pos}）{conf_text}")
                    else:
                        lines.append(f"• {name}{conf_text}")

                if total_count > 5:
                    lines.append(f"\n还有 {total_count - 5} 个未显示…")

                self.result_label.text = "\n".join(lines) if self.result_label else ""
                 
                # 语音播报（控制频率）
                current_time = time.time()
                if (
                    self._tts_enabled
                    and self._tts
                    and tts_text
                    and (current_time - self._last_tts_time > self._tts_interval)
                ):
                    self._tts.speak(tts_text)
                    self._last_tts_time = current_time
            else:
                if self.result_label:
                    self.result_label.text = "[b]前方畅通[/b]\n暂无检测到障碍物"
         
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
