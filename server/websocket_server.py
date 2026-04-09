"""
WebSocket 服务端
接收手机端视频帧，处理后返回检测结果
"""

import asyncio
import base64
import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set

import numpy as np
import cv2
import websockets
import yaml
from websockets.server import WebSocketServerProtocol

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.detection.yolo_detector import YOLODetector, Detection
from src.utils.logger import get_logger, setup_logger

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
        max_clients: int = 5,
        max_frame_size: int = 10 * 1024 * 1024,
        use_llm: bool = False,
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
        
        # LLM (可选)
        self._advisor = None
    
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
        
        # 构建 SSL 上下文（可选）
        ssl_context = None
        scheme = "ws"
        if self._ssl_certfile and self._ssl_keyfile:
            import ssl as _ssl
            ssl_context = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
            ssl_context.minimum_version = _ssl.TLSVersion.TLSv1_2
            ssl_context.load_cert_chain(self._ssl_certfile, self._ssl_keyfile)
            scheme = "wss"

        logger.info(f"启动 WebSocket 服务: {scheme}://{self.host}:{self.port}")

        async with websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            max_size=self._ws_max_size,
            ssl=ssl_context,
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
        
        try:
            async for message in websocket:
                await self._process_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端断开: {client_id}")
        except Exception as e:
            logger.error(f"处理客户端错误: {e}")
        finally:
            self._clients.discard(websocket)
    
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
        
        # 生成语音文本
        frame_height, frame_width = frame.shape[:2]
        tts_text = await self._generate_tts_text(detections, frame_width, frame_height)
        
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

    async def _generate_tts_text(self, detections: List[Detection], frame_width: int, frame_height: int) -> str:
        """生成语音播报文本"""
        if not detections:
            return ""
        
        # 使用 LLM（如果启用）
        if self._advisor:
            now = time.time()
            if now - self._last_llm_time >= self._llm_min_interval:
                self._last_llm_time = now

                top_det = max(detections, key=lambda x: x.confidence)
                name_zh = self._detector.get_class_name_zh(top_det.class_name)
                distance = self._estimate_distance(top_det, frame_width, frame_height)

                try:
                    return await asyncio.to_thread(
                        self._advisor.generate_warning,
                        top_det,
                        distance=distance,
                        object_name=name_zh
                    )
                except Exception as e:
                    logger.warning(f"LLM 生成播报失败: {e}")
        
        # 简单生成
        if len(detections) == 1:
            det = detections[0]
            name_zh = self._detector.get_class_name_zh(det.class_name)
            return f"注意{det.relative_position}有{name_zh}"
        else:
            # 多个目标
            positions = set(d.relative_position for d in detections)
            if len(positions) == 1:
                pos = list(positions)[0]
                return f"注意{pos}有{len(detections)}个物体"
            else:
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
        use_llm=bool(llm_cfg.get("use_llm", False)),
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
