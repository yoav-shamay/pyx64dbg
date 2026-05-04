
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

class FileNotSelectedError(Exception):
    """
    Exception raised when trying to access an object that requires a file to be selected, but no file is selected.
    """
    def __init__(self):
        message = "No file is selected."
        super().__init__(message)