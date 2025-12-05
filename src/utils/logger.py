"""日志管理模块

提供统一的日志记录功能，支持不同级别的日志输出。
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_level: str = "INFO", log_file: bool = True):
    """配置全局logger

    Args:
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR）
        log_file: 是否输出到文件
    """
    # 移除默认handler
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )

    # 添加文件输出
    if log_file:
        project_root = Path(__file__).resolve().parent.parent.parent
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        # 普通日志
        logger.add(
            log_dir / "wenning_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation="00:00",  # 每天00:00轮转
            retention="7 days",  # 保留7天
            compression="zip"  # 压缩旧日志
        )

        # 错误日志单独记录
        logger.add(
            log_dir / "errors_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            rotation="00:00",
            retention="30 days",
            compression="zip"
        )


# 默认配置logger
setup_logger()


def get_logger(name: str = None):
    """获取logger实例

    Args:
        name: logger名称，通常使用__name__

    Returns:
        logger实例
    """
    if name:
        return logger.bind(name=name)
    return logger
