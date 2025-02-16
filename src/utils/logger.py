from loguru import logger
import os

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logger
logger.add(
    "logs/app.log",
    rotation="500 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
)

# Export logger instance
__all__ = ['logger'] 