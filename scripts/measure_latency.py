"""
实验二：端到端系统延迟测量
运行: python scripts/measure_latency.py [url] [n_frames]
示例: python scripts/measure_latency.py wss://localhost:8765 100
"""
import asyncio
import base64
import json
import ssl
import statistics
import sys
import time

import cv2
import websockets


async def measure(url: str, n_frames: int = 100):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    latencies = []
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # 没有摄像头时用纯黑帧
        import numpy as np
        use_dummy = True
    else:
        use_dummy = False

    print(f"目标: {url}  帧数: {n_frames}")
    print("开始测量...")

    try:
        async with websockets.connect(url, ssl=ctx, ping_interval=None) as ws:
            for i in range(n_frames):
                if use_dummy:
                    import numpy as np
                    frame = np.zeros((480, 640, 3), dtype="uint8")
                else:
                    ret, frame = cap.read()
                    if not ret:
                        break

                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                payload = json.dumps({
                    "type": "frame",
                    "data": base64.b64encode(buf).decode()
                })

                t0 = time.perf_counter()
                await ws.send(payload)
                await ws.recv()
                latencies.append((time.perf_counter() - t0) * 1000)

                print(f"\r进度 {i+1}/{n_frames}  当前: {latencies[-1]:.1f} ms", end="")
    finally:
        cap.release()

    if not latencies:
        print("\n未收集到数据")
        return

    sorted_lat = sorted(latencies)
    p95 = sorted_lat[int(len(latencies) * 0.95)]

    print(f"\n\n{'='*45}")
    print(f"  样本数:   {len(latencies)}")
    print(f"  均值:     {statistics.mean(latencies):.1f} ms")
    print(f"  中位数:   {statistics.median(latencies):.1f} ms")
    print(f"  P95:      {p95:.1f} ms")
    print(f"  最大值:   {max(latencies):.1f} ms")
    print(f"  标准差:   {statistics.stdev(latencies):.1f} ms")
    print(f"{'='*45}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "wss://localhost:8765"
    n   = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    asyncio.run(measure(url, n))
