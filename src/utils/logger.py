"""
日志工具模块
基于 loguru 提供统一的日志管理
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


# 移除默认的 handler
logger.remove()

# 全局 logger 实例
_logger_initialized = False


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    rotation: str = "10 MB"
) -> None:
    """
    初始化日志配置
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        rotation: 日志轮转大小
    """
    global _logger_initialized
    
    if _logger_initialized:
        return
    
    # 控制台输出
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True
    )
    
    # 文件输出
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation=rotation,
            retention="7 days",
            encoding="utf-8"
        )
    
    _logger_initialized = True
    logger.info("日志系统初始化完成")


def get_logger():
    """
    获取 logger 实例
    
    Returns:
        loguru.Logger: logger 实例
    """
    return logger
