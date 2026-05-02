from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser
from PyQt6.QtGui import QFont
from capstone.x86 import X86_OP_IMM, X86_OP_REG, X86_OP_MEM, X86_REG_RIP
from pyx64dbg.debugger import Debugger
from pyx64dbg.GUI.debugger_state import DebuggerState

import capstone

from pyx64dbg.number_types import Int64

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

# GUI Light Theme Palette
THEME = {
    "bg": "#FFFFFF",
    "text": "#000000",
    "addr": "#666666",          # Subtle dark grey
    "mnemonic": "#0000D0",      # Bold deep blue
    "reg": "#A00000",           # Dark red
    "imm": "#006600",           # Forest green
    "sym": "#660099",           # Purple
    "punct": "#888888",         # Light grey
    "rip_bg": "#FFF2CC",        # Light yellow background
    "bp_bg": "#FFE6E6",         # Light red background
    "bp_rip_bg": "#FFCC99",     # Orange/Peach if RIP is on a Breakpoint
}

def _span(text: str, color_key: str, bold: bool = False) -> str:
    """Wraps text in an HTML span with the theme color."""
    color = THEME.get(color_key, THEME["text"])
    html = f'<span style="color: {color};">{text}</span>'
    return f'<b>{html}</b>' if bold else html

# amount of instructions to show when disassembling from a specific address (like RIP)
SPECIFIC_ADDRESS_INSTRUCTION_COUNT = 50

