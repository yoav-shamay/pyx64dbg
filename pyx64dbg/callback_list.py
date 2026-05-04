class CallbackList:
    def __init__(self):
        self._callbacks = []
    
    def add(self, callback):
        self._callbacks.append(callback)
    
    def remove(self, callback):
        self._callbacks.remove(callback)
    
    def trigger(self, *args, **kwargs):
        for callback in self._callbacks:
            callback(*args, **kwargs)