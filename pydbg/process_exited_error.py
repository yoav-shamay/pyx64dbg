class ProcessExitedError(Exception):
    """
    This class represents an error that occurs when attempting to run a debugger function after the process has exited.
    Should not occur when using the console, however can happen when using the API.
    """
    def __init__(self, exit_code=None, signal=None):
        self.exit_code = exit_code
        self.signal = signal

    def __str__(self):
        if self.exit_code is not None:
            return f"Process exited with code {self.exit_code}"
        if self.signal is not None:
            return f"Process terminated by signal {self.signal}"
        return "Process exited"

