from typing import Optional

class ProcessExitedError(Exception):
    """
    This class represents an error that occurs when attempting to run a debugger function after the process has exited.
    Should not occur when using the console, however can happen when using the API.
    """
    def __init__(self, exit_code: Optional[int]=None, signal: Optional[int]=None) -> None:
        self.exit_code: int | None = exit_code
        self.signal: int | None = signal

    def __str__(self) -> str:
        """
        Produces a string representation of the error, indicating the exit code or signal if available.
        """
        if self.exit_code is not None:
            return f"Process exited with code {self.exit_code}"
        if self.signal is not None:
            return f"Process terminated by signal {self.signal}"
        return "Process exited"

