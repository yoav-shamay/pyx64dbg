class ExceptionTrap:
    """
    This class represents an object to return in case the console access an object that is not available based on the process running / not running.
    When trying to use this object, it will raise the wanted exception.
    """
    def __init__(self, exception):
        super().__setattr__("exception", exception) # store the exception in a way that doesn't call __setattr__ again to avoid infinite recursion
    
    def _raise_exception(self, *args, **kwargs):
        raise self.exception
    
    __getattr__ = _raise_exception
    __call__ = _raise_exception
    __repr__ = _raise_exception
    __str__ = _raise_exception
    __getitem__ = _raise_exception
    __setitem__ = _raise_exception
    __setattr__ = _raise_exception

    def __dir__(self):
        # Prevent dir() from showing any attributes to avoid confusion, since all attributes raise the exception when accessed
        return []


class ProcessNotRunningError(Exception):
    """
    Exception raised when trying to access an object that requires the process to be running, but the process is not running.
    """
    def __init__(self):
        message = "The process is not running."
        super().__init__(message)

class ProcessAlreadyRunningError(Exception):
    """
    Exception raised when trying to access an object that requires the process to be not running, but the process is running.
    """
    def __init__(self):
        message = "The process is already running."
        super().__init__(message)