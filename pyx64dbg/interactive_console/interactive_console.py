import sys
from typing import Callable

from elftools.construct import Debugger
from pyx64dbg.interactive_console.console_commands import (
    get_available_commands,
    get_all_commands_help,
)
from pyx64dbg.interactive_console.invalid_process_state_trap import (
    ExceptionTrap,
    ProcessAlreadyRunningError,
    ProcessNotRunningError,
)
from prompt_toolkit import print_formatted_text, HTML
import atexit

help_message = """This is an interactive python console.
Available methods / objects:
<METHODS_LIST>
You can also use the number types such as Int32, UInt64, etc., for constant-size integers. See help(number_types) for more details.
You can also call functions without parenthesis, e. g. "s" or "dis regs.rip,10".
Use help(object) to view the docstring for any of the above methods or properties for more details on their usage."""


class InteractiveConsole:
    """
    An ipython-based interactive console for debugging.
    Allows the user to interact with the debugger in a REPL-like environment.
    Defines aliases for commonly used functions and attributes to make them easier to access in the interactive console.
    """

    def __init__(
        self,
        file_name,
        update_aliases_callback: Callable[[dict], None] = None,
        new_debugger_object_callback: Callable[[Debugger], None] = None
    ):
        self.file_name = file_name
        self.debugger = None
        self.process_running = False
        self._init_help_message()
        self.update_aliases_callback = update_aliases_callback
        self.new_debugger_object_callback = new_debugger_object_callback
        self._process_already_running_trap = ExceptionTrap(ProcessAlreadyRunningError())
        self._process_not_running_trap = ExceptionTrap(ProcessNotRunningError())

    def get_aliases(self):
        cur_commands = get_available_commands(self, self.process_running)
        aliases = {}
        for names, obj in cur_commands:
            for name in names:
                aliases[name] = obj
        return aliases

    def _init_help_message(self):
        """
        Initializes the help message by replacing the <METHODS_LIST> placeholder with a list of the available methods and their descriptions.
        """
        command_help = get_all_commands_help()
        methods_list = ""
        for names, description in command_help:
            methods_list += f"- {' / '.join(names)}: {description}\n"
        self.help_message = help_message.replace("<METHODS_LIST>", methods_list)


    def _handle_process_exit(self):
        if self.debugger.exit_code is not None:
            print(f"Process exited with code {self.debugger.exit_code}.")
        else:
            exit_signal = self.debugger.error_signal
            print(f"Process terminated by signal {exit_signal}.")
        self.debugger = None
        if self.new_debugger_object_callback is not None:
            self.new_debugger_object_callback(None)
        self.process_running = False
        if self.update_aliases_callback is not None:
            self.update_aliases_callback(self.get_aliases())
        self._init_help_message()

    def _handle_process_stop(self):
        """
        Handle process stopping by signal, not forwarding it yet, which means the process is still active.
        """
        stop_signal = self.debugger.stopped_signal
        print(f"Process stopped by signal {stop_signal}.")
    
    def print_error(self, exc_name, exc_desc):
        """
        Function to call in order to print a triggered exception in a user-friendly way.
        Should be manually called by the CLI / GUI using this object.
        """
        output = f"<ansired><b>{exc_name}</b></ansired>: {exc_desc}"
        print_formatted_text(HTML(output))
    
    def handle_exit(self):
        """
        An exit handler that kills the debugged process if it's still running when exiting the CLI.
        Should be manually set by the CLI / GUI using this object.
        """
        if self.process_running:
            self.debugger.exit_callback = None  # disable the exit callback to avoid printing the exit message when we kill the process
            self.debugger.kill_process()


    from pyx64dbg.interactive_console.disassembly_function import (
        print_disassembly,
        _mem_operand_to_str,
    )
    from pyx64dbg.interactive_console.console_functions import (
        print_breakpoints,
        help,
        run_process,
    )