class DisassemblyView(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._debugger_worker = main_window.debugger_worker
        self.cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.cs.detail = True
        self._init_callbacks()
        self._init_ui()

        self._debugger_state = None
        # disassembly options - from RIP, a specified memory range (usually a symbol), or from a specific address (with the default count)
        # by default - disassemble from RIP
        self._disassemble_from_rip = True
        self._disassemble_range = None
        self._disassemble_address = None
    
    def _init_callbacks(self) -> None:
        self._debugger_worker.process_started.connect(self._on_process_run)
        self._debugger_worker.state_update.connect(self._on_state_update)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # QTextBrowser is better than QTextEdit for read-only rich text
        self.text_browser = QTextBrowser()
        self.text_browser.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
        
        # Use a good GUI monospace font
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        self.text_browser.setFont(font)
        
        self.text_browser.setStyleSheet(f"background-color: {THEME['bg']}; color: {THEME['text']}; border: none;")
        
        layout.addWidget(self.text_browser)
    
    def _load_disassembly(self, instructions : list[capstone.CsInsn]) -> None:
        """
        Loads the given instructions into the view with syntax highlighting and indicators for RIP and breakpoints.
        """
        html = [
            '<table style="border-collapse: collapse; white-space: nowrap; font-family: Consolas, monospace;">'
        ]
        
        for insn in instructions:
            is_rip = (insn.address == self._rip)
            is_bp = (insn.address in self._debugger_state.breakpoints)
            
            # Determine row background and indicator icon
            row_bg = "transparent"
            indicator = "&nbsp;"
            
            if is_rip and is_bp:
                row_bg = THEME["bp_rip_bg"]
                indicator = "▶🔴"
            elif is_rip:
                row_bg = THEME["rip_bg"]
                indicator = "▶"
            elif is_bp:
                row_bg = THEME["bp_bg"]
                indicator = "🔴"

            # 1. Address & Mnemonic
            addr_html = _span(f"0x{insn.address:012x}", "addr")
            mnem_html = _span(f"{insn.mnemonic:<6}", "mnemonic", bold=True)
            
            # 2. Operands Syntax Highlighting
            operands_html = []
            for op in insn.operands:
                if op.type == X86_OP_IMM:
                    sym = self._address_to_symbol.get(op.imm)
                    if sym:
                        operands_html.append(f"{_span(sym, 'sym', bold=True)} {_span(f'({hex(op.imm)})', 'addr')}")
                    else:
                        operands_html.append(_span(hex(op.imm), "imm"))
                elif op.type == X86_OP_REG:
                    operands_html.append(_span(insn.reg_name(op.reg), "reg"))
                elif op.type == X86_OP_MEM:
                    operands_html.append(self._format_mem_operand(insn, op))
            
            ops_str = _span(", ", "punct").join(operands_html)
            
            # 3. Construct Table Row
            html.append(f'''
                <tr style="background-color: {row_bg};">
                    <td style="width: 30px; text-align: center;">{indicator}</td>
                    <td style="padding-right: 15px;">{addr_html}</td>
                    <td style="padding-right: 15px;">{mnem_html}</td>
                    <td>{ops_str}</td>
                </tr>
            ''')
            
        html.append('</table>')
        self.text_browser.setHtml("".join(html))
    
    def _disassemble_memory_range(self, start: int, end: int) -> list[capstone.CsInsn]:
        """
        Disassembles instructions in the given memory range.
        """
        code = self._debugger_worker.call_from_another_thread("read_memory", start, end - start, returning=True)
        return list(self.cs.disasm(code, start))
    
    def _format_mem_operand(self, instruction, op) -> str:
        """
        Formats the memory operand [base + index*scale + disp] with GUI colors.
        """
        parts = []
        
        if op.mem.segment != 0:
            parts.append(f"{_span(instruction.reg_name(op.mem.segment), 'reg')}{_span(':', 'punct')}")
            
        if op.mem.base != 0:
            parts.append(_span(instruction.reg_name(op.mem.base), "reg"))
            
        if op.mem.index != 0:
            if parts: parts.append(_span("+", "punct"))
            parts.append(_span(instruction.reg_name(op.mem.index), "reg"))
            if op.mem.scale != 1:
                parts.append(f"{_span('*', 'punct')}{_span(str(op.mem.scale), 'imm')}")
                
        if op.mem.disp != 0:
            if parts: parts.append(_span("+" if op.mem.disp > 0 else "-", "punct"))
            val = abs(op.mem.disp) if parts else op.mem.disp
            
            # Check for symbols (like global variables)
            if op.mem.base == 0 and op.mem.index == 0:
                symbol = self._address_to_symbol.get(op.mem.disp)
                parts.append(_span(symbol, "sym", bold=True) if symbol else _span(hex(val), "imm"))
            else:
                parts.append(_span(hex(val), "imm"))

        inner = "".join(parts)
        res = f"{_span('[', 'punct')}{inner}{_span(']', 'punct')}"

        # RIP-relative resolution
        if op.mem.base == X86_REG_RIP and op.mem.index == 0:
            rip_target = instruction.address + instruction.size + op.mem.disp
            symbol = self._address_to_symbol.get(rip_target)
            
            res += f" {_span('(', 'punct')}"
            if symbol:
                res += f"{_span(symbol, 'sym', bold=True)}{_span(',', 'punct')} "
            res += f"{_span(hex(rip_target), 'addr')}{_span(')', 'punct')}"

        return res
    
    def _on_process_run(self):
        """
        Called when the process starts running.
        Initiates the address to symbol mapping (as it's constant for a given execution).
        """
        self._address_to_symbol = self._debugger_worker.call_from_another_thread("get_address_to_symbol_mapping", returning=True)
    
    def _refresh_view(self):
        if self._disassemble_from_rip:
            instructions = self._debugger_worker.call_from_another_thread("read_instructions", self._rip, SPECIFIC_ADDRESS_INSTRUCTION_COUNT, returning=True)
        elif self._disassemble_range is not None:
            instructions = self._disassemble_memory_range(self._disassemble_range[0], self._disassemble_range[1])
        elif self._disassemble_address is not None:
            instructions = self._debugger_worker.call_from_another_thread("read_instructions", self._disassemble_address, SPECIFIC_ADDRESS_INSTRUCTION_COUNT, returning=True)
        self._load_disassembly(instructions)
    
    def _on_state_update(self, debugger_state: DebuggerState) -> None:  
        self._debugger_state = debugger_state
        self._rip = Int64.from_bytes(debugger_state.standard_regs["rip"]) # compute rip as an int64 for use later
        self._refresh_view()
    
    def disassemble_from_rip(self):
        """
        Sets the view to disassemble from RIP on the next state update.
        """
        self._disassemble_from_rip = True
        self._disassemble_range = None
        self._disassemble_address = None
        self._refresh_view()
    
    def disassemble_memory_range(self, start: int, end: int):
        """
        Sets the view to disassemble from the given memory range on the next state update.
        """
        self._disassemble_from_rip = False
        self._disassemble_range = (start, end)
        self._disassemble_address = None
        self._refresh_view()
    
    def disassemble_from_address(self, address: int):
        """
        Sets the view to disassemble from the given address on the next state update.
        """
        self._disassemble_from_rip = False
        self._disassemble_range = None
        self._disassemble_address = address
        self._refresh_view()