from __future__ import annotations
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from pyx64dbg.GUI.debugger_state import DebuggerState
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.utils import prompt_for_expression
from pyx64dbg.vector_register import VectorRegister
from pyx64dbg.GUI.async_slot import async_slot

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

# structure: a dict where keys are group names (e.g. "FPU", "xmm"), and values are names in debugger
TREE_STRUCTURE = {
    "FPU": {
        "control": ["fcw", "fsw", "ftw", "fop", "fip", "fdp"],
        "st": [f"st{i}" for i in range(8)],
    },
    "mm": [f"mm{i}" for i in range(8)],
    "mxcsr": ["mxcsr", "mxcsr_mask"],
    "xmm": [f"xmm{i}" for i in range(16)],
    "ymm": [f"ymm{i}" for i in range(16)]
}

REGISTER_LIST = []
# create a flat list of all registers from the structure for easy access when getting register values
def add_to_register_list(structure: dict):
    """
    Recursive method to extract a flat list of register names from the nested TREE_STRUCTURE.
    """
    for value in structure.values():
        if isinstance(value, dict):
            add_to_register_list(value)
        else:
            REGISTER_LIST.extend(value)

add_to_register_list(TREE_STRUCTURE)

ALL_SINGLE_PATHS = ["sf32", "sf64"] # all single value paths for vector registers
ALL_ARRAY_PATHS = ["i8", "i16", "i32", "i64", "f32", "f64", "u8", "u16", "u32", "u64"] # all array paths for vector registers

# create roles to store register name and lane name and index for easy assignment when double clicking
ROLE_REG_NAME = Qt.ItemDataRole.UserRole
ROLE_LANE_NAME = Qt.ItemDataRole.UserRole + 1
ROLE_LANE_INDEX = Qt.ItemDataRole.UserRole + 2
ROLE_IS_VALID = Qt.ItemDataRole.UserRole + 3 # whether it's N/A or valid to edit

