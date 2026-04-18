from capstone.x86 import *
from prompt_toolkit import print_formatted_text, HTML
from prompt_toolkit.styles import Style

disasm_style = Style.from_dict(
    {
        "addr": "#888888",  # hex addresses - Grey
        "mnemonic": "#ffcc00",  # instruction name - Yellow/Gold
        "reg": "#ffffff",  # register names - White
        "imm": "#ff33ff",  # immediate values - Magenta
        "sym": "#00ff00 bold",  # symbols - Bright Green
        "mem": "#00ffff",  # memory operand brackets - Cyan
        "punct": "#888888",  # punctuation - Grey
        "current": "bg:#555522",  # Background highlight for current RIP
    }
)


def _mem_operand_to_str(self, instruction, op):
    """
    Converts an x86 memory operand into a formatted HTML string.
    Structure: segment:[base + index * scale + disp]
    Will attempt to resolve symbols and show RIP-relative addresses in a user-friendly way.
    """
    parts = []

    # 1. Segment (e.g., fs:)
    segment_prefix = ""
    if op.mem.segment != 0:
        reg_name = instruction.reg_name(op.mem.segment)
        segment_prefix = f"<reg>{reg_name}</reg><punct>:</punct>"

    # 2. Base Register
    if op.mem.base != 0:
        parts.append(f"<reg>{instruction.reg_name(op.mem.base)}</reg>")

    # 3. Index Register * Scale
    if op.mem.index != 0:
        if parts:
            parts.append("<punct>+</punct>")

        index_reg = instruction.reg_name(op.mem.index)
        parts.append(f"<reg>{index_reg}</reg>")

        if op.mem.scale != 1:
            # Scale is the multiplier (number), * is the operator
            parts.append(f"<punct>*</punct><imm>{op.mem.scale}</imm>")

    # 4. Displacement / Displacement Symbol
    if op.mem.disp != 0:
        # If there are already registers, we need a sign
        if parts:
            if op.mem.disp > 0:
                parts.append("<punct>+</punct>")
            else:
                parts.append("<punct>-</punct>")

        # Determine if the displacement is a known symbol when there's no base/index
        val_to_show = abs(op.mem.disp) if parts else op.mem.disp
        if op.mem.base == 0 and op.mem.index == 0:
            symbol = self.debugger.address_to_symbol.get(op.mem.disp)
            if symbol:
                parts.append(f"<sym>{symbol}</sym>")
            else:
                parts.append(f"<imm>{hex(val_to_show)}</imm>")
        else:
            parts.append(f"<imm>{hex(val_to_show)}</imm>")


    inner = "".join(parts)

    res = f"{segment_prefix}<mem>[</mem>{inner}<mem>]</mem>"

    # for RIP-relative addressing, show the actual address and potentially resolve it to a symbol
    if op.mem.base == X86_REG_RIP and op.mem.index == 0:
        rip_relative_address = instruction.address + instruction.size + op.mem.disp
        symbol = self.debugger.address_to_symbol.get(rip_relative_address)
        if symbol:
            res += (
                f" <punct>(</punct>"
                f"<sym>{symbol}</sym>"
                f"<punct>,</punct> "
                f"<addr>{hex(rip_relative_address)}</addr>"
                f"<punct>)</punct>"
            )
        else:
            res += f" <addr>({hex(rip_relative_address)})</addr>"
    return res


def print_disassembly(self, address: int, instruction_cnt: int) -> None:
    """
    Prints the disassembly of the instructions at the given address.
    Disassembles instruction_cnt instructions.
    """
    instructions = self.debugger.read_instruction(address, instruction_cnt)

    # get RIP to highlight the current instruction
    current_rip = self.debugger.registers.rip

    for insn in instructions:
        is_current = insn.address == current_rip

        # 1. Address and Mnemonic
        addr_html = f"<addr>0x{insn.address:012x}</addr>"
        mnem_html = f"<mnemonic>{insn.mnemonic:<8}</mnemonic>"

        # 2. Process Operands
        operands_html = []
        for op in insn.operands:
            if op.type == X86_OP_IMM:
                # Immediate value (e.g., call 0x401000)
                sym = self.debugger.address_to_symbol.get(op.imm)
                if sym:
                    operands_html.append(
                        f"<sym>{sym}</sym> <addr>({hex(op.imm)})</addr>"
                    )
                else:
                    operands_html.append(f"<imm>{hex(op.imm)}</imm>")

            elif op.type == X86_OP_REG:
                # Pure Register (e.g., mov rax, rbx)
                operands_html.append(f"<reg>{insn.reg_name(op.reg)}</reg>")

            elif op.type == X86_OP_MEM:
                # Memory Reference (e.g., [rax + rdi*4])
                operands_html.append(self._mem_operand_to_str(insn, op))

        # 3. Assemble the line
        ops_str = "<punct>, </punct>".join(operands_html)
        prefix = "<b>&gt; </b>" if is_current else "  "
        line_html = f"{prefix}{addr_html}  {mnem_html} {ops_str}"

        # 4. Apply current line background if applicable
        if is_current:
            line_html = f"<current>{line_html}</current>"

        print_formatted_text(HTML(line_html), style=disasm_style)
