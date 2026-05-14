import sys
from typing import Callable, TextIO, Optional

from pyx64dbg.debugger import Debugger
from pyx64dbg.interactive_console.console_aliases import (
    get_aliases,
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
Type help for more information.
"""

class InteractiveConsole:
    """
    An ipython-based interactive console for debugging.
    Allows the user to interact with the debugger in a REPL-like environment.
    Defines aliases for commonly used functions and attributes to make them easier to access in the interactive console.
    """

    def __init__(
        self,
        file_name: Optional[str] = None,
        redirect_stdio_to_pty : bool = True,
        disable_pty_echo: bool = True,
        stdout_stream: Optional[TextIO]=None,
    ):
        """
        Initializes the interactive console.
        Options:
        file_name - initial file to debug (can also be set later with select_file command)
        redirect_stdio_to_pty - whether to redirect the debugged process's stdio to a PTY
        disable_pty_echo - whether to disable echo on the PTY (if redirecting)
        stdout_stream - the stream to print output to (defaults to sys.stdout)
        """
        self.file_name: str | None = file_name
        self.debugger: Debugger | None = None
        self._init_help_message()
        self.file_select_callbacks: CallbackList[[str]] = CallbackList()
        self.update_aliases_callbacks: CallbackList[[dict[str, object]]] = CallbackList()
        self.new_debugger_object_callbacks: CallbackList[[Debugger | None]] = CallbackList()
        self._process_already_running_trap: ExceptionTrap = ExceptionTrap(ProcessAlreadyRunningError())
        self._process_not_running_trap: ExceptionTrap = ExceptionTrap(ProcessNotRunningError())
        self._output_stream: TextIO = stdout_stream if stdout_stream is not None else sys.stdout
        # the output object for the toolkit, used for formatting text.
        # for the terminal size, use a hardcoded lambda with the standard default size (80x24) as it doesn't matter for our usage.
        self._toolkit_output: Vt100_Output = Vt100_Output(self._output_stream, lambda: (24, 80))
        self._redirect_stdio_to_pty: bool = redirect_stdio_to_pty
        self._disable_pty_echo: bool = disable_pty_echo
        self.system_msg_wrapper: Callable[[str], str] = lambda msg: msg + "\n" # default wrapper - just add newline, can be modified later

    def get_aliases(self) -> dict[str, object]:
        """
        Returns the current aliases for the interactive console based on the process state.
        """
        process_running = self.debugger is not None # we have a running process iff debugger object is not None
        return get_aliases(self, process_running)

    def _init_help_message(self) -> None:
        """
        Initializes the help message by replacing the <METHODS_LIST> placeholder with a list of the available methods and their descriptions.
        """
        command_help = get_all_commands_help()
        methods_list = ""
        for names, description in command_help:
            methods_list += f"- {' / '.join(names)}: {description}\n"
        self.help_message = help_message.replace("<METHODS_LIST>", methods_list)


    def _handle_process_exit(self) -> None:
        """
        Callback when the process exits.
        Prints a message and updates the internal state.
        """
        if self.debugger is None:
            # if this was mistakenly called when there's no debugger, just ignore it and return without doing anything
            return
        if self.debugger.exit_code is not None:
            msg = f"Process exited with code {self.debugger.exit_code}."
        else:
            exit_signal = self.debugger.error_signal
            if exit_signal is not None:
                msg = f"Process terminated by signal {exit_signal}."
            else:
                msg = "Process exited."
        print(self.system_msg_wrapper(msg), end='', file=self._output_stream)
        # remove all callbacks now that we remove the reference to the debugger, as they can still be called
        self.debugger.exit_callbacks.remove(self._handle_process_exit)
        self.debugger.stop_callbacks.remove(self._handle_process_stop)
        self.debugger = None
        self.new_debugger_object_callbacks.trigger(None)
        self._on_process_exit() # call the process exit handler to update aliases

    def _handle_process_stop(self) -> None:
        """
        Callback when the process stops by signal, not forwarding it yet, which means the process is still active.
        """
        if self.debugger is None:
            # if this was mistakenly called when there's no debugger, just ignore it and return without doing anything
            return
        stop_signal = self.debugger.stopped_signal
        if stop_signal is not None:
            # if we stopped by a real signal and not a breakpoint
            msg = f"Process stopped by signal {stop_signal}."
            print(self.system_msg_wrapper(msg), end='', file=self._output_stream)

    def print_error(self, exc_name: str, exc_desc: str) -> None:
        """
        Function to call in order to print a triggered exception in a user-friendly way.
        Should be manually called by the CLI / GUI using this object.
        """
        output = f"<ansired><b>{exc_name}</b></ansired>: {exc_desc}"
        print_formatted_text(HTML(output), output=self._toolkit_output)
    
    def handle_exit(self) -> None:
        """
        An exit handler that kills the debugged process if it's still running when exiting the CLI.
        Should be manually set by the CLI / GUI using this object.
        """
        if self.debugger is None: # if the debugger is already None, it means the process isn't running and we don't have to do anything
            return
        # remove the exit callback to avoid printing exit message after exiting
        self.debugger.exit_callbacks.remove(self._handle_process_exit)
        self.debugger.control.kill_process()
    
    def _on_process_run(self) -> None:
        """
        A helper function that sets up the debugger callbacks and aliases when the process starts.
        Should be run whenever a new debugger object is created.
        """
        if self.debugger is None:
            # if this was mistakenly called when there's no debugger, just ignore it and return without doing anything
            return
        self.debugger.exit_callbacks.add(self._handle_process_exit)
        self.debugger.stop_callbacks.add(self._handle_process_stop)
        # update the aliases in the interactive console to reflect the new state of the debugger, which may have new commands available now that the process is running
        self.update_aliases_callbacks.trigger(self.get_aliases())
    
    def _on_process_exit(self) -> None:
        """
        A helper function that handles the stuff needs to be done when a process exits.
        Currently just calls the update aliases callback to update the aliases in the console itself.
        Should be run whenever the debugger object is set to None.
        """
        # update the aliases in the interactive console to reflect the new state of the debugger, which may have some commands unavailable now that the process is not running
        self.update_aliases_callbacks.trigger(self.get_aliases())
    
    def update_debugger(self, debugger: Debugger | None) -> None:
        """
        Should be called when the debugger object is updated from an external source.
        Syncs the state of the interactive console with the new debugger state.
        """
        self.debugger = debugger
        if self.debugger is None:
            self._on_process_exit()
        else:
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
