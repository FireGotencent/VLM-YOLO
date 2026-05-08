"""
WebSocket 服务端
接收手机端视频帧，处理后返回检测结果
"""

import asyncio
import base64
import json
import sys
import time
from dataclasses import dataclass, asdict
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Set

import numpy as np
import cv2
import websockets
import yaml
from websockets.server import WebSocketServerProtocol

# 当手机浏览器直接访问 wss 端口时返回此页，引导用户接受证书
_CERT_TRUST_HTML = (
    "<!DOCTYPE html>"
    "<html><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<title>VisionGuide WebSocket</title>"
    "<style>body{font:16px/1.6 sans-serif;max-width:420px;margin:60px auto;padding:0 20px;text-align:center}"
    ".ok{color:#0a0;font-size:2em;margin:16px 0}</style>"
    "</head><body>"
    "<div class=\"ok\">&#10003;</div>"
    "<h2>WebSocket 端口证书已接受</h2>"
    "<p>此页面仅用于让浏览器信任 WebSocket 端口的 SSL 证书。</p>"
    "<p>请<strong>返回主页面</strong>点击「连接服务端」。</p>"
    "</body></html>"
).encode("utf-8")


async def _ws_process_request(connection, request):
    """非 WebSocket 升级请求时返回证书接受引导页（兼容 websockets >= 13 asyncio API）"""
    upgrade = request.headers.get("Upgrade", "")
    if upgrade.lower() != "websocket":
        import logging
        logging.getLogger("websockets").info(
            f"HTTP GET {request.path} — 返回证书接受页（非 WebSocket 请求）"
        )
        try:
            from websockets.http11 import Response
            from websockets.datastructures import Headers
            headers = Headers([
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(_CERT_TRUST_HTML))),
            ])
            return Response(HTTPStatus.OK, "OK", headers, _CERT_TRUST_HTML)
        except Exception:
            # 极老版本降级：返回元组格式
            return (HTTPStatus.OK,
                    [("Content-Type", "text/html; charset=utf-8"),
                     ("Content-Length", str(len(_CERT_TRUST_HTML)))],
                    _CERT_TRUST_HTML)
    return None

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.detection.yolo_detector import YOLODetector, Detection
from src.utils.logger import get_logger, setup_logger
from server.gemini_live_client import GeminiLiveClient

logger = get_logger()


@dataclass
class DetectionResult:
    """检测结果"""
    class_name: str
    class_zh: str
    position: str
    confidence: float
    bbox: List[int]


@dataclass
class ServerResponse:
    """服务端响应"""
    type: str
    timestamp: float
    objects: List[Dict]
    tts_text: str
    total_count: int
    process_time_ms: float


