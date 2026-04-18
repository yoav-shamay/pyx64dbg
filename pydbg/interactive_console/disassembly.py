from capstone.x86 import *

def mem_operand_to_str(instruction, op):
    mem_str = ""
    if op.mem.segment != 0:
        mem_str += instruction.reg_name(op.mem.segment) + ":"
    mem_str += "["
    if op.mem.base != 0:
        mem_str += instruction.reg_name(op.mem.base)
    if op.mem.index != 0:
        if op.mem.base != 0 and op.mem.index >= 0:
            mem_str += "+"
        mem_str += instruction.reg_name(op.mem.index)
        if op.mem.scale != 1:
            mem_str += f"*{op.mem.scale}"
    if op.mem.disp != 0:
        if (op.mem.base != 0 or op.mem.index != 0) and op.mem.disp >= 0:
            mem_str += "+"
        mem_str += hex(op.mem.disp)
    mem_str += "]"
    return mem_str
def print_disassembly(self, address : int, instruction_cnt : int) -> None:
        """
        Prints the disassembly of the instructions at the given address.
        Disassembles instruction_cnt instructions.
        """
        instructions = self.debugger.read_instruction(address, instruction_cnt)
        for instruction in instructions:
            instruction_line = f"0x{instruction.address:016x}: {instruction.mnemonic:<8} "
            operands = []
            for op in instruction.operands:
                if op.type == X86_OP_IMM:
                    address = op.imm
                    if address in self.debugger.address_to_symbol:
                        symbol = self.debugger.address_to_symbol[address]
                        operands.append(f"{symbol} ({hex(address)})")
                    else:
                        operands.append(hex(address))
                elif op.type == X86_OP_REG:
                    operands.append(instruction.reg_name(op.reg))
                elif op.type == X86_OP_MEM:
                    mem_str = mem_operand_to_str(instruction, op)
                    operands.append(mem_str)
                else:
                    operands.append("?")
            instruction_line += ", ".join(operands)
            print(instruction_line)