from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QMenu, QMessageBox, QTableWidgetItem, QWidget, QVBoxLayout, QTableWidget, 
    QLabel, QAbstractItemView, QHeaderView, QInputDialog
)
from PySide6.QtCore import Qt, QPoint

import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_REG, X86_OP_MEM, X86_REG_RIP, X86Op

from pyx64dbg.GUI.debugger_state import DebuggerState
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.utils import prompt_for_expression
from pyx64dbg.number_types import Int64, UInt64

from pyx64dbg.GUI.async_slot import async_slot

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
    """
    This class defines the disassembly view widget in the GUI.
    Displays the disassembled instructions of the debugged process.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._address_to_symbol: dict[UInt64, str] = {}
        self._rip: UInt64 = UInt64(0)
        self._debugger_state: DebuggerState | None = None
        
        self._cs: capstone.Cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self._cs.detail = True
        # disassembly mode - from RIP, address range (usually a symbol), or specific address (default count)
        self._disassemble_from_rip: bool = False
        self._disassemble_range: tuple[UInt64, UInt64] | None = None # tuple of (start, end) addresses to disassemble. end isn't inclusive.
        self._disassemble_address: UInt64 | None = None

        self._init_ui()
        self._register_callbacks()
        self._load_qss()

    def _load_qss(self) -> None:
        """
        Load the style qss file.
        """
        with open("pyx64dbg/GUI/styles/disassembly_view.qss", "r") as f:
            self.setStyleSheet(f.read())

    def _init_ui(self) -> None:
        """
        Inits the UI, creating the table and setting its properties.
        """
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

    def _register_callbacks(self) -> None:
        """
        Registers the callbacks to update the view on various process events.
        """
        self._debugger_worker.process_started.connect(self._on_process_run)
        self._debugger_worker.state_update.connect(self._on_state_update)
        self._debugger_worker.file_selected.connect(self._on_file_selected)


    def _create_cell_label(self, text: str, status_val: str, alignment: Qt.AlignmentFlag=Qt.AlignmentFlag.AlignLeft) -> QLabel:
        """
        Helper to create a styled label for any column.
        Gets the text, the status value for the row (for QSS styling) and the alignment for the cell.
        """
        lbl = QLabel(text)
        # set the "status" property which will be used in styling
        lbl.setProperty("status", status_val)
        # Set the alignment of the label, ensuring it's vertically cenetred in addition to the provided alignment
        lbl.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        # Add a tiny bit of padding so text isn't touching the line
        lbl.setContentsMargins(5, 0, 5, 0)
        return lbl

    def _load_disassembly(self, instructions: list[capstone.CsInsn]):
        """
        Loads a specified list of instructions into the table.
        """
        # set the table row count to match the number of instructions we want to display
        self.table.setRowCount(len(instructions))
        # add each instruction to the table
        for row, insn in enumerate(instructions):
            # Determine indicators - if it's the current instruction and if it's a breakpoint
            is_rip = (insn.address == self._rip)
            is_bp = (insn.address in self._debugger_state.breakpoints if self._debugger_state else False)

            # Determine "Status" property for QSS, and indicator column
            status = "normal"
            indicator = ""
            if is_rip and is_bp:
                status, indicator = "rip-bp", "▶🔴"
            elif is_rip:
                status, indicator = "rip", "▶"
            elif is_bp:
                status, indicator = "bp", "🔴"


            # Indicator Column
            self.table.setCellWidget(row, 0, self._create_cell_label(indicator, status, Qt.AlignmentFlag.AlignCenter))

            # Address Column.
            # have an item with the address number, to access programmatically (for context menu)
            addr_item = QTableWidgetItem()
            addr_item.setData(Qt.ItemDataRole.UserRole, insn.address)
            self.table.setItem(row, 1, addr_item)
            # the address text itself
            addr_str = f"0x{insn.address:012x}"
            # Wrap in a span to use the COLORS['addr'] color defined in your file
            addr_html = f"<span style='color:{COLORS['addr']};'>{addr_str}</span>"
            self.table.setCellWidget(row, 1, self._create_cell_label(addr_html, status))

            # Mnemonic Column
            # Wrap in span for bold/color
            mnem_html = f"<span style='color:{COLORS['mnem']}; font-weight:bold;'>{insn.mnemonic}</span>"
            self.table.setCellWidget(row, 2, self._create_cell_label(mnem_html, status))

            # Operands Column
            ops_html = self._format_operands_html(insn)
            self.table.setCellWidget(row, 3, self._create_cell_label(ops_html, status))

    def _format_operands_html(self, insn: capstone.CsInsn) -> str:
        """
        Formats the operand part of an instruction to label text (with HTML).
        Returns the formatted HTML string for the operands.
        """
        parts: list[str] = []
        for op in insn.operands:
            if op.type == X86_OP_IMM:
                # immediate operand - try to resolve to a symbol
                sym = self._address_to_symbol.get(op.imm)
                if sym:
                    parts.append(f"<span style='color:{COLORS['sym']};'><b>{sym}</b></span>")
                else:
                    parts.append(f"<span style='color:{COLORS['imm']};'>{hex(op.imm)}</span>")
            elif op.type == X86_OP_REG:
                # register operand - just show the register name
                parts.append(f"<span style='color:{COLORS['reg']};'>{insn.reg_name(op.reg)}</span>")
            elif op.type == X86_OP_MEM:
                # mem operand - use the helper function
                parts.append(self._format_mem_html(insn, op))
        # return the parts joined with a comma
        return ", ".join(parts)

    def _tag(self, text: str, color_key: str, bold: bool = False) -> str:
        """
        Puts the text in a span with the color from COLORS based on the color_key, and bold if specified.
        Returns the formatted HTML string for the text.
        """
        color = COLORS.get(color_key, "#000000")
        style = f"color:{color};"
        if bold: style += "font-weight:bold;"
        return f"<span style='{style}'>{text}</span>"

    def _format_mem_html(self, insn: capstone.CsInsn, op: X86Op) -> str:
        """
        Formats a memory operand into an HTML string, resolving symbols where possible.
        Returns the formatted HTML string for the memory operand.
        """
        parts: list[str] = []
        segment_part = ""
        # Segment register
        if op.mem.segment != 0:
            segment_part = f"{self._tag(insn.reg_name(op.mem.segment), 'reg')}{self._tag(':', 'punct')}"
        # Base register
        if op.mem.base != 0:
            parts.append(self._tag(insn.reg_name(op.mem.base), 'reg'))
        # Index register, including scale
        if op.mem.index != 0:
            if parts: parts.append(self._tag("+", "punct"))
            parts.append(self._tag(insn.reg_name(op.mem.index), 'reg'))
            if op.mem.scale != 1:
                parts.append(f"{self._tag('*', 'punct')}{self._tag(str(op.mem.scale), 'imm')}")
        # Displacement - including symbol resolution for absolute addresses (disp with no base or index)
        if op.mem.disp != 0:
            if len(parts) > 0:
                parts.append(self._tag("+" if op.mem.disp > 0 else "-", "punct"))
                val = abs(op.mem.disp)
            else:
                val = op.mem.disp
            
            # Symbol check for absolute displacements
            if op.mem.base == 0 and op.mem.index == 0: # absolute address
                symbol = self._address_to_symbol.get(op.mem.disp)
                if symbol:
                    parts.append(self._tag(symbol, "sym", True))
                else:
                    parts.append(self._tag(hex(val), "imm"))
            else:
                parts.append(self._tag(hex(val), "imm"))
        
        # join the parts together, and use format segment:[parts] if there's a segment
        inner = "".join(parts)
        res = f"{segment_part}{self._tag('[', 'punct')}{inner}{self._tag(']', 'punct')}"

        # RIP-Relative Resolution (parenthesis after the instruction)
        if op.mem.base == X86_REG_RIP and op.mem.index == 0: # [RIP+disp] addressing
            rip_target = insn.address + insn.size + op.mem.disp
            symbol = self._address_to_symbol.get(rip_target) # try to resolve symbol
            res += f" {self._tag('(', 'punct')}"
            if symbol:
                # if symbol, format as symbol, address
                res += f"{self._tag(symbol, 'sym', True)}{self._tag(',', 'punct')} "
            # without symbol, just show the address
            res += f"{self._tag(hex(rip_target), 'addr')}{self._tag(')', 'punct')}"
            
        return res

    @async_slot
    async def _on_process_run(self) -> None:
        """
        Callback for when the process starts running.
        Fetches the address to symbol mapping and starts disassembling from RIP.
        """
        self._address_to_symbol = await self._debugger_worker.call_async(self._debugger_worker.get_address_to_symbol_mapping)
        # by default - disassemble from RIP
        await self.make_disassemble_from_rip()

    @async_slot
    async def _on_state_update(self, debugger_state: DebuggerState) -> None:
        """
        Callback for when the debugger state updates (like after stepping or hitting a breakpoint).
        Updates the RIP and refreshes the view if we're in a mode that follows RIP.
        """
        self._debugger_state = debugger_state
        self._rip = Int64.from_bytes(debugger_state.standard_regs["rip"])
        await self._refresh_view()

    async def _refresh_view(self) -> None:
        """
        Function that refreshes the disassembly view after an update.
        Fetches the instructions based on the mode and loads them into the view.
        """
        if self._main_window.debugger_busy:
            return # if the debugger is busy, don't try to refresh as we can't call the thread
        try:
            instructions = None
            if self._disassemble_from_rip:
                # from RIP - read the instructions, take SPECIFIC_ADDRESS_INSTRUCTION_COUNT instructions from the current RIP address
                instructions = await self._debugger_worker.call_async(self._debugger_worker.read_instructions, self._rip, SPECIFIC_ADDRESS_INSTRUCTION_COUNT)
            elif self._disassemble_range:
                # range - read the memory for the range and dissasemble it here as the debugger doesn't have a method for disassembling a range
                code = await self._debugger_worker.call_async(self._debugger_worker.read_memory, self._disassemble_range[0], self._disassemble_range[1])
                instructions = list(self._cs.disasm(code, self._disassemble_range[0]))
            elif self._disassemble_address:
                # specific address - read SPECIFIC_ADDRESS_INSTRUCTION_COUNT instructions from the specific address (similar to from RIP)
                instructions = await self._debugger_worker.call_async(self._debugger_worker.read_instructions, self._disassemble_address, SPECIFIC_ADDRESS_INSTRUCTION_COUNT)
            self._load_disassembly(instructions)
        except:
            # There might be an error while reading memory (like invalid address). in this case we'll just not update the view.
            pass

    # Disassembly Option Setters
    async def make_disassemble_from_rip(self) -> None:
        """
        Method to change the dissasembly mode to follow RIP.
        """
        self._disassemble_from_rip = True
        self._disassemble_range = None
        self._disassemble_address = None
        if self._debugger_state: await self._refresh_view()

    async def make_disassemble_memory_range(self, start: int, end: int) -> None:
        """
        Method to change the disassembly mode to disassemble a memory range (usually a symbol).
        """
        self._disassemble_from_rip = False
        self._disassemble_range = (start, end)
        self._disassemble_address = None
        if self._debugger_state: await self._refresh_view()

    async def make_disassemble_from_address(self, address: int) -> None:
        """
        Method to change the disassembly mode to disassemble from a specific address.
        """
        self._disassemble_from_rip = False
        self._disassemble_range = None
        self._disassemble_address = address
        if self._debugger_state: await self._refresh_view()

    def _show_context_menu(self, position: QPoint) -> None:
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
        act_reset_rip.triggered.connect(async_slot(self.make_disassemble_from_rip)) # wrap in async_slot as this function is async but doesn't have the decorator as it's called internally
        if self._main_window.debugger_busy:
            act_reset_rip.setEnabled(False) # don't allow actions while the debugger is busy
        # Choose a location (Prompt)
        act_goto = menu.addAction("Go to address...")
        act_goto.triggered.connect(self._go_to_address_prompt)
        if self._main_window.debugger_busy:
            act_goto.setEnabled(False) # don't allow actions while the debugger is busy
        # show the menu at the cursor position
        menu.exec(self.table.viewport().mapToGlobal(position))

    @async_slot
    async def _go_to_address_prompt(self) -> None:
        """
        Opens a dialog to jump to a specific address.
        """
        address = await prompt_for_expression(self, "Disassemble At", "Address:", self._debugger_worker)
        if address is not None:
            await self.make_disassemble_from_address(address)

    @async_slot
    async def _toggle_breakpoint(self, address: int) -> None:
        """
        Toggle a breakpoint on the given address.
        """
        if address in self._debugger_state.breakpoints:
            await self._debugger_worker.call_async(self._debugger_worker.remove_breakpoint, address)
        else:
            await self._debugger_worker.call_async(self._debugger_worker.add_breakpoint, address)

    @async_slot
    async def _set_rip(self, address: int) -> None:
        """
        Sets the instruction pointer (RIP) to the given address.
        """
        await self._debugger_worker.call_async(self._debugger_worker.set_register, "rip", address)
    
    def _on_file_selected(self) -> None:
        """
        Callback for when a new file is selected in the debugger.
        Resets the disassembly view to follow RIP.
        As the process is not running yet, no actual visual update is needed, just internal state reset.
        """
        self._disassemble_from_rip = True
        self._disassemble_range = None
        self._disassemble_address = None
