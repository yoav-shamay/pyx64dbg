import inspect
import sys
from pyx64dbg.interactive_console.console_commands import get_available_commands, get_all_commands_help
from IPython.terminal.embed import InteractiveShellEmbed
from IPython.terminal.prompts import Prompts, Token
from pyx64dbg.interactive_console.invalid_process_state_trap import ExceptionTrap, ProcessAlreadyRunningError, ProcessNotRunningError
from prompt_toolkit import print_formatted_text, HTML
from pyx64dbg.debugger import Debugger
import atexit

class ConsolePrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [(Token.Prompt, "PyX64Dbg> ")]

banner = """Welcome to the PyX64Dbg interactive console!
Type help for more information."""

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
    def __init__(self, file_name, verbose=False):
        self.file_name = file_name
        self.debugger = None
        self.process_running = False
        self.verbose = verbose
        self._init_help_message()
        self._process_already_running_trap = ExceptionTrap(ProcessAlreadyRunningError())
        self._process_not_running_trap = ExceptionTrap(ProcessNotRunningError())
    
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
    
    def _get_aliases(self):
        cur_commands = get_available_commands(self, self.process_running)
        aliases = {}
        for names, obj in cur_commands:
            for name in names:
                aliases[name] = obj
        return aliases

    def _refresh_aliases(self):
        aliases = self._get_aliases()
        self.shell.push(aliases)
    
    
    def _init_help_message(self):
        """
        Initializes the help message by replacing the <METHODS_LIST> placeholder with a list of the available methods and their descriptions.
        """
        command_help = get_all_commands_help()
        methods_list = ""
        for names, description in command_help:
            methods_list += f"- {' / '.join(names)}: {description}\n"
        self.help_message = help_message.replace("<METHODS_LIST>", methods_list)

    def _show_simple_error(self, exc_tuple=None, filename=None, tb=None, tb_offset=None,
                          exception_only=False, running_compiled_code=False):
        """
        Shows error message only, without overwhelming the user with internal errors of the console, which are not relevant to the user and can be confusing.
        """
        if exc_tuple is not None:
            exc_type, exc_value, _ = exc_tuple
        else:
            exc_type, exc_value, _ = sys.exc_info()
        # print the error type in red and bold, and the error message normally.
        output = f"<ansired><b>{exc_type.__name__}</b></ansired>: {exc_value}"
        print_formatted_text(HTML(output))
    
    def _handle_process_exit(self):
        if self.debugger.exit_code is not None:
            print(f"Process exited with code {self.debugger.exit_code}.")
        else:
            exit_signal = self.debugger.error_signal
            print(f"Process terminated by signal {exit_signal}.")
        self.debugger = None
        self.process_running = False
        self._refresh_aliases()
        self._init_help_message()

    def _handle_process_stop(self):
        """
        Handle process stopping by signal, not forwarding it yet, which means the process is still active.
        """
        stop_signal = self.debugger.stopped_signal
        print(f"Process stopped by signal {stop_signal}.")

    def run_process(self, *argv):
        """
        Run the process. Can give optional arguments to the process, e. g. run_process("arg1", "arg2").
        """
        argv_list = list(argv)
        self.debugger = Debugger.start_and_debug(self.file_name, redirect_stdio_to_pty=False, argv=argv_list)
        self.debugger.exit_callback = self._handle_process_exit
        self.debugger.stop_callback = self._handle_process_stop
        self.process_running = True
        self._refresh_aliases()
        self._init_help_message()
    
    def _handle_exit(self):
        """
        Kill the debugged process if it's still running when exiting the console.
        """
        if self.process_running:
            self.debugger.exit_callback = None # disable the exit callback to avoid printing the exit message when we kill the process
            self.debugger.kill_process()

    def start_console(self):
        atexit.register(self._handle_exit) # register the exit handler
        self.shell = InteractiveShellEmbed(colors='linux' ,display_banner=False)
        # define custom prompt (PyX64Dbg>) for the console
        self.shell.prompts = ConsolePrompt(self.shell)
        # disable tracebacks to avoid overwhelming the user with internal errors of the console, which are not relevant to the user and can be confusing
        if not self.verbose:
            self.shell.showtraceback = self._show_simple_error
        self.shell.autocall = 2 # automatically call functions without parentheses, e. g. "s" instead of "s()"
        print(banner)
        self.shell(local_ns=self._get_aliases())
    
    from interactive_console.disassembly import print_disassembly, _mem_operand_to_str