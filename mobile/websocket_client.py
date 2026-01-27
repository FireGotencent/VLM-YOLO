"""
WebSocket 客户端
负责与服务端通信
"""

import asyncio
import base64
import json
import threading
import time
from typing import Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol


class WebSocketClient:
    """WebSocket 客户端"""
    
    def __init__(
        self,
        server_url: str,
        on_result: Optional[Callable[[dict], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None
    ):
        """
        初始化客户端
        
        Args:
            server_url: 服务器地址 (如 "ws://100.98.158.25:8765")
            on_result: 收到检测结果的回调
            on_connected: 连接成功回调
            on_disconnected: 断开连接回调
        """
        self.server_url = server_url
        self.on_result = on_result
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        
        self._websocket: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._send_queue: asyncio.Queue = None
        self._connected = False
    
    def connect(self) -> None:
        """启动连接（在后台线程）"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def disconnect(self) -> None:
        """断开连接"""
        self._running = False
        self._connected = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
    
    def send_frame(self, jpeg_data: bytes) -> None:
        """
        发送视频帧
        
        Args:
            jpeg_data: JPEG 编码的图像数据
        """
        if not self._running or not self._connected or self._send_queue is None:
            return
        
        message = {
            "type": "frame",
            "timestamp": time.time(),
            "data": base64.b64encode(jpeg_data).decode("utf-8")
        }
        
        try:
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(
                    lambda: self._send_queue.put_nowait(json.dumps(message))
                )
        except Exception:
            pass
    
    def _run_loop(self) -> None:
        """运行事件循环（后台线程）"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._send_queue = asyncio.Queue()
        
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            print(f"事件循环错误: {e}")
        finally:
            try:
                self._loop.close()
            except:
                pass
    
    async def _connect_loop(self) -> None:
        """连接循环（自动重连）"""
        while self._running:
            try:
                print(f"正在连接: {self.server_url}")
                async with websockets.connect(
                    self.server_url,
                    max_size=10 * 1024 * 1024,
                    ping_interval=20,      # 心跳间隔
                    ping_timeout=10,       # 心跳超时
                    close_timeout=5
                ) as websocket:
                    self._websocket = websocket
                    self._connected = True
                    print(f"已连接到服务器: {self.server_url}")
                    
                    if self.on_connected:
                        self.on_connected()
                    
                    # 使用 wait 而不是 gather，任一任务完成后返回
                    try:
                        send_task = asyncio.create_task(self._send_loop(websocket))
                        receive_task = asyncio.create_task(self._receive_loop(websocket))
                        
                        # 等待任一任务完成（通常是因为出错）
                        done, pending = await asyncio.wait(
                            [send_task, receive_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        # 取消未完成的任务
                        for task in pending:
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                    except Exception as e:
                        print(f"任务错误: {e}")
                    
            except websockets.exceptions.ConnectionClosed as e:
                print(f"连接关闭: {e}")
            except Exception as e:
                print(f"连接错误: {e}")
            
            self._websocket = None
            self._connected = False
            
            if self.on_disconnected:
                self.on_disconnected()
            
            if self._running:
                print("3秒后重连...")
                await asyncio.sleep(3)
    
    async def _send_loop(self, websocket: WebSocketClientProtocol) -> None:
        """发送循环"""
        while self._running and self._connected:
            try:
                message = await asyncio.wait_for(
                    self._send_queue.get(),
                    timeout=5.0
                )
                await websocket.send(message)
            except asyncio.TimeoutError:
                # 超时时发送心跳
                try:
                    await websocket.send(json.dumps({"type": "ping"}))
                except:
                    break
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                print(f"发送错误: {e}")
                break
    
    async def _receive_loop(self, websocket: WebSocketClientProtocol) -> None:
        """接收循环"""
        while self._running and self._connected:
            try:
                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=30.0
                )
                data = json.loads(message)
                
                if data.get("type") == "detection_result":
                    if self.on_result:
                        self.on_result(data)
                elif data.get("type") == "pong":
                    pass  # 心跳响应
                        
            except asyncio.TimeoutError:
                continue  # 超时继续等待
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                print(f"接收错误: {e}")
                break
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected and self._websocket is not None

