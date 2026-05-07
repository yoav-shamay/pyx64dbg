from pyx64dbg.debugger import Debugger

class DebuggerState:
    """
    A class that contains common data related to the current state of the debugger, such as registers and breakpoints.
    Will be saved on the main window, and used to update the various views as it changes.
    Prevents calling the worker thread every time we want to get this data.
    """
    def __init__(self, debugger : Debugger):
        """
        Allows initialization from a Debugger object.
        """
        self.standard_regs = debugger.registers.standard_regs
        self.breakpoints = debugger.breakpoints.get_breakpoints()
        self.stopped_signal = debugger.stopped_signal
