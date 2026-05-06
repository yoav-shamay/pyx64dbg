from IPython.terminal.embed import InteractiveShellEmbed
from IPython.terminal.prompts import Prompts, Token
from pyx64dbg.interactive_console.interactive_console import InteractiveConsole, banner
import atexit
import sys

class ConsolePrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [(Token.Prompt, "PyX64Dbg> ")]


class IPythonCLI:
    def __init__(self, file_name = None, verbose=False):
        self.file_name = file_name
        self.verbose = verbose
        self.interactive_console = InteractiveConsole(
            file_name,
            redirect_stdio_to_pty=False
        )
        self.interactive_console.update_aliases_callbacks.add(self._refresh_aliases)
        self.interactive_console.new_debugger_object_callbacks.add(self._update_debugger_object)
        self.debugger = None

    def _refresh_aliases(self, aliases):
        self.shell.push(aliases)

    def _update_debugger_object(self, debugger):
        self.debugger = debugger
    
    def _show_simple_error(
        self,
        exc_tuple=None,
        filename=None,
        tb=None,
        tb_offset=None,
        exception_only=False,
        running_compiled_code=False,
    ):
        """
        Custom error handler to show only the exception type and message without the full traceback.
        This is in order to simplify the error output for the user.
        """
        if exc_tuple is not None:
            exc_type, exc_value, _ = exc_tuple
        else:
            exc_type, exc_value, _ = sys.exc_info()
        self.interactive_console.print_error(exc_type.__name__, exc_value)

    def start_console(self):
        atexit.register(self.interactive_console.handle_exit)  # register the exit handler
        self.shell = InteractiveShellEmbed(colors="linux", display_banner=False)
        # define custom prompt (PyX64Dbg>) for the console
        self.shell.prompts = ConsolePrompt(self.shell)
        # disable tracebacks to avoid overwhelming the user with internal errors of the console, which are not relevant to the user and can be confusing]
        # unless verbose mode is enabled, in which case we want to show the full traceback for debugging purposes
        if not self.verbose:
            self.shell.showtraceback = self._show_simple_error
        self.shell.autocall = (
            2  # allow to call functions without parentheses, e. g. "s" instead of "s()"
        )
        # Disable the kernel from printing the autocall expansion to keep the CLI cleaner
        self.shell.show_rewritten_input = False
        print(banner, end='') # banner already has a newline at the end
        self.shell(local_ns=self.interactive_console.get_aliases())
