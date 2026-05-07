from typing import Callable

class CallbackList:
    """
    Manages a list of callbacks and allows triggering them with arguments.
    Used to manage the various callbacks in the debugger
    """
    def __init__(self):
        self._callbacks: list[Callable] = []
    
    def add(self, callback: Callable):
        """
        Adds a given callback to the list.
        """
        self._callbacks.append(callback)
    
    def remove(self, callback: Callable):
        """
        Removes a given callback from the list.
        """
        self._callbacks.remove(callback)
    
    def trigger(self, *args, **kwargs):
        """
        Triggers all callbacks in the list with the given arguments.
        """
        for callback in self._callbacks:
            callback(*args, **kwargs)