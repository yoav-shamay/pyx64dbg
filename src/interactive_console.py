from IPython import embed
import number_types

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

    def _get_aliases(self):
        """
        Define aliases for commonly used functions and attributes to make them easier to access in the interactive console.
        """
        return {
            "single_step": self.debugger.single_step,
            "step": self.debugger.single_step,

            "continue_execution": self.debugger.continue_execution,
            "cont": self.debugger.continue_execution,

            "next": self.debugger.next,
            "finish": self.debugger.finish,

            "registers": self.debugger.registers,
            "regs": self.debugger.registers,

            "memory": self.debugger.memory,
            "mem": self.debugger.memory,

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
            "remove_breakpoint": self.debugger.breakpoints.remove_breakpoint,
            "breakpoints": self.debugger.breakpoints.get_breakpoints,
            "brks": self.debugger.breakpoints.get_breakpoints,
            "get_breakpoints": self.debugger.breakpoints.get_breakpoints,
        }
    
    def run(self):
        embed(colors='linux', user_ns=self._get_aliases())