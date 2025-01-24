import threading

class ContainerThread(threading.Thread):
    '''Thread class with a stop() method. The thread itself has to check if stopped() returns True'''

    def __init__(self,  *args, **kwargs):
        '''Initializes the thread.'''
        super(ContainerThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        '''Stops the thread.'''
        self._stop_event.set()

    def stopped(self):
        '''Returns True if the thread is stopped.'''
        return self._stop_event.is_set()