# Tailscale + 手机摄像头 配置指南

本文档介绍如何使用 Tailscale 实现跨网络的手机摄像头接入。

## 什么是 Tailscale？

Tailscale 是基于 WireGuard 的零配置 VPN 服务，可以让不同网络下的设备像在同一局域网一样通信。

**优势**：
- ✅ 简单配置，无需公网 IP
- ✅ 端到端加密，安全可靠
- ✅ 跨平台支持（Windows/Mac/Linux/Android/iOS）
- ✅ 免费额度足够个人使用（100 台设备）

## 配置步骤

### 步骤 1：注册 Tailscale 账号

访问 https://tailscale.com/ 注册账号（可使用 Google/Microsoft/GitHub 登录）

### 步骤 2：在电脑上安装 Tailscale

**Windows**:
1. 下载安装包: https://tailscale.com/download/windows
2. 安装后登录你的账号
3. 记下分配的 Tailscale IP（如 `100.x.x.x`）

**命令行查看 IP**:
```bash
tailscale ip -4
```

### 步骤 3：在手机上安装 Tailscale

**Android**:
1. 从 Google Play 安装 "Tailscale"
2. 登录同一个账号
3. 开启 Tailscale 连接

**iOS**:
1. 从 App Store 安装 "Tailscale"
2. 登录同一个账号

### 步骤 4：安装手机摄像头 App

推荐使用 **IP Webcam** (Android):
1. 安装 IP Webcam
2. 打开 App，点击 "Start server"
3. 记下显示的本地端口（默认 8080）

### 步骤 5：获取手机的 Tailscale IP

在手机的 Tailscale App 中查看分配的 IP 地址（如 `100.64.0.2`）

或者在电脑上查看所有设备:
```bash
tailscale status
```

### 步骤 6：配置 VisionGuide

编辑 `config.yaml`:

```yaml
camera:
  # 使用 Tailscale 网络
  type: "ip_webcam"
  
  # 填写手机的 Tailscale IP（不是局域网 IP）
  network_source: "100.64.0.2"   # 替换为你手机的 Tailscale IP
  network_port: 8080
  
  width: 1280
  height: 720
  fps: 30
```

### 步骤 7：测试连接

1. 确保手机和电脑都开启了 Tailscale
2. 在电脑上测试访问:
```bash
# 测试网络连通性
ping 100.64.0.2

# 测试视频流（在浏览器打开）
# http://100.64.0.2:8080/video
```

3. 启动 VisionGuide:
```bash
conda activate vgllm
python main.py
```

## 网络拓扑

```
┌─────────────────┐         ┌─────────────────┐
│   Android 手机   │         │   Windows 电脑   │
│                 │         │                 │
│  ┌───────────┐  │         │  ┌───────────┐  │
│  │ IP Webcam │  │◄───────►│  │VisionGuide│  │
│  │  :8080    │  │ Tailscale│  │  System   │  │
│  └───────────┘  │ 虚拟网络  │  └───────────┘  │
│                 │         │                 │
│ Tailscale:      │         │ Tailscale:      │
│ 100.64.0.2      │         │ 100.64.0.1      │
└─────────────────┘         └─────────────────┘
        │                           │
        │     ┌─────────────┐       │
        └────►│  Tailscale  │◄──────┘
              │   服务器     │
              │ (中继协调)   │
              └─────────────┘
```

## 常见问题

### Q: 延迟高怎么办？

Tailscale 在两台设备都在 NAT 后时会通过中继服务器转发，可能增加延迟。

**解决方案**:
1. 尝试 `tailscale ping <手机IP>` 查看直连状态
2. 如果显示 "via DERP"，说明在用中继
3. 某些情况下等待几分钟会自动建立直连

### Q: IP Webcam 在后台被杀？

Android 系统可能会在后台关闭 IP Webcam。

**解决方案**:
1. 在 IP Webcam 设置中启用 "Prevent sleep"
2. 在手机电池设置中允许 IP Webcam 后台运行
3. 锁定 App 防止被清理

### Q: 如何提高视频质量？

在 IP Webcam 中调整:
- Video preferences → Video resolution
- Video preferences → Quality

建议设置 720p，太高的分辨率会增加延迟。

## 安全提示

1. Tailscale 使用端到端加密，视频流不会被第三方看到
2. 不要将 IP Webcam 的端口暴露到公网
3. 定期检查 Tailscale Admin Console 中的设备列表
