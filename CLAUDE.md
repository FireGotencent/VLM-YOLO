# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VisionGuide LLM System — 基于多模态AI的视障导航辅助系统。通过摄像头采集画面，YOLOv8检测物体，LLM生成导航建议，语音输出给用户。支持桌面端(PyQt6)、移动端(Kivy)、Web端(PWA)三种客户端。

## Commands

```bash
# 环境激活
conda activate vgllm

# 安装依赖
pip install -r requirements.txt

# 运行桌面应用
python main.py

# 运行WebSocket服务器（供移动端/Web端连接）
python server/main.py

# 运行Web客户端开发服务器
python -m http.server 8081 --directory mobile

# 运行Kivy移动端
cd mobile && python main.py

# 运行测试
pytest tests/
```

## Architecture

五层架构，数据自底向上流动：

```
采集层 (src/capture/)        — OpenCV摄像头/网络摄像头采集帧
  ↓
感知层 (src/detection/)      — YOLOv8物体检测 + 距离估计
  ↓
融合层 (src/fusion/)         — 场景编码(文本描述) + 空间映射(九宫格定位)
  ↓
决策层 (src/reasoning/)      — LLM推理引擎 + 导航建议生成
  ↓
交互层 (src/interaction/, src/ui/)  — 语音I/O + PyQt6界面
```

## Key Modules

- **`src/reasoning/api_provider.py`** — LLM多供应商抽象基类，实现了Ollama/OpenAI/Claude/Gemini四个Provider
- **`src/reasoning/llm_engine.py`** — 统一LLM调用接口，维护对话历史
- **`src/detection/yolo_detector.py`** — YOLOv8检测封装，返回Detection对象(bbox, class, confidence, position)
- **`src/fusion/scene_encoder.py`** — 将检测结果转为结构化场景描述，分配危险等级
- **`src/fusion/spatial_mapper.py`** — 像素坐标映射到九宫格位置描述（左/中/右，上/中/下）
- **`src/utils/config.py`** — Pydantic配置模型
- **`server/websocket_server.py`** — asyncio WebSocket服务器，处理远程视频帧

## Deployment Modes

1. **桌面模式** — `main.py` → PyQt6 GUI，本地摄像头+YOLO+LLM全在本地运行
2. **服务器模式** — `server/main.py` → WebSocket服务器，接收远程客户端视频帧并返回检测/导航结果
3. **Web客户端** — `mobile/web_client.html` → PWA应用，通过WebSocket连接服务器

## Configuration

- **桌面配置**: `config.yaml` — 摄像头、YOLO模型、LLM供应商、语音、导航参数
- **服务器配置**: `server/config.yaml` — WebSocket端口(默认8765)、处理FPS、JPEG质量
- **API密钥**: `.env` (从 `.env.example` 复制) — OpenAI/Claude/Gemini API keys
- LLM供应商切换只需修改 `config.yaml` 中的 `provider` 字段，无需改代码

## 待完成工作（服务端 + Web端）

### 服务端 (server/)

#### 高优先级
- [ ] **帧率限制未生效** — `config.yaml` 中 `target_fps` 已配置但代码未实现，客户端可无限制发送帧
- [ ] **视觉多模态未启用** — LLM Provider 已实现 `chat_with_vision()`，但服务端未调用，图像数据未传给 LLM
- [ ] **NavigationAdvisor 能力未充分利用** — `suggest_path()` / `generate_warning()` 等方法未在服务端调用，仅用于生成简单 TTS 文本
- [ ] **深度估计仅为启发式** — 基于检测框面积的粗略距离估算，无真正深度模型集成

#### 中优先级
- [ ] **无认证机制** — WebSocket 服务器对所有连接开放，无 token/密钥验证
- [ ] **无客户端限流** — 单个客户端可大量发送帧导致服务器过载
- [ ] **无跨帧物体追踪** — 每帧独立检测，无 object ID 跨帧关联
- [ ] **无时空上下文积累** — 每次 LLM 调用独立，未传入空间/时间上下文
- [ ] **LLM 调用无重试/熔断** — 失败后直接降级，无指数退避策略
- [ ] **spatial_mapper 未在服务端集成** — 融合层的九宫格映射模块已导入但未使用

#### 低优先级
- [ ] **无健康检查端点** — 缺少 HTTP health check / status 接口
- [ ] **无性能监控** — 缺少推理耗时、内存使用、LLM 延迟等指标上报
- [ ] **`jpeg_quality` 配置未使用** — 服务端接收预编码帧，此配置项无效

### Web 客户端 (mobile/web_client.html)

#### 高优先级
- [ ] **设置不持久化** — 服务器地址、FPS、JPEG 质量等设置刷新后丢失，需加 localStorage
- [ ] **无可视化检测框** — 仅文字列出检测结果，未在视频画面上绘制 bounding box

#### 中优先级
- [ ] **无网络质量指示** — 缺少延迟图表、丢帧统计、带宽用量显示
- [ ] **无截图/录制功能** — 无法保存帧画面或录制会话
- [ ] **无障碍支持不足** — ARIA 标签不完整，缺少屏幕阅读器优化（对视障用户尤为重要）

#### 低优先级
- [ ] **无浏览器兼容提示** — 不支持的浏览器无降级提示
- [ ] **无深色/浅色主题切换** — 当前仅深色主题

### Kivy 移动端 (mobile/main.py)

#### 中优先级
- [ ] **桌面端无摄像头** — `HAS_CAMERA=False` 导致桌面测试无法发送真实帧
- [ ] **设置不持久化** — 服务器 IP、TTS 偏好等重启后丢失
- [ ] **帧参数不可调** — JPEG 质量(70%)硬编码，无 FPS/分辨率调节 UI
- [ ] **无离线模式** — 断网后无降级处理或结果缓存
