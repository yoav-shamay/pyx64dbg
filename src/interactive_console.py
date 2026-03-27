import number_types
from IPython.terminal.embed import InteractiveShellEmbed
from IPython.terminal.prompts import Prompts, Token

class ConsolePrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [(Token.Prompt, "PyDbg> ")]


class InteractiveConsole:
    """
    An ipython-based interactive console for debugging.
    Allows the user to interact with the debugger in a REPL-like environment.
    Defines aliases for commonly used functions and attributes to make them easier to access in the interactive console.
    """
    def __init__(self, debugger):
        self.debugger = debugger
    
    def _print_disassembly(self, address : int, instruction_cnt : int) -> None:
        instructions = self.debugger.memory.read_instruction(address, instruction_cnt)
        for instruction in instructions:
            print(f"0x{instruction.address:016x}: {instruction.mnemonic:<8} {instruction.op_str}")
    
    def _print_breakpoints(self):
        breakpoints = self.debugger.breakpoints.get_breakpoints()
        print("Current breakpoints:")
        for bp in breakpoints:
            print(f"0x{bp:016x}")

    def _get_aliases(self):
        """
        Define aliases for commonly used functions and attributes to make them easier to access in the interactive console.
        """
        return {
            "single_step": self.debugger.single_step,
            "step": self.debugger.single_step,
            "s": self.debugger.single_step,

            "continue_execution": self.debugger.continue_execution,
            "cont": self.debugger.continue_execution,
            "c": self.debugger.continue_execution,

            "next": self.debugger.next,
            "n": self.debugger.next,

            "finish": self.debugger.finish,
            "fin": self.debugger.finish,
            "f": self.debugger.finish,

            "registers": self.debugger.registers,
            "regs": self.debugger.registers,

            "memory": self.debugger.memory,
            "mem": self.debugger.memory,

            "read_number": self.debugger.memory.read_number,
            "read_num": self.debugger.memory.read_number,

            "Int8": number_types.Int8,
            "UInt8": number_types.UInt8,
            "Int16": number_types.Int16,
            "UInt16": number_types.UInt16,
            "Int32": number_types.Int32,
            "UInt32": number_types.UInt32,
            "Int64": number_types.Int64,
            "UInt64": number_types.UInt64,
            "Char": number_types.Char,
            "UChar": number_types.UChar,
            "Short": number_types.Short,
            "UShort": number_types.UShort,
            "Int": number_types.Int,
            "UInt": number_types.UInt,
            "Long": number_types.Long,
            "ULong": number_types.ULong,

            "disassemble": self._print_disassembly,
            "dis": self._print_disassembly,

            "add_breakpoint": self.debugger.breakpoints.add_breakpoint,
            "brk": self.debugger.breakpoints.add_breakpoint,
            "b": self.debugger.breakpoints.add_breakpoint,
            "remove_breakpoint": self.debugger.breakpoints.remove_breakpoint,
            "breakpoints": self._print_breakpoints,
            "brks": self._print_breakpoints,
            
            "debugger": self.debugger,
            "dbg": self.debugger,
        }
    
    def run(self):
        shell = InteractiveShellEmbed(colors='linux',user_ns=self._get_aliases())
        shell.prompts = ConsolePrompt(shell)
        shell.run_line_magic("autocall", "2") # enable autocall, so that we don't have to type parentheses for function calls
        shell()