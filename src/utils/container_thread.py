import threading
from loguru import logger
# from src.models.container import Container  # Remove top-level import
import time

class ContainerThread(threading.Thread):
    """Thread class with proper cleanup for container logic"""
    
    def __init__(self, target):
        super().__init__(daemon=True)
        self.target = target
        self._stop_event = threading.Event()

    def run(self):
        """Run the container logic with error handling"""
        try:
            self.target()
        except Exception as e:
            logger.error(f"Container thread failed: {str(e)}")
        finally:
            logger.info("Container thread stopped")

    def stop(self):
        """Signal the thread to stop"""
        self._stop_event.set()
        logger.info("Container thread stop requested")

    def stopped(self):
        '''Returns True if the thread is stopped.'''
        return self._stop_event.is_set()