import sys
from typing import Callable

from elftools.construct import Debugger
from pyx64dbg.interactive_console.console_commands import (
    get_available_commands,
    get_all_commands_help,
)
from pyx64dbg.interactive_console.exception_trap import ExceptionTrap
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit import print_formatted_text, HTML
from pyx64dbg.callback_list import CallbackList
from pyx64dbg.interactive_console.exceptions import ProcessAlreadyRunningError, ProcessNotRunningError

help_message = """This is an interactive python console.
Available methods / objects:
<METHODS_LIST>
You can also use the number types such as Int32, UInt64, etc., for constant-size integers. See help(number_types) for more details.
You can also call functions without parenthesis, e. g. "s" or "dis regs.rip,10".
Use help(object) to view the docstring for any of the above methods or properties for more details on their usage."""

banner = """Welcome to the PyX64Dbg interactive console!
Type help for more information."""

class InteractiveConsole:
    """
    An ipython-based interactive console for debugging.
    Allows the user to interact with the debugger in a REPL-like environment.
    Defines aliases for commonly used functions and attributes to make them easier to access in the interactive console.
    """

    def __init__(
        self,
        file_name: str = None,
        redirect_stdio_to_pty : bool = True,
        disable_pty_echo: bool = True,
        stdout_stream=None,
    ):
        self.file_name = file_name
        self.debugger = None
        self.process_running = False
        self._init_help_message()
        self.file_select_callbacks = CallbackList()
        self.update_aliases_callbacks = CallbackList()
        self.new_debugger_object_callbacks = CallbackList()
        self._process_already_running_trap = ExceptionTrap(ProcessAlreadyRunningError())
        self._process_not_running_trap = ExceptionTrap(ProcessNotRunningError())
        self._output_stream = stdout_stream if stdout_stream is not None else sys.stdout
        self._toolkit_output = Vt100_Output(self._output_stream, lambda: (24, 80))
        self._redirect_stdio_to_pty = redirect_stdio_to_pty
        self._disable_pty_echo = disable_pty_echo
        
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
            print(f"Process exited with code {self.debugger.exit_code}.", file=self._output_stream)
        else:
            exit_signal = self.debugger.error_signal
            print(f"Process terminated by signal {exit_signal}.", file=self._output_stream)
        # remove all callbacks now that we remove the reference to the debugger, as they can still be called
        self.debugger.exit_callbacks.remove(self._handle_process_exit)
        self.debugger.stop_callbacks.remove(self._handle_process_stop)
        self.debugger = None
        self.new_debugger_object_callbacks.trigger(None)
        self._on_process_exit() # call the process exit handler to update aliases and help message

    def _handle_process_stop(self):
        """
        Handle process stopping by signal, not forwarding it yet, which means the process is still active.
        """
        stop_signal = self.debugger.stopped_signal
        if stop_signal is not None:
            # if we stopped by a real signal and not a breakpoint
            print(f"Process stopped by signal {stop_signal}.", file=self._output_stream)

    def print_error(self, exc_name, exc_desc):
        """
        Function to call in order to print a triggered exception in a user-friendly way.
        Should be manually called by the CLI / GUI using this object.
        """
        output = f"<ansired><b>{exc_name}</b></ansired>: {exc_desc}"
        print_formatted_text(HTML(output), output=self._toolkit_output)
    
    def handle_exit(self):
        """
        An exit handler that kills the debugged process if it's still running when exiting the CLI.
        Should be manually set by the CLI / GUI using this object.
        """
        if self.process_running:
            # remove the exit callback to avoid printing exit message after exiting
            self.debugger.exit_callbacks.remove(self._handle_process_exit)
            self.debugger.kill_process()
    
    def _on_process_run(self):
        self.debugger.exit_callbacks.add(self._handle_process_exit)
        self.debugger.stop_callbacks.add(self._handle_process_stop)
        self.process_running = True
        # update the aliases in the interactive console to reflect the new state of the debugger, which may have new commands available now that the process is running
        self.update_aliases_callbacks.trigger(self.get_aliases())
    
    def _on_process_exit(self):
        self.process_running = False
        # update the aliases in the interactive console to reflect the new state of the debugger, which may have some commands unavailable now that the process is not running
        self.update_aliases_callbacks.trigger(self.get_aliases())
    
    def update_debugger(self, debugger):
        """
        Should be called when the debugger object is updated from an external source.
        Syncs the state of the interactive console with the new debugger state.
        """
        self.debugger = debugger
        if self.debugger is None:
            self.process_running = False
            self._on_process_exit()
        else:
            self.process_running = True
            self._on_process_run()

    from pyx64dbg.interactive_console.disassembly_function import (
        print_disassembly,
        _mem_operand_to_str,
    )
    from pyx64dbg.interactive_console.console_functions import (
        print_breakpoints,
        help,
        run_process,
        select_file,
    )
