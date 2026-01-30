# 客户端-服务端架构部署指南

## 系统架构

```
📱 手机端 (Kivy App)              🖥️ 电脑端 (Python Server)
┌────────────────────┐            ┌────────────────────┐
│ 摄像头采集          │            │ WebSocket Server   │
│ ↓                  │  ──────►   │ ↓                  │
│ JPEG 压缩          │  Tailscale  │ YOLO Detection     │
│ ↓                  │            │ ↓                  │
│ WebSocket 发送     │            │ 生成导航建议        │
│                    │  ◄──────   │ ↓                  │
│ TTS 语音播报       │   JSON     │ 返回检测结果        │
└────────────────────┘            └────────────────────┘
```

---

## 快速开始

### 1. 启动服务端 (电脑)

```bash
# 激活环境
conda activate vgllm

# 启动服务
cd d:\VisionGuide_LLM_System
python -m server.websocket_server

# 或者
python server/websocket_server.py
```

服务端将在 `ws://0.0.0.0:8765` 监听。

### 2. 获取电脑的 Tailscale IP

```bash
tailscale ip -4
# 例如: 100.98.158.52
```

### 3. 启动客户端 (桌面测试)

```bash
# 桌面模式运行 Kivy App
cd mobile
python main.py
```

输入服务器的 Tailscale IP，点击"连接"。

### 4. 测试通信

```bash
# 发送测试帧到服务端
python mobile/test_client.py ws://100.98.158.52:8765
```

---

## Android APK 打包

### 环境准备 (Linux/WSL)

Buildozer 需要 Linux 环境：

```bash
# 安装依赖
sudo apt install -y python3-pip python3-setuptools git zip unzip openjdk-17-jdk

# 安装 buildozer
pip install buildozer

# 安装 Android SDK 依赖
sudo apt install -y autoconf automake libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev cmake
```

### 打包 APK

```bash
cd mobile

# 首次打包 (会下载 Android SDK/NDK，需要较长时间)
buildozer android debug

# APK 位置
ls bin/visionguide-0.1-debug.apk
```

### 安装到手机

```bash
# 通过 ADB 安装
adb install bin/visionguide-0.1-debug.apk
```

---

## 配置说明

### 服务端配置 (`server/config.yaml`)

```yaml
server:
  host: "0.0.0.0"     # 监听所有接口
  port: 8765          # WebSocket 端口

detection:
  model: "yolo26n.pt" # YOLO 模型
  confidence: 0.5     # 置信度阈值
```

### 客户端配置

在 App 界面输入：
- **服务器 IP**: 电脑的 Tailscale IP (如 `100.98.158.52`)
- **端口**: `8765`

---

## 故障排除

### 连接失败
1. 检查服务端是否启动
2. 检查 Tailscale 是否连接
3. 测试: `ping <服务器IP>`

### 视频卡顿
1. 降低视频质量
2. 检查网络延迟: `tailscale ping <手机IP>`

### TTS 不播报
1. 检查手机音量
2. 确认 plyer 安装正确
