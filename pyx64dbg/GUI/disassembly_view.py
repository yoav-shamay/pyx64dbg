from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QMenu, QMessageBox, QTableWidgetItem, QWidget, QVBoxLayout, QTableWidget, 
    QLabel, QAbstractItemView, QHeaderView, QInputDialog
)
from PySide6.QtCore import Qt

import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_REG, X86_OP_MEM, X86_REG_RIP

from pyx64dbg.GUI.debugger_state import DebuggerState
from pyx64dbg.number_types import Int64

from async_slot import async_slot

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

# amount of instructions to show when disassembling from an address (either RIP or specific address)
SPECIFIC_ADDRESS_INSTRUCTION_COUNT = 50

# Internal Palette for HTML Spans (Matches your original THEME)
COLORS = {
    "addr": "#666666",
    "mnem": "#0000D0",
    "reg": "#A00000",
    "imm": "#006600",
    "sym": "#660099",
    "punct": "#888888",
}

class DisassemblyView(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._debugger_worker = main_window.debugger_worker
        self._address_to_symbol = {}
        self._rip = 0
        self._debugger_state = None
        
        self.cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.cs.detail = True
        # disassembly mode - from RIP, address range (usually a symbol), or specific address (default count)
        self._disassemble_from_rip = None
        self._disassemble_range = None # tuple of (start, end) addresses to disassemble. end isn't inclusive.
        self._disassemble_address = None

        self._init_ui()
        self._init_callbacks()
        self._load_qss()

    def _load_qss(self):
        """
        Load the style qss file
        """
        with open("pyx64dbg/GUI/styles/disassembly.qss", "r") as f:
            self.setStyleSheet(f.read())

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # create the table for the disassembly with 4 columns
        self.table = QTableWidget(0, 4)

        # table behavior
        self.table.setShowGrid(False) # don't show grid
        self.table.verticalHeader().hide() # don't show row numbers
        self.table.horizontalHeader().hide() # don't show column names
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # selecting a cell highlights the entire row
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection) # only allow selecting one row at a time
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # don't allow editing cells

        # vertical header - controls the row height.
        v_header = self.table.verticalHeader()
        # make the rows 18px, which is a good height for making the instructions close
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        v_header.setDefaultSectionSize(18)

        # horizontal header - controls the column widths
        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed) # indicators column - should be fixed to a small width to fit the icons
        self.table.setColumnWidth(0, 50)
        h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # address column - should be just wide enough to fit the addresses
        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # mnemonic column - should be just wide enough to fit the mnemonics
        h_header.setStretchLastSection(True) # operands column - should take up the remaining space as it's the major part
        
        # Remove any internal margins
        self.table.setContentsMargins(0, 0, 0, 0)

        # register right click menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def _init_callbacks(self):
        self._debugger_worker.process_started.connect(self._on_process_run)
        self._debugger_worker.state_update.connect(self._on_state_update)


    def _create_cell_label(self, text, status_val, alignment=Qt.AlignmentFlag.AlignLeft):
        """
        Helper to create a styled label for any column
        """
        lbl = QLabel(text)
        lbl.setProperty("status", status_val)
        # Ensure the label fills the entire cell height/width
        lbl.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        # Add a tiny bit of padding so text isn't touching the line
        lbl.setContentsMargins(5, 0, 5, 0)
        return lbl

    def _load_disassembly(self, instructions: list[capstone.CsInsn]):
        self.table.setRowCount(len(instructions))

        for row, insn in enumerate(instructions):
            is_rip = (insn.address == self._rip)
            is_bp = (insn.address in self._debugger_state.breakpoints if self._debugger_state else False)

            # Determine "Status" property for QSS
            status = "normal"
            indicator = ""
            if is_rip and is_bp:
                status, indicator = "rip-bp", "▶🔴"
            elif is_rip:
                status, indicator = "rip", "▶"
            elif is_bp:
                status, indicator = "bp", "🔴"


            # 1. Indicator Column
            self.table.setCellWidget(row, 0, self._create_cell_label(indicator, status, Qt.AlignmentFlag.AlignCenter))

            # 2. Address Column.
            # have an item with the address number, to access programmatically (for context menu)
            addr_item = QTableWidgetItem()
            addr_item.setData(Qt.ItemDataRole.UserRole, insn.address)
            self.table.setItem(row, 1, addr_item)
            # the address text itself
            addr_str = f"0x{insn.address:012x}"
            # Wrap in a span to use the COLORS['addr'] color defined in your file
            addr_html = f"<span style='color:{COLORS['addr']};'>{addr_str}</span>"
            self.table.setCellWidget(row, 1, self._create_cell_label(addr_html, status))

            # 3. Mnemonic Column
            # Wrap in span for bold/color
            mnem_html = f"<span style='color:{COLORS['mnem']}; font-weight:bold;'>{insn.mnemonic}</span>"
            self.table.setCellWidget(row, 2, self._create_cell_label(mnem_html, status))

            # 4. Operands Column
            ops_html = self._format_operands_html(insn)
            self.table.setCellWidget(row, 3, self._create_cell_label(ops_html, status))

    def _format_operands_html(self, insn: capstone.CsInsn) -> str:
        # (Same logic as before, just generating spans for registers/immediates)
        # Using inline styles for tokens (colors) is still okay here 
        # because those represent data-types (registers vs symbols),
        # whereas row colors represent debugger-state.
        parts = []
        for op in insn.operands:
            if op.type == X86_OP_IMM:
                sym = self._address_to_symbol.get(op.imm)
                parts.append(f"<span style='color:#660099;'><b>{sym}</b></span>" if sym else f"<span style='color:#006600;'>{hex(op.imm)}</span>")
            elif op.type == X86_OP_REG:
                parts.append(f"<span style='color:#A00000;'>{insn.reg_name(op.reg)}</span>")
            elif op.type == X86_OP_MEM:
                parts.append(self._format_mem_html(insn, op))
        return ", ".join(parts)

    def _tag(self, text: str, color_key: str, bold: bool = False) -> str:
        color = COLORS.get(color_key, "#000000")
        style = f"color:{color};"
        if bold: style += "font-weight:bold;"
        return f"<span style='{style}'>{text}</span>"

    def _format_mem_html(self, insn, op):
        parts = []
        # Segment
        if op.mem.segment != 0:
            parts.append(f"{self._tag(insn.reg_name(op.mem.segment), 'reg')}{self._tag(':', 'punct')}")
        # Base
        if op.mem.base != 0:
            parts.append(self._tag(insn.reg_name(op.mem.base), 'reg'))
        # Index
        if op.mem.index != 0:
            if parts: parts.append(self._tag("+", "punct"))
            parts.append(self._tag(insn.reg_name(op.mem.index), 'reg'))
            if op.mem.scale != 1:
                parts.append(f"{self._tag('*', 'punct')}{self._tag(str(op.mem.scale), 'imm')}")
        # Displacement
        if op.mem.disp != 0:
            if parts:
                parts.append(self._tag("+" if op.mem.disp > 0 else "-", "punct"))
                val = abs(op.mem.disp)
            else:
                val = op.mem.disp
            
            # Symbol check for absolute displacements
            if op.mem.base == 0 and op.mem.index == 0:
                symbol = self._address_to_symbol.get(op.mem.disp)
                parts.append(self._tag(symbol, "sym", True) if symbol else self._tag(hex(val), "imm"))
            else:
                parts.append(self._tag(hex(val), "imm"))

        inner = "".join(parts)
        res = f"{self._tag('[', 'punct')}{inner}{self._tag(']', 'punct')}"

        # RIP-Relative Resolution
        if op.mem.base == X86_REG_RIP and op.mem.index == 0:
            rip_target = insn.address + insn.size + op.mem.disp
            symbol = self._address_to_symbol.get(rip_target)
            res += f" {self._tag('(', 'punct')}"
            if symbol:
                res += f"{self._tag(symbol, 'sym', True)}{self._tag(',', 'punct')} "
            res += f"{self._tag(hex(rip_target), 'addr')}{self._tag(')', 'punct')}"
            
        return res

    @async_slot
    async def _on_process_run(self):
        self._address_to_symbol = await self._debugger_worker.call_async(self._debugger_worker.get_address_to_symbol_mapping)
        # by default - disassemble from RIP
        await self._make_disassemble_from_rip()

    @async_slot
    async def _on_state_update(self, debugger_state: DebuggerState):
        self._debugger_state = debugger_state
        self._rip = Int64.from_bytes(debugger_state.standard_regs["rip"])
        await self._refresh_view()

    async def _refresh_view(self):
        instructions = None
        if self._disassemble_from_rip:
            instructions = await self._debugger_worker.call_async(self._debugger_worker.read_instructions, self._rip, SPECIFIC_ADDRESS_INSTRUCTION_COUNT)
        elif self._disassemble_range:
            code = await self._debugger_worker.call_async(self._debugger_worker.read_memory, self._disassemble_range[0], self._disassemble_range[1])
            instructions = list(self.cs.disasm(code, self._disassemble_range[0]))
        elif self._disassemble_address:
            instructions = await self._debugger_worker.call_async(self._debugger_worker.read_instructions, self._disassemble_address, SPECIFIC_ADDRESS_INSTRUCTION_COUNT)
        if instructions: # instructions might be None if there was some error (like debugger not fully initialized). in this case, just don't update the view.
            self._load_disassembly(instructions)

    # Disassembly Option Setters
    async def _make_disassemble_from_rip(self):
        self._disassemble_from_rip = True
        self._disassemble_range = None
        self._disassemble_address = None
        if self._debugger_state: await self._refresh_view()

    async def make_disassemble_memory_range(self, start: int, end: int):
        self._disassemble_from_rip = False
        self._disassemble_range = (start, end)
        self._disassemble_address = None
        if self._debugger_state: await self._refresh_view()

    async def _make_disassemble_from_address(self, address: int):
        self._disassemble_from_rip = False
        self._disassemble_range = None
        self._disassemble_address = address
        if self._debugger_state: await self._refresh_view()

    def _show_context_menu(self, position):
        """
        Builds and displays the right-click menu.
        Available options:
        1. Add/Remove Breakpoint (if clicked on an instruction)
        2. Set RIP to Selected Line (if clicked on an instruction)
        3. Change disassembly mode to follow RIP
        4. Go to address... (prompts for an address to disassemble from)
        """
        # Get the row we clicked on (which indicates the instruction)
        row = self.table.rowAt(position.y())

        menu = QMenu(self)
        
        # If we selected an instruction
        if row != -1:
            # get the address associated with this instruction from the hidden data role
            addr_item = self.table.item(row, 1) # we stored the address in column 1, which is the address column
            if addr_item is not None:
                addr = addr_item.data(Qt.ItemDataRole.UserRole)
                # Add/Remove Breakpoint
                is_bp = addr in self._debugger_state.breakpoints
                bp_label = "Remove Breakpoint" if is_bp else "Add Breakpoint"
                act_bp = menu.addAction(bp_label)
                act_bp.triggered.connect(lambda: self._toggle_breakpoint(addr))
                if self._main_window.debugger_busy:
                    act_bp.setEnabled(False) # don't allow actions while the debugger is busy

                # Set RIP to Selected Line
                act_rip = menu.addAction("Set RIP to here")
                act_rip.triggered.connect(lambda: self._set_rip(addr))
                if self._main_window.debugger_busy:
                    act_rip.setEnabled(False) # don't allow actions while the debugger is busy
                # add a separator to distinguish the instruction-specific options from the more general options
                menu.addSeparator()

        # Change disassembly to RIP
        act_reset_rip = menu.addAction("Go to current RIP")
        act_reset_rip.triggered.connect(async_slot(self._make_disassemble_from_rip)) # wrap in async_slot as this function is async but doesn't have the decorator as it's called internally
        if self._main_window.debugger_busy:
            act_reset_rip.setEnabled(False) # don't allow actions while the debugger is busy
        # Choose a location (Prompt)
        act_goto = menu.addAction("Go to address...")
        act_goto.triggered.connect(self._prompt_for_address)
        if self._main_window.debugger_busy:
            act_goto.setEnabled(False) # don't allow actions while the debugger is busy
        # show the menu at the cursor position
        menu.exec(self.table.viewport().mapToGlobal(position))

    @async_slot
    async def _prompt_for_address(self):
        """
        Opens a dialog to jump to a specific address.
        """
        text, ok = QInputDialog.getText(self, "Disassemble At", "Address:")
        if ok and text:
            try:
                # evaluate the expression
                address = await self._debugger_worker.call_async(self._debugger_worker.evaluate_expression, text)
                await self._make_disassemble_from_address(address)
            except Exception as e:
                # show an error dialog if the expression couldn't be evaluated
                error_dialog = QMessageBox(self)
                error_dialog.setIcon(QMessageBox.Icon.Critical)
                error_dialog.setWindowTitle("Error")
                # show the exception type and message in the error dialog
                error_dialog.setText(f"<b>{e.__class__.__name__}</b>: {str(e)}")
                error_dialog.exec()

    @async_slot
    async def _toggle_breakpoint(self, address: int):
        """
        Toggle a breakpoint on the given address.
        """
        if address in self._debugger_state.breakpoints:
            await self._debugger_worker.call_async(self._debugger_worker.remove_breakpoint, address)
        else:
            await self._debugger_worker.call_async(self._debugger_worker.add_breakpoint, address)

    @async_slot
    async def _set_rip(self, address: int):
        """
        Sets the instruction pointer (RIP) to the given address.
        """
        await self._debugger_worker.call_async(self._debugger_worker.set_register, "rip", address)