class VisionGuideServer:
    """视觉导航服务器"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        model_path: str = "yolo26n.pt",
        confidence: float = 0.5,
        device: str = "auto",
        alert_front_distance: float = 2.0,
        alert_side_distance: float = 1.0,
        max_clients: int = 5,
        max_frame_size: int = 10 * 1024 * 1024,
        use_llm: bool = False,
        use_vision: bool = False,
        use_live: bool = False,
        live_model: str = "gemini-3.1-flash-live-preview",
        live_frame_interval: float = 1.5,
        llm_provider: str = "ollama",
        llm_model: str = "qwen2.5:7b",
        llm_base_url: Optional[str] = None,
        llm_min_interval: float = 2.0,
        ssl_certfile: Optional[str] = None,
        ssl_keyfile: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.use_llm = use_llm
        self._use_vision = use_vision
        self._alert_front_dist = alert_front_distance
        self._alert_side_dist = alert_side_distance
        self._use_live = use_live
        self._live_model = live_model
        self._live_frame_interval = live_frame_interval
        self._max_clients = max_clients
        self._ws_max_size = max(1024 * 1024, int(max_frame_size * 2))
        self._llm_provider = llm_provider
        self._llm_model = llm_model
        self._llm_base_url = llm_base_url
        self._llm_min_interval = max(0.0, float(llm_min_interval))
        self._last_llm_time = 0.0
        self._ssl_certfile = ssl_certfile
        self._ssl_keyfile = ssl_keyfile
        
        # 客户端连接
        self._clients: Set[WebSocketServerProtocol] = set()
        
        # YOLO 检测器
        self._detector = YOLODetector(
            model_path=model_path,
            confidence=confidence,
            device=device
        )
        
        # 统计
        self._frame_count = 0
        self._start_time = time.time()

        # LLM（后台异步运行，帧处理不阻塞）
        self._advisor = None
        self._llm_cache: str = ""              # 上次 LLM 输出，供当前帧立即返回
        self._llm_task: Optional[asyncio.Task] = None  # 正在运行的后台 Task

        # Gemini Live 会话（每个客户端连接独立创建）
        self._live_client: Optional[GeminiLiveClient] = None
    
    async def start(self):
        """启动服务器"""
        # 加载模型
        logger.info("正在加载 YOLO 模型...")
        if not self._detector.load():
            logger.error("YOLO 模型加载失败")
            return
        logger.info("YOLO 模型加载成功")
        
        # 初始化 LLM (可选)
        if self.use_llm:
            try:
                from src.reasoning.llm_engine import LLMEngine
                from src.reasoning.navigation_advisor import NavigationAdvisor

                llm_kwargs = {}
                if self._llm_provider in ("openai", "ollama") and self._llm_base_url:
                    llm_kwargs["base_url"] = self._llm_base_url

                self._advisor = NavigationAdvisor(
                    LLMEngine(
                        provider=self._llm_provider,
                        model=self._llm_model,
                        **llm_kwargs
                    )
                )
                logger.info(f"LLM 导航顾问初始化成功 (provider={self._llm_provider}, model={self._llm_model})")
            except Exception as e:
                logger.warning(f"LLM 初始化失败: {e}")
        
        # 优先使用 Tailscale 受信任证书（与 HTTPS 服务器保持一致）
        ts_cert = project_root / "mobile" / "_ts_cert.pem"
        ts_key  = project_root / "mobile" / "_ts_key.pem"
        if ts_cert.exists() and ts_key.exists():
            logger.info(f"检测到 Tailscale 证书，自动使用: {ts_cert}")
            self._ssl_certfile = str(ts_cert)
            self._ssl_keyfile  = str(ts_key)

        # 构建 SSL 上下文（可选）
        ssl_context = None
        scheme = "ws"
        if self._ssl_certfile and self._ssl_keyfile:
            import ssl as _ssl
            ssl_context = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
            ssl_context.minimum_version = _ssl.TLSVersion.TLSv1_2
            ssl_context.load_cert_chain(self._ssl_certfile, self._ssl_keyfile)
            scheme = "wss"
            logger.info(f"SSL 证书: {self._ssl_certfile}")

        logger.info(f"启动 WebSocket 服务: {scheme}://{self.host}:{self.port}")

        async with websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            max_size=self._ws_max_size,
            ssl=ssl_context,
            process_request=_ws_process_request,
            ping_interval=None,   # 摄像头帧流即活跃证明，无需 keepalive ping
        ):
            logger.info(f"服务器已启动（{'TLS 加密' if ssl_context else '无加密'}），等待客户端连接...")
            await asyncio.Future()  # 永久运行
    
    async def _handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"客户端连接: {client_id}")

        if self._max_clients > 0 and len(self._clients) >= self._max_clients:
            logger.warning(f"拒绝连接（超过最大客户端数 {self._max_clients}）: {client_id}")
            await websocket.close(code=4000, reason="too many clients")
            return
        
        self._clients.add(websocket)

        # 为此客户端建立 Gemini Live 会话
        if self._use_live and self._live_client is None:
            import os as _os
            api_key = _os.getenv("GOOGLE_API_KEY", "")
            if api_key:
                live = GeminiLiveClient(
                    api_key=api_key,
                    model=self._live_model,
                    frame_interval=self._live_frame_interval,
                )
                ok = await live.connect()
                if ok:
                    def _on_live_text(text: str) -> None:
                        self._llm_cache = text
                        logger.info(f"[Live] {text}")
                    live.set_text_callback(_on_live_text)
                    self._live_client = live
                    logger.info(f"[Live] 已为客户端 {client_id} 创建 Live 会话")
                else:
                    logger.warning("[Live] 连接失败，降级为批量推理")
            else:
                logger.warning("[Live] 未找到 GOOGLE_API_KEY，跳过 Live 模式")

        try:
            async for message in websocket:
                await self._process_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端断开: {client_id}")
        except Exception as e:
            if "resume_reading" not in str(e):
                logger.error(f"处理客户端错误: {e}")
        finally:
            self._clients.discard(websocket)
            if self._live_client is not None:
                await self._live_client.close()
                self._live_client = None
                logger.info(f"[Live] 客户端 {client_id} 断开，Live 会话已关闭")
    
    async def _process_message(
        self,
        websocket: WebSocketServerProtocol,
        message: str
    ):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")
            
            if msg_type == "frame":
                await self._process_frame(websocket, data)
            elif msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
            else:
                logger.warning(f"未知消息类型: {msg_type}")
                
        except json.JSONDecodeError:
            logger.error("无效的 JSON 消息")
        except Exception as e:
            logger.error(f"处理消息错误: {e}")
    
    async def _process_frame(
        self,
        websocket: WebSocketServerProtocol,
        data: dict
    ):
        """处理视频帧"""
        start_time = time.time()
        
        # 解码图像
        try:
            frame_data = base64.b64decode(data["data"])
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
        except Exception as e:
            logger.error(f"解码帧失败: {e}")
            return
        
        # YOLO 检测
        detections = self._detector.detect(frame)
        
        # 构建结果
        objects = []
        for det in detections:
            obj = {
                "class": det.class_name,
                "class_zh": self._detector.get_class_name_zh(det.class_name),
                "position": det.relative_position,
                "confidence": round(det.confidence, 2),
                "bbox": list(det.bbox)
            }
            objects.append(obj)
        
        frame_height, frame_width = frame.shape[:2]

        # 只对报警距离内的目标生成 TTS / 送给 LLM
        alert_dets = self._filter_for_alert(detections, frame_width, frame_height)

        if alert_dets:
            if self._live_client and self._live_client.connected:
                yolo_ctx = self._format_yolo_context(alert_dets, frame_width, frame_height)
                await self._live_client.send_frame(frame, yolo_ctx)
            elif self._advisor:
                self._maybe_start_llm_task(alert_dets, frame_width, frame_height, frame)
            tts_text = self._llm_cache if self._llm_cache else self._quick_tts(alert_dets)
        else:
            # 无相关目标：清空缓存，不播报
            self._llm_cache = ""
            tts_text = ""
        
        # 计算处理时间
        process_time = (time.time() - start_time) * 1000
        
        # 构建响应
        response = ServerResponse(
            type="detection_result",
            timestamp=time.time(),
            objects=objects,
            tts_text=tts_text,
            total_count=len(objects),
            process_time_ms=round(process_time, 1)
        )
        
        # 发送响应
        await websocket.send(json.dumps(asdict(response)))
        
        # 统计
        self._frame_count += 1
        if self._frame_count % 100 == 0:
            elapsed = time.time() - self._start_time
            fps = self._frame_count / elapsed
            logger.info(f"已处理 {self._frame_count} 帧, 平均 {fps:.1f} FPS")
    
    def _estimate_distance(self, detection: Detection, frame_width: int, frame_height: int) -> float:
        """基于目标框面积的粗略距离估计（米）"""
        try:
            frame_area = max(1, int(frame_width) * int(frame_height))
            ratio = detection.area / frame_area
        except Exception:
            return 2.0

        if ratio >= 0.20:
            return 0.8
        if ratio >= 0.10:
            return 1.2
        if ratio >= 0.05:
            return 2.0
        if ratio >= 0.02:
            return 3.0
        return 4.0

    # ------------------------------------------------------------------
    # LLM 后台推理（不阻塞帧处理循环）
    # ------------------------------------------------------------------

    def _maybe_start_llm_task(
        self,
        detections: List[Detection],
        frame_width: int,
        frame_height: int,
        frame,
    ) -> None:
        """若满足间隔条件且无正在运行的 Task，则启动后台 LLM 推理"""
        if not self._advisor or not detections:
            return
        now = time.time()
        if now - self._last_llm_time < self._llm_min_interval:
            return
        if self._llm_task and not self._llm_task.done():
            return
        self._last_llm_time = now
        self._llm_task = asyncio.create_task(
            self._run_llm_and_cache(detections, frame_width, frame_height, frame)
        )

    async def _run_llm_and_cache(
        self,
        detections: List[Detection],
        frame_width: int,
        frame_height: int,
        frame,
    ) -> None:
        """在后台调用 LLM，将结果写入缓存"""
        enriched = [
            {
                "name": self._detector.get_class_name_zh(d.class_name),
                "position": d.relative_position,
                "confidence": round(d.confidence, 2),
                "distance": self._estimate_distance(d, frame_width, frame_height),
            }
            for d in detections
        ]
        try:
            if self._use_vision and frame is not None:
                import tempfile, os as _os
                fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
                _os.close(fd)
                try:
                    cv2.imwrite(tmp_path, frame)
                    result = await asyncio.to_thread(
                        self._advisor.analyze_scene_with_image,
                        enriched, [tmp_path]
                    )
                finally:
                    try:
                        _os.unlink(tmp_path)
                    except Exception:
                        pass
            else:
                result = await asyncio.to_thread(
                    self._advisor.analyze_scene_enriched, enriched
                )
            if result:
                self._llm_cache = result
                logger.info(f"[LLM] {result}")
        except Exception as e:
            logger.warning(f"LLM 后台推理失败: {e}")

    def _filter_for_alert(
        self,
        detections: List[Detection],
        frame_width: int,
        frame_height: int,
    ) -> List[Detection]:
        """
        只保留在报警距离内的检测目标：
          正前方 ≤ alert_front_distance
          左/右侧 ≤ alert_side_distance
        """
        result = []
        for det in detections:
            dist = self._estimate_distance(det, frame_width, frame_height)
            pos = det.relative_position
            if "前" in pos and dist <= self._alert_front_dist:
                result.append(det)
            elif ("左" in pos or "右" in pos) and dist <= self._alert_side_dist:
                result.append(det)
        return result

    def _format_yolo_context(
        self, detections: List[Detection], frame_width: int, frame_height: int
    ) -> str:
        """将 YOLO 检测结果格式化为 Live API 文字上下文"""
        if not detections:
            return "YOLO: 未检测到障碍物"
        parts = [
            f"{self._detector.get_class_name_zh(d.class_name)}"
            f"({d.relative_position},{self._estimate_distance(d, frame_width, frame_height):.1f}m)"
            for d in detections
        ]
        return "YOLO: " + " ".join(parts)

    def _quick_tts(self, detections: List[Detection]) -> str:
        """LLM 未就绪时的即时规则播报"""
        if not detections:
            return ""
        if len(detections) == 1:
            d = detections[0]
            return f"注意{d.relative_position}有{self._detector.get_class_name_zh(d.class_name)}"
        positions = set(d.relative_position for d in detections)
        if len(positions) == 1:
            return f"注意{list(positions)[0]}有{len(detections)}个物体"
        return f"周围检测到{len(detections)}个物体，请注意避让"
    
    @property
    def client_count(self) -> int:
        """当前连接的客户端数"""
        return len(self._clients)


def load_server_config(config_path: Optional[str] = None) -> dict:
    """
    加载服务端配置（server/config.yaml）

    Args:
        config_path: 可选的配置文件路径

    Returns:
        dict: 配置字典
    """
    path = Path(config_path) if config_path else (Path(__file__).parent / "config.yaml")
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"加载服务端配置失败: {e}")
        return {}


async def main():
    """主函数"""
    config = load_server_config()
    setup_logger(level=config.get("logging", {}).get("level", "INFO"))
    
    logger.info("=" * 50)
    logger.info("VisionGuide Server 启动")
    logger.info("=" * 50)
    
    server_cfg = config.get("server", {})
    processing_cfg = config.get("processing", {})
    detection_cfg = config.get("detection", {})
    llm_cfg = config.get("llm", {})
    ssl_cfg = config.get("ssl", {})

    # 解析证书路径（相对路径基于项目根目录）
    project_root = Path(__file__).parent.parent
    def resolve(p: Optional[str]) -> Optional[str]:
        if not p:
            return None
        path = Path(p)
        return str(path if path.is_absolute() else project_root / path)

    server = VisionGuideServer(
        host=server_cfg.get("host", "0.0.0.0"),
        port=int(server_cfg.get("port", 8765)),
        max_clients=int(server_cfg.get("max_clients", 5)),
        max_frame_size=int(processing_cfg.get("max_frame_size", 10 * 1024 * 1024)),
        model_path=detection_cfg.get("model", "yolo26n.pt"),
        confidence=float(detection_cfg.get("confidence", 0.5)),
        device=str(detection_cfg.get("device", "auto")),
        alert_front_distance=float(detection_cfg.get("alert_front_distance", 2.0)),
        alert_side_distance=float(detection_cfg.get("alert_side_distance", 1.0)),
        use_llm=bool(llm_cfg.get("use_llm", False)),
        use_vision=bool(llm_cfg.get("use_vision", False)),
        use_live=bool(llm_cfg.get("use_live", False)),
        live_model=str(llm_cfg.get("live_model", "gemini-3.1-flash-live-preview")),
        live_frame_interval=float(llm_cfg.get("live_frame_interval", 1.5)),
        llm_provider=str(llm_cfg.get("provider", "ollama")),
        llm_model=str(llm_cfg.get("model", "qwen2.5:7b")),
        llm_base_url=llm_cfg.get("base_url"),
        llm_min_interval=float(llm_cfg.get("min_interval", 2.0)),
        ssl_certfile=resolve(ssl_cfg.get("certfile")),
        ssl_keyfile=resolve(ssl_cfg.get("keyfile")),
    )
    
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
