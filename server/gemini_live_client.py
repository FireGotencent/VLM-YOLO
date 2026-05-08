"""
Gemini Live API 客户端
保持与 Gemini 的长连接 WebSocket 会话，实时推送视频帧并接收导航建议。
"""
import asyncio
import base64
import json
import logging
import time
from typing import Callable, Optional

import cv2
import numpy as np
import websockets

logger = logging.getLogger(__name__)

_LIVE_ENDPOINT = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta."
    "GenerativeService.BidiGenerateContent?key={api_key}"
)

_SYSTEM_PROMPT = (
    "你是专业的盲人导航助手「视导」。规则："
    "①每次只输出1~2句话，不超过25个字。"
    "②直接说行动指令，例如「前方有行人，请右转绕行」。"
    "③无障碍时说「前方畅通，可以继续前行」。"
    "④有紧急危险时加「紧急」前缀。"
    "⑤不要重复完全相同的提示。"
)


class GeminiLiveClient:
    """
    与 Gemini Live API 保持持久 WebSocket 会话。
    通过 send_frame() 推送视频帧 + YOLO 上下文，
    通过 set_text_callback() 异步接收导航文本。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.1-flash-live-preview",
        frame_interval: float = 1.5,
    ):
        self.api_key = api_key
        self.model = model
        self.frame_interval = frame_interval  # 发帧最小间隔（秒）

        self._ws = None
        self._connected = False
        self._recv_task: Optional[asyncio.Task] = None
        self._last_sent: float = 0.0
        self._text_buffer: str = ""
        self._on_text: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def set_text_callback(self, cb: Callable[[str], None]) -> None:
        """设置收到导航文本时的回调"""
        self._on_text = cb

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """建立 Live API 连接并等待 setupComplete 确认"""
        url = _LIVE_ENDPOINT.format(api_key=self.api_key)
        try:
            self._ws = await websockets.connect(
                url,
                ping_interval=None,
                open_timeout=15,
                additional_headers={"Content-Type": "application/json"},
            )
            # 发送初始配置
            await self._ws.send(json.dumps({
                "config": {
                    "model": f"models/{self.model}",
                    "responseModalities": ["TEXT"],
                    "systemInstruction": {
                        "parts": [{"text": _SYSTEM_PROMPT}]
                    }
                }
            }))
            # 等待 setupComplete
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=15)
                data = json.loads(raw)
                if "setupComplete" not in data:
                    logger.warning(f"[Live] 首条消息非 setupComplete: {list(data.keys())}")
            except asyncio.TimeoutError:
                logger.warning("[Live] 等待 setupComplete 超时，继续运行")

            self._connected = True
            self._recv_task = asyncio.create_task(self._recv_loop())
            logger.info(f"[Live] 已连接  model={self.model}")
            return True

        except Exception as e:
            logger.error(f"[Live] 连接失败: {e}")
            self._connected = False
            return False

    async def close(self) -> None:
        """关闭连接并取消接收任务"""
        self._connected = False
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        logger.info("[Live] 连接已关闭")

    async def send_frame(self, frame: np.ndarray, yolo_context: str = "") -> None:
        """
        推送一帧图像（受 frame_interval 限速）。
        yolo_context 为 YOLO 检测摘要，附在图像后以辅助理解。
        """
        if not self._connected or self._ws is None:
            return
        now = time.time()
        if now - self._last_sent < self.frame_interval:
            return
        self._last_sent = now

        try:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            b64 = base64.b64encode(buf.tobytes()).decode()

            await self._ws.send(json.dumps({
                "realtimeInput": {
                    "video": {"data": b64, "mimeType": "image/jpeg"}
                }
            }))

            if yolo_context:
                await self._ws.send(json.dumps({
                    "realtimeInput": {"text": yolo_context}
                }))

        except Exception as e:
            logger.warning(f"[Live] 发送帧失败: {e}")
            self._connected = False

    # ------------------------------------------------------------------
    # 接收循环
    # ------------------------------------------------------------------

    async def _recv_loop(self) -> None:
        """持续接收服务器消息，拼接文本片段，turn 结束后触发回调"""
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                self._handle_server_message(data)
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"[Live] 接收端连接关闭: code={e.code}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[Live] 接收循环错误: {e}")
        finally:
            self._connected = False

    def _handle_server_message(self, data: dict) -> None:
        sc = data.get("serverContent", {})

        # 拼接文本片段
        for part in sc.get("modelTurn", {}).get("parts", []):
            text = part.get("text", "").strip()
            if text:
                self._text_buffer += text

        # outputTranscription（TEXT 模式下的文字转写）
        if sc.get("outputTranscription", {}).get("text", "").strip():
            self._text_buffer += sc["outputTranscription"]["text"].strip()

        # turn 结束 → 触发回调，清空缓冲
        if sc.get("turnComplete") or sc.get("generationComplete"):
            result = self._text_buffer.strip()
            self._text_buffer = ""
            if result and self._on_text:
                self._on_text(result)
