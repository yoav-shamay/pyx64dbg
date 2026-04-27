import inspect
from pyx64dbg.debugger import Debugger

def print_breakpoints(self):
    """
    Prints the current breakpoints.
    """
    breakpoints = self.debugger.breakpoints.get_breakpoints()
    print("Current breakpoints:")
    for bp in breakpoints:
        print(f"0x{bp:016x}")

def help(self, obj=None):
    """
    Show help for the given object, or general help if no object is provided.
    If the object is a function, shows its signature.
    Prints the docstring of the object if it exists.
    """
    if obj is None:
        print(self.help_message)
    else:
        # if a function, print its signature
        if callable(obj):
            print(f"{obj.__name__}{inspect.signature(obj)}")
        # print the docstring of the object
        docstring = obj.__doc__
        if docstring is None:
            print("No help available for this object.")
        else:
            docstring = docstring.strip() # strip leading and trailing newlines
            print(docstring)

def run_process(self, *argv):
        """
        Run the process. Can give optional arguments to the process, e. g. run_process("arg1", "arg2").
        """
        argv_list = list(argv)
        self.debugger = Debugger.start_and_debug(self.file_name, redirect_stdio_to_pty=False, argv=argv_list)
        # call the debugger update callback if it exists
        if self.new_debugger_object_callback is not None:
            self.new_debugger_object_callback(None)
        
        self.debugger.exit_callback = self._handle_process_exit
        self.debugger.stop_callback = self._handle_process_stop
        self.process_running = True
        self._init_help_message()
        # update the aliases in the interactive console to reflect the new state of the debugger, which may have new commands available now that the process is running
        if self.update_aliases_callback is not None:
            self.update_aliases_callback(self.get_aliases())