"""
VisionGuide LLM System - 程序入口

基于多模态大模型与YOLO目标检测的盲人避障导航系统
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    
    from src.utils.config import load_config
    from src.utils.logger import setup_logger
    from src.ui.main_window import MainWindow
    
    # 加载配置
    config = load_config()
    
    # 设置日志
    setup_logger(
        level=config.logging.level,
        log_file=config.logging.file,
        rotation=config.logging.rotation
    )
    
    from src.utils.logger import get_logger
    logger = get_logger()
    
    logger.info("=" * 50)
    logger.info("VisionGuide LLM System 启动")
    logger.info("=" * 50)
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置全局样式
    app.setStyleSheet("""
        * {
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
        }
    """)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    logger.info("应用程序已启动")
    
    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
