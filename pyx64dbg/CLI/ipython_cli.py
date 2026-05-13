from typing import Optional

from IPython.terminal.embed import InteractiveShellEmbed
from IPython.terminal.prompts import Prompts, Token
from pyx64dbg.interactive_console.interactive_console import InteractiveConsole, banner
import atexit
import sys

class ConsolePrompt(Prompts):
    """
    An implementation of the IPython Prompts class to define a custom prompt for our interactive console.
    We want to show "PyX64Dbg> " as the prompt for our console.
    """
    def in_prompt_tokens(self, cli=None):
        """
        Override of the in_prompt_tokens method to return our custom prompt.
        """
        return [(Token.Prompt, "PyX64Dbg> ")]


class IPythonCLI:
    """
    A class that manages the IPython CLI for the debugger.
    Uses the InteractiveConsole class to manage the console state, and uses IPython for the shell itself.
    """
    def __init__(self, file_name: Optional[str] = None, verbose: bool = False):
        self._verbose: bool = verbose
        # create the interactive console object. We want stdio to appear in the terminal, so we don't redirect it to a PTY.
        self._interactive_console = InteractiveConsole(
            file_name,
            redirect_stdio_to_pty=False
        )
        # register our callbacks for updating aliases
        self._interactive_console.update_aliases_callbacks.add(self._refresh_aliases)

    def _refresh_aliases(self, aliases: dict[str, object]) -> None:
        """
        The callback for refreshing the aliases in the interactive console.
        Moves the aliases to the IPython shell's user namespace so that they are accessible to the user.
        """
        self._shell.push(aliases)
    
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
        # if we are not provided exc_tuple, take it from sys.exc_info() to get the current exception
        if exc_tuple is not None:
            exc_type, exc_value, _ = exc_tuple
        else:
            exc_type, exc_value, _ = sys.exc_info()
        # use the console printing error message with the name of the exception class and its msg
        self._interactive_console.print_error(exc_type.__name__, exc_value)

    def start_console(self) -> None:
        """
        Starts the IPython interactive console.
        """
        atexit.register(self._interactive_console.handle_exit)  # register the console exit handler using atexit
        # create the InteractiveShellEmbed object for the console, with linux colors and no banner (we have our own banner that we print separately)
        self._shell = InteractiveShellEmbed(colors="linux", display_banner=False)
        # define custom prompt (PyX64Dbg>) for the console
        self._shell.prompts = ConsolePrompt(self._shell)
        # if verbose mode is disabled, use the custom simple error handler that shows reduced error information to simplify console output
        if not self._verbose:
            self._shell.showtraceback = self._show_simple_error
        # allow to call functions without parentheses, e. g. "s" instead of "s()"
        self._shell.autocall = (2)
        # Disable the kernel from printing the autocall expansion to keep the CLI cleaner
        self._shell.show_rewritten_input = False
        print(banner, end='') # banner already has a newline at the end
        # start the shell with the initial aliases from the interactive console
        self._shell(local_ns=self._interactive_console.get_aliases())
