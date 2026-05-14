from __future__ import annotations

from typing import Callable, ParamSpec, Generic

P = ParamSpec("P") # parameter specifications of the callables

class CallbackList(Generic[P]):
    """
    Manages a list of callbacks and allows triggering them with arguments.
    Used to manage the various callbacks in the debugger
    """
    def __init__(self):
        self._callbacks: list[Callable[P, None]] = []
    
    def add(self, callback: Callable[P, None]):
        """
        Adds a given callback to the list.
        """
        self._callbacks.append(callback)
    
    def remove(self, callback: Callable[P, None]):
        """
        Removes a given callback from the list.
        """
        self._callbacks.remove(callback)
    
    def trigger(self, *args: P.args, **kwargs: P.kwargs) -> None:
        """
        Triggers all callbacks in the list with the given arguments.
        """
        for callback in self._callbacks:
            callback(*args, **kwargs)