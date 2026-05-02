import inspect
from pyx64dbg.debugger import Debugger

def print_breakpoints(self) -> None:
    """
    Prints the current breakpoints.
    """
    breakpoints = self.debugger.breakpoints.get_breakpoints()
    print("Current breakpoints:", file=self._output_stream)
    for bp in breakpoints:
        print(f"0x{bp:016x}", file=self._output_stream)

def help(self, obj=None) -> None:
    """
    Show help for the given object, or general help if no object is provided.
    If the object is a function, shows its signature.
    Prints the docstring of the object if it exists.
    """
    if obj is None:
        print(self.help_message, file=self._output_stream)
    else:
        # if a function, print its signature
        if callable(obj):
            print(f"{obj.__name__}{inspect.signature(obj)}", file=self._output_stream)
        # print the docstring of the object
        docstring = obj.__doc__
        if docstring is None:
            print("No help available for this object.", file=self._output_stream)
        else:
            docstring = docstring.strip() # strip leading and trailing newlines
            print(docstring, file=self._output_stream)

def run_process(self, *argv) -> None:
    """
    Run the process. Can give optional arguments to the process, e. g. run_process("arg1", "arg2").
    """
    if self.file_name is None:
        raise ValueError("No file specified to run.")
    argv_list = list(argv)
    self.debugger = Debugger.start_and_debug(self.file_name, redirect_stdio_to_pty=self._redirect_stdio_to_pty, disable_pty_echo=self._disable_pty_echo, argv=argv_list)
    # call the debugger update callback if it exists
    if self.new_debugger_object_callback is not None:
        self.new_debugger_object_callback(self.debugger)
    self._on_process_run() # call the process run handler to set up aliases and help message


def select_file(self, file_name : str) -> None:
    """
    Selects a new file to debug.
    Stops the currently running process if there is one, as we switch to a new file.
    """
    self.file_name = file_name
    if self.process_running:
        # remove the exit callback to avoid printing exit message after exiting
        self.debugger.exit_callbacks.remove(self._handle_process_exit)
        # kill the running process
        self.debugger.kill_process()
        # set that there's no active debugger / process
        self.debugger = None
        self._on_process_exit() # call the process exit handler to update aliases, process_running and help message
        # call the new debugger object callback as we updated debugger to None
        if self.new_debugger_object_callback is not None:
            self.new_debugger_object_callback(None)