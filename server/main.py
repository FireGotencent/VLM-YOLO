"""
VisionGuide Server - 服务端入口
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.websocket_server import main

if __name__ == "__main__":
    asyncio.run(main())
