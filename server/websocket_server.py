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
        use_llm: bool = False
    ):
        self.host = host
        self.port = port
        self.use_llm = use_llm
        
        # 客户端连接
        self._clients: Set[WebSocketServerProtocol] = set()
        
        # YOLO 检测器
        self._detector = YOLODetector(
            model_path=model_path,
            confidence=confidence
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
                from src.reasoning.navigation_advisor import NavigationAdvisor
                self._advisor = NavigationAdvisor()
                logger.info("LLM 导航顾问初始化成功")
            except Exception as e:
                logger.warning(f"LLM 初始化失败: {e}")
        
        # 启动 WebSocket 服务
        logger.info(f"启动 WebSocket 服务: ws://{self.host}:{self.port}")
        
        async with websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024  # 10MB
        ):
            logger.info("服务器已启动，等待客户端连接...")
            await asyncio.Future()  # 永久运行
    
    async def _handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"客户端连接: {client_id}")
        
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
        tts_text = self._generate_tts_text(detections)
        
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
    
    def _generate_tts_text(self, detections: List[Detection]) -> str:
        """生成语音播报文本"""
        if not detections:
            return ""
        
        # 使用 LLM（如果启用）
        if self._advisor:
            alert = self._advisor.quick_alert(detections)
            if alert:
                return alert
        
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


async def main():
    """主函数"""
    setup_logger(level="INFO")
    
    logger.info("=" * 50)
    logger.info("VisionGuide Server 启动")
    logger.info("=" * 50)
    
    server = VisionGuideServer(
        host="0.0.0.0",
        port=8765,
        model_path="yolo26n.pt",
        confidence=0.5,
        use_llm=False  # 禁用 LLM 以提高速度
    )
    
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
