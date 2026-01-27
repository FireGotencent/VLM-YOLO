"""
VisionGuide Server - 服务端入口
"""

import asyncio
from server.websocket_server import main

if __name__ == "__main__":
    asyncio.run(main())