class ExtendedRegistersView(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._register_nodes = {}
        self._vector_nodes = {}

        self._init_ui()
        self._register_callbacks()
    
    def _register_callbacks(self):
        self._debugger_worker.state_update.connect(self._on_state_update)

    def _init_ui(self):
        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2) # one column for register names, one for values
        self._tree.setAlternatingRowColors(True) # alternating row colors makes it easier to read
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # select entire rows when clicking a cell
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # make the first column (register name) fit contents, and the second column (value) take the remaining space
        self._tree.setHeaderHidden(True) # hide column headers
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked) # allow editing register values by double clicking a cell
        self._create_register_tree(TREE_STRUCTURE, self._tree.invisibleRootItem()) # init the tree with the register names, we'll fill in the values later
        # add the tree to the widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    def _create_reg_item(self, reg_item: QTreeWidgetItem, reg_path: str):
        reg_item.setText(1, "N/A") # default value until we fill it in
        reg_item.setData(0, ROLE_REG_NAME, reg_path)
        reg_item.setData(0, ROLE_IS_VALID, False) # N/A means invalid
        self._register_nodes[reg_path] = reg_item # save the item in self._register_nodes for access later

    def _create_register_tree(self, structure: dict, parent_item: QTreeWidgetItem):
        if isinstance(structure, list):
            # if it's a list, iterate over all children and add them to the parent
            for reg_name in structure:
                reg_item = QTreeWidgetItem(parent_item, [reg_name])
                self._create_reg_item(reg_item, reg_name)
        else:
            # otherwise, recursively create each subgroup
            for group_name, group_content in structure.items():
                group_item = QTreeWidgetItem(parent_item, [group_name])
                self._create_register_tree(group_content, group_item)

    def _create_array_in_vector_view(self, array_item: QTreeWidgetItem, arr: list[Any], reg_name: str, path_name: str):
        self._vector_nodes[reg_name][path_name] = []
        for i, val in enumerate(arr):
            lane_item = QTreeWidgetItem(array_item, [f"[{i}]"])
            lane_item.setText(1, str(val))
            lane_item.setData(0, ROLE_REG_NAME, reg_name)
            lane_item.setData(0, ROLE_LANE_NAME, path_name)
            lane_item.setData(0, ROLE_LANE_INDEX, i)
            lane_item.setData(0, ROLE_IS_VALID, True) # valid as isn't N/A
            self._vector_nodes[reg_name][path_name].append(lane_item)
    
    def _create_vector_view(self, reg_item: QTreeWidgetItem, vector_reg: VectorRegister, reg_name: str):
        self._vector_nodes[reg_name] = {} # initialize the dict for this vector register
        for path_name in ALL_SINGLE_PATHS:
            item = QTreeWidgetItem(reg_item, [path_name])
            item.setText(1, str(getattr(vector_reg, path_name)))
            item.setData(0, ROLE_REG_NAME, reg_name)
            item.setData(0, ROLE_LANE_NAME, path_name)
            item.setData(0, ROLE_IS_VALID, True) # valid as isn't N/A
            self._vector_nodes[reg_name][path_name] = item
        # array lanes
        for path_name in ALL_ARRAY_PATHS:
            if path_name == "f64" and vector_reg.size == 8:
                continue # skip f64 view for 64-bit vectors, as it's already covered by the sf64 view
            item = QTreeWidgetItem(reg_item, [path_name])
            self._create_array_in_vector_view(item, getattr(vector_reg, path_name), reg_name, path_name)
    
    def _update_vector_view(self, reg_item: QTreeWidgetItem, vector_reg: VectorRegister, reg_name: str):
        for path_name in ALL_SINGLE_PATHS:
            self._vector_nodes[reg_name][path_name].setText(1, str(getattr(vector_reg, path_name)))
        for path_name in ALL_ARRAY_PATHS: # iterate over all array views
            if path_name not in self._vector_nodes[reg_name]: # if this view doesn't exist for this register, skip it
                continue
            for i, lane_item in enumerate(self._vector_nodes[reg_name][path_name]):
                lane_item.setText(1, str(getattr(vector_reg, path_name)[i]))

    
    async def _update_register_value(self, reg_item: QTreeWidgetItem, reg_name: str):
        try:
            reg_value = await self._debugger_worker.call_async(self._debugger_worker.get_register, reg_name)
        except ValueError:
            # register isn't available
            reg_item.setText(1, f"N/A")
            reg_item.setData(0, ROLE_IS_VALID, False) # mark as invalid to prevent editing
            reg_item.takeChildren() # clear all children, relevant for vector registers
            if reg_name in self._vector_nodes: # delete its vector nodes if we saved them
                del self._vector_nodes[reg_name]
            return
        if isinstance(reg_value, VectorRegister):
            reg_item.setText(1, "") # clear the text if it was N/A
            if reg_name in self._vector_nodes:
                self._update_vector_view(reg_item, reg_value, reg_name)
            else:
                self._create_vector_view(reg_item, reg_value, reg_name)
        else:
            reg_item.setData(0, ROLE_IS_VALID, True) # mark as valid to allow editing if it was previously N/A
            reg_item.setText(1, str(reg_value))

    async def _update_register_values(self):
        for reg_name in REGISTER_LIST:
            reg_item = self._register_nodes[reg_name]
            await self._update_register_value(reg_item, reg_name)

    @async_slot
    async def _on_state_update(self, state: DebuggerState):
        self._tree.setUpdatesEnabled(False) # disable updates while we update to improve performance and prevent flickering
        await self._update_register_values()
        self._tree.setUpdatesEnabled(True) # reenable updates after we're done
    
    @async_slot
    async def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        reg_name = item.data(0, ROLE_REG_NAME)
        if reg_name is None:
            return # if the item doesn't have a register associated with it, ignore the double click
        is_valid = item.data(0, ROLE_IS_VALID)
        if not is_valid:
            return # if the item is marked as invalid (e.g. N/A), ignore the double click
        # if it's a vector register
        existing_val = item.text(1) # take the value text as the existing value to show
        if reg_name in self._vector_nodes:
            lane_name = item.data(0, ROLE_LANE_NAME)
            if lane_name in ALL_SINGLE_PATHS:
                new_val = await prompt_for_expression(self, f"Edit {reg_name} {lane_name}", f"Enter new value for {reg_name} {lane_name}:", self._debugger_worker, existing_val)
                if new_val is not None:
                    await self._debugger_worker.call_async(self._debugger_worker.update_vector_register, reg_name, lane_name, None, new_val)
            else:
                lane_index = item.data(0, ROLE_LANE_INDEX)
                new_val = await prompt_for_expression(self, f"Edit {reg_name} {lane_name}[{lane_index}]", f"Enter new value for {reg_name} {lane_name}[{lane_index}]:", self._debugger_worker, existing_val)
                if new_val is not None:
                    await self._debugger_worker.call_async(self._debugger_worker.update_vector_register, reg_name, lane_name, lane_index, new_val)
        else:
            new_val = await prompt_for_expression(self, f"Edit {reg_name}", f"Enter new value for {reg_name}:", self._debugger_worker, existing_val)
            if new_val is not None:
                await self._debugger_worker.call_async(self._debugger_worker.set_register, reg_name, new_val)
        
