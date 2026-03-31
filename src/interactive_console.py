import inspect
from commands import get_commands
from IPython.terminal.embed import InteractiveShellEmbed
from IPython.terminal.prompts import Prompts, Token

class ConsolePrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [(Token.Prompt, "PyDbg> ")]

banner = """Welcome to the PyDbg interactive console!
Type help for more information."""

help_message = """This is an interactive python console.
Available methods / objects:
<METHODS_LIST>
You can also use the number types defined in the number_types module, such as Int32, UInt64, etc., for reading numbers from memory.
You can also call functions without parenthesis, e. g. "s" or "dis regs.rip,10".
Use help(object) to view the docstring for any of the above methods or properties for more details on their usage, or help(number_types) to view the available number types and their details."""

class InteractiveConsole:
    """
    An ipython-based interactive console for debugging.
    Allows the user to interact with the debugger in a REPL-like environment.
    Defines aliases for commonly used functions and attributes to make them easier to access in the interactive console.
    """
    def __init__(self, debugger):
        self.debugger = debugger
        self._init_help_message()
    
    def print_disassembly(self, address : int, instruction_cnt : int) -> None:
        """
        Prints the disassembly of the instructions at the given address.
        Disassembles instruction_cnt instructions.
        """
        instructions = self.debugger.memory.read_instruction(address, instruction_cnt)
        for instruction in instructions:
            print(f"0x{instruction.address:016x}: {instruction.mnemonic:<8} {instruction.op_str}")
    
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
                print(docstring)

    def _get_aliases(self):
        """
        Define aliases for commonly used functions and attributes to make them easier to access in the interactive console.
        """
        commands = get_commands(self)
        aliases_dict = {}
        for names, func, _ in commands:
            for name in names:
                aliases_dict[name] = func
        return aliases_dict
    
    def _init_help_message(self):
        """
        Initializes the help message by replacing the <METHODS_LIST> placeholder with a list of the available methods and their descriptions.
        """
        commands = get_commands(self)
        methods_list = ""
        for names, _, description in commands:
            methods_list += f"- {' / '.join(names)}: {description}\n"
        self.help_message = help_message.replace("<METHODS_LIST>", methods_list)

    def run(self):
        shell = InteractiveShellEmbed(colors='linux',user_ns=self._get_aliases() ,display_banner=False)
        shell.prompts = ConsolePrompt(shell)
        shell.autocall = 2 # automatically call functions without parentheses, e. g. "s" instead of "s()"
        print(banner)
        shell()