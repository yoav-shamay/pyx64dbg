"""
This module contains the functions for printing styled disassembly in the interactive console.
"""
from __future__ import annotations
import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_REG, X86_OP_MEM, X86_REG_RIP, X86Op
from typing import TYPE_CHECKING
from prompt_toolkit import print_formatted_text, HTML
from prompt_toolkit.styles import Style
import html

from pyx64dbg.number_types import CIntBase

if TYPE_CHECKING:
    from pyx64dbg.interactive_console.interactive_console import InteractiveConsole

# the color map for the disassembly output
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


def mem_operand_to_str(console: InteractiveConsole, instruction: capstone.CsInsn, op: X86Op) -> str:
    """
    Converts an x86 memory operand into a formatted HTML string.
    Structure: segment:[base + index * scale + disp]
    Will attempt to resolve symbols and show RIP-relative addresses in a user-friendly way.
    """
    # Contains the various parts of the memory operand
    parts: list[str] = []

    # Segment (e.g., fs:)
    segment_prefix = ""
    if op.mem.segment != 0:
        reg_name = instruction.reg_name(op.mem.segment)
        segment_prefix = f"<reg>{reg_name}</reg><punct>:</punct>"

    # Base Register
    if op.mem.base != 0:
        parts.append(f"<reg>{instruction.reg_name(op.mem.base)}</reg>")

    # Index Register * Scale
    if op.mem.index != 0:
        if parts:
            parts.append("<punct>+</punct>")

        index_reg = instruction.reg_name(op.mem.index)
        parts.append(f"<reg>{index_reg}</reg>")

        if op.mem.scale != 1:
            # Scale is the multiplier (number), * is the operator
            parts.append(f"<punct>*</punct><imm>{op.mem.scale}</imm>")

    # Displacement (constant offset from register / absolute address) - including symbol resolution
    if op.mem.disp != 0:
        # If there are already registers, we need a sign
        if parts:
            if op.mem.disp > 0:
                parts.append("<punct>+</punct>")
            else:
                parts.append("<punct>-</punct>")

        # if there's a previous part we already added +/- so we need to show the absolute value.
        val_to_show = abs(op.mem.disp) if parts else op.mem.disp
        # Determine if the displacement is a known symbol when there's no base/index
        if op.mem.base == 0 and op.mem.index == 0:
            symbol = console.debugger.address_to_symbol.get(op.mem.disp)
            if symbol:
                parts.append(f"<sym>{html.escape(symbol)}</sym>") # need to escape the symbol name as it can contain special chars
            else:
                parts.append(f"<imm>{hex(val_to_show)}</imm>")
        else:
            parts.append(f"<imm>{hex(val_to_show)}</imm>")

    # combine the parts together with the segment prefix and memory brackets
    inner = "".join(parts)

    # show with the segment prefix and memory brackets
    res = f"{segment_prefix}<mem>[</mem>{inner}<mem>]</mem>"

    # for RIP-relative addressing, show the actual address and potentially resolve it to a symbol
    if op.mem.base == X86_REG_RIP and op.mem.index == 0:
        rip_relative_address = instruction.address + instruction.size + op.mem.disp
        # potentially resolve this RIP-relative address for a symbol
        symbol = console.debugger.address_to_symbol.get(rip_relative_address)
        if symbol:
            # if there's a symbol, show as (symbol, 0xaddress)
            res += (
                f" <punct>(</punct>"
                f"<sym>{html.escape(symbol)}</sym>"
                f"<punct>,</punct> "
                f"<addr>{hex(rip_relative_address)}</addr>"
                f"<punct>)</punct>"
            )
        else:
            # otherwise show just as (0xaddress)
            res += f" <addr>({hex(rip_relative_address)})</addr>"
    return res


def print_disassembly(console: InteractiveConsole, address: int | CIntBase, instruction_cnt: int) -> None:
    """
    Prints the disassembly of the instructions at the given address.
    Disassembles instruction_cnt instructions.
    """
    instructions = console.debugger.memory.read_instruction(address, instruction_cnt)

    # get RIP to highlight the current instruction
    current_rip = console.debugger.registers.rip

    for insn in instructions:
        is_current = insn.address == current_rip

        # Address and Mnemonic
        addr_html = f"<addr>0x{insn.address:012x}</addr>"
        mnem_html = f"<mnemonic>{insn.mnemonic:<8}</mnemonic>"

        # Process Operands
        operands_html = []
        for op in insn.operands:
            if op.type == X86_OP_IMM:
                # Immediate value (e.g., call 0x401000) - try to resolve symbol, otherwise just show 0xaddress
                sym = console.debugger.address_to_symbol.get(op.imm)
                if sym:
                    operands_html.append(
                        f"<sym>{sym}</sym> <addr>({hex(op.imm)})</addr>"
                    )
                else:
                    operands_html.append(f"<imm>{hex(op.imm)}</imm>")

            elif op.type == X86_OP_REG:
                # Pure Register (e.g., mov rax, rbx) - show register name
                operands_html.append(f"<reg>{insn.reg_name(op.reg)}</reg>")

            elif op.type == X86_OP_MEM:
                # Memory Reference (e.g., [rax + rdi*4]) - use helper method
                operands_html.append(mem_operand_to_str(console, insn, op))

        # Assemble the line by joining every operand
        ops_str = "<punct>, </punct>".join(operands_html)
        # show > before the instruction if it's the current one
        prefix = "<b>&gt; </b>" if is_current else "  "
        # combine all parts together
        line_html = f"{prefix}{addr_html}  {mnem_html} {ops_str}"

        # Apply current line background if applicable
        if is_current:
            line_html = f"<current>{line_html}</current>"

        # print using prompt_toolkit with the defined style
        print_formatted_text(HTML(line_html), style=disasm_style, output=console._toolkit_output)
