# 客户端-服务端架构部署指南

## 系统架构

```
📱 手机浏览器 (Web PWA)             🖥️ 电脑端 (Python Server)
┌────────────────────┐            ┌────────────────────┐
│ 摄像头采集          │            │ WebSocket Server   │
│ ↓                  │  ──────►   │ ↓                  │
│ JPEG 压缩          │   wss://   │ YOLO Detection     │
│ ↓                  │            │ ↓                  │
│ WebSocket 发送     │            │ 生成导航建议        │
│                    │  ◄──────   │ ↓                  │
│ TTS 语音播报       │   JSON     │ 返回检测结果        │
└────────────────────┘            └────────────────────┘
```

---

## 快速开始

### 1. 启动服务端（电脑）

```bash
conda activate vgllm
cd D:\VisionGuide_LLM_System
python server/main.py
```

服务端在 `wss://0.0.0.0:8765` 监听（SSL 已启用）。

### 2. 启动 HTTPS 静态服务（电脑，另开终端）

```bash
python mobile/start_https_server.py
```

脚本自动生成自签名证书，打印可访问地址：

```
HTTPS 服务器已启动
  局域网访问:  https://192.168.1.5:8443
  Tailscale:   https://100.111.x.x:8443
```

### 3. 手机浏览器访问

1. 打开上面输出的 HTTPS 地址
2. 首次访问提示证书不受信任 → 点「高级」→「继续前往」
3. 填写 WebSocket 地址（格式 `wss://<同一IP>:8765`）
4. 点「连接服务端」→「开启摄像头」

### 4. 测试通信

```bash
python mobile/test_client.py wss://127.0.0.1:8765
```

---

## 跨网络访问（Tailscale）

不同 WiFi 或 4G 场景下使用 Tailscale 穿透，详见 [tailscale_setup.md](./tailscale_setup.md)。

连接后将 IP 替换为 Tailscale IP（100.x.x.x），其余步骤不变。

---

## 配置说明

### 服务端配置（`server/config.yaml`）

```yaml
server:
  host: "0.0.0.0"
  port: 8765

detection:
  model: "yolo26n.pt"
  confidence: 0.5

llm:
  provider: "openai"
  model: "gpt-4o-mini"
  use_llm: true
  min_interval: 2.0

ssl:
  certfile: "mobile/_dev_cert.pem"
  keyfile:  "mobile/_dev_key.pem"
```

API Key 配置：复制 `.env.example` 为 `.env`，填入 `OPENAI_API_KEY`。

---

## 故障排除

**连接失败**
1. 检查服务端是否启动（终端有无报错）
2. 地址用 `wss://` 而非 `ws://`
3. 防火墙放行 8765 端口

**摄像头不可用**
→ 页面必须通过 HTTPS 访问，HTTP 下 `navigator.mediaDevices` 不可用。

**视频卡顿**
→ 在 Web 客户端降低 FPS 或 JPEG 质量；检查网络延迟。
