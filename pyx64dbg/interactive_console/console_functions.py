"""
This module includes various functions that are used exclusively in the interactive console, and not in the debugger API itself.
Those functions print output to the console, or change the internal console state.
Includes:
- print_breakpoints: prints the current breakpoints in the process.
- help: shows help for a given object, or general help if no object is provided.
- run_process: runs the process with optional arguments.
- select_file: selects a new file to debug, stopping the currently running process if there is
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
import inspect
from pyx64dbg.debugger import Debugger
from pyx64dbg.utils import validate_file
from pyx64dbg.interactive_console.exceptions import FileNotSelectedError

if TYPE_CHECKING:
    from pyx64dbg.interactive_console.interactive_console import InteractiveConsole


def print_breakpoints(console: InteractiveConsole) -> None:
    """
    Prints the current breakpoints.
    """
    breakpoints = console.debugger.breakpoints.get_breakpoints()
    print("Current breakpoints:", file=console._output_stream)
    for bp in breakpoints:
        print(f"0x{bp:016x}", file=console._output_stream)


def help(console: InteractiveConsole, obj: Any = None) -> None:
    """
    Show help for the given object, or general help if no object is provided.
    If the object is a function, shows its signature.
    Prints the docstring of the object if it exists.
    """
    if obj is None:
        # if we didn't ask help for a specific object, print the general message
        print(console.help_message, file=console._output_stream)
    else:
        # if a function, print its signature
        if callable(obj):
            print(f"{obj.__name__}{inspect.signature(obj)}", file=console._output_stream)
        # print the docstring of the object
        docstring = obj.__doc__
        if docstring is None:  # no docstring, print a default message
            print("No help available for this object.", file=console._output_stream)
        else:
            docstring = docstring.strip()  # strip leading and trailing newlines
            print(docstring, file=console._output_stream)


def run_process(console: InteractiveConsole, *argv: str) -> None:
    """
    Run the process. Can give optional arguments to the process, e. g. run_process("arg1", "arg2").
    """
    if console.file_name is None:
        # no file is selected - we can't run
        raise FileNotSelectedError()
    argv_list = list(argv) # convert to list for usage in the API
    # create the debugger object using start_and_debug
    console.debugger = Debugger.start_and_debug(
        console.file_name,
        redirect_stdio_to_pty=console._redirect_stdio_to_pty,
        disable_pty_echo=console._disable_pty_echo,
        argv=argv_list,
    )
    # call the debugger update callbacks
    console.new_debugger_object_callbacks.trigger(console.debugger)
    console._on_process_run()  # call the process run handler to set up aliases


def select_file(console: InteractiveConsole, file_name: str, trigger_callbacks: bool = True) -> None:
    """
    Selects a new file to debug.
    Stops the currently running process if there is one, as we switch to a new file.
    """
    # validate the file before selecting
    validate_file(file_name)
    console.file_name = file_name
    if console.debugger is not None:
        # if the process is running, we need to stop it before switching to a new file
        # remove the exit callback to avoid printing exit message after exiting
        console.debugger.exit_callbacks.remove(console._handle_process_exit)
        # kill the running process
        console.debugger.control.kill_process()
        # set that there's no active debugger / process
        console.debugger = None
        console._on_process_exit()  # call the process exit handler to update aliases
        # call the new debugger object callbacks as we updated debugger to None, if we want to trigger them
        if trigger_callbacks:
            console.new_debugger_object_callbacks.trigger(None)
    # call the file select callbacks to notify about the file change
    if trigger_callbacks:
        console.file_select_callbacks.trigger(file_name)
