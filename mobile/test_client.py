"""
测试客户端 - 用于桌面环境测试通信协议
不使用摄像头，发送测试图片
"""

import asyncio
import base64
import json
import time
from pathlib import Path

import websockets


async def test_client(server_url: str = "ws://localhost:8765"):
    """测试客户端"""
    print(f"连接到服务器: {server_url}")
    
    try:
        async with websockets.connect(server_url) as websocket:
            print("已连接!")
            
            # 创建测试图片 (纯色)
            import io
            from PIL import Image
            
            # 创建一个测试图像
            img = Image.new('RGB', (640, 480), color=(100, 150, 200))
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=70)
            jpeg_data = buffer.getvalue()
            
            print(f"测试图像大小: {len(jpeg_data)} bytes")
            
            # 发送测试帧
            for i in range(5):
                message = {
                    "type": "frame",
                    "timestamp": time.time(),
                    "data": base64.b64encode(jpeg_data).decode("utf-8")
                }
                
                await websocket.send(json.dumps(message))
                print(f"发送帧 {i+1}")
                
                # 等待响应
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                
                print(f"收到响应: type={data.get('type')}, "
                      f"objects={data.get('total_count', 0)}, "
                      f"time={data.get('process_time_ms', 0)}ms")
                
                if data.get('tts_text'):
                    print(f"TTS: {data['tts_text']}")
                
                await asyncio.sleep(1)
            
            print("测试完成!")
            
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    import sys
    
    server_url = "ws://localhost:8765"
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    
    asyncio.run(test_client(server_url))
