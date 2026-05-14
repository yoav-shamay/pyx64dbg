from __future__ import annotations
from typing import TYPE_CHECKING, Any, TypeAlias, Union

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from pyx64dbg.GUI.debugger_state import DebuggerState
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.utils import prompt_for_expression
from pyx64dbg.vector_register import VectorRegister
from pyx64dbg.number_types import CNumBase
from pyx64dbg.GUI.async_slot import async_slot

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

# structure: a dict where keys are group names (e.g. "FPU", "xmm"), and values are either dicts or a list of register names
TREE_STRUCTURE_TYPE: TypeAlias = dict[str, Union[list[str], "TREE_STRUCTURE_TYPE"]] | list[str] # define a recursive type alias for the tree
TREE_STRUCTURE: TREE_STRUCTURE_TYPE = {
    "FPU": {
        "control": ["fcw", "fsw", "ftw", "fop", "fip", "fdp"],
        "st": [f"st{i}" for i in range(8)],
    },
    "mm": [f"mm{i}" for i in range(8)],
    "mxcsr": ["mxcsr", "mxcsr_mask"],
    "xmm": [f"xmm{i}" for i in range(16)],
    "ymm": [f"ymm{i}" for i in range(16)]
}

REGISTER_LIST: list[str] = []
# create a flat list of all registers from the structure for easy access when getting register values
def add_to_register_list(structure: TREE_STRUCTURE_TYPE):
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

# create roles to store register name and array name and index for easy assignment when double clicking
ROLE_REG_NAME = Qt.ItemDataRole.UserRole # register name
ROLE_ARR_TYPE = Qt.ItemDataRole.UserRole + 1 # type of arr to index
ROLE_ARR_INDEX = Qt.ItemDataRole.UserRole + 2 # index in array if it's an array view
ROLE_IS_VALID = Qt.ItemDataRole.UserRole + 3 # whether it's N/A or valid to edit

class ExtendedRegistersView(QWidget):
    """
    This class defines the extended registers view widget in the GUI.
    It shows the extended registers such as FPU, MMX, XMM and YMM registers in a tree view.\
    Also allows to edit register values.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._register_nodes: dict[str, QTreeWidgetItem] = {} # map between register name and tree node
        self._vector_nodes: dict[str, dict[str, list[QTreeWidgetItem] | QTreeWidgetItem]] = {} # map between vector register name and the type to the node

        self._init_ui()
        self._create_register_tree(TREE_STRUCTURE, self._tree.invisibleRootItem()) # init the tree with the register names, we'll fill in the values later
        self._register_callbacks()
        self._load_qss()
    
    def _register_callbacks(self) -> None:
        """
        Registers the debugger worker callbacks to update the view on various events.
        """
        self._debugger_worker.state_update.connect(self._on_state_update)
    
    def _load_qss(self) -> None:
        """
        Loads the QSS stylesheet from extended_registers_view.qss and applies it to the widget.
        """
        with open(str(self._main_window.base_path / "styles" / "extended_registers_view.qss"), "r") as f:
            self.setStyleSheet(f.read())

    def _init_ui(self) -> None:
        """
        Inits the UI of the widget, creating the tree view and adding it to the layout.
        """
        # setup a monospace consolas font for the register values
        self._values_font = QFont("Consolas", 10)
        self._values_font.setStyleHint(QFont.StyleHint.Monospace)
        # configure tree widget
        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2) # one column for register names, one for values
        self._tree.setAlternatingRowColors(True) # alternating row colors makes it easier to read
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # select entire rows when clicking a cell
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # make the first column (register name) fit contents, and the second column (value) take the remaining space
        self._tree.setHeaderHidden(True) # hide column headers
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked) # allow editing register values by double clicking a cell
        # add the tree to the widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)


    def _create_reg_item(self, reg_item: QTreeWidgetItem, reg_path: str) -> None:
        """
        Inits the tree node for a register, setting its text, font and roles, and saving it in the _register_nodes dict.
        """
        reg_item.setText(1, "N/A") # default value until we fill it in
        reg_item.setFont(1, self._values_font) # use other font for register values
        reg_item.setData(0, ROLE_REG_NAME, reg_path)
        reg_item.setData(0, ROLE_IS_VALID, False) # N/A means invalid
        self._register_nodes[reg_path] = reg_item # save the item in self._register_nodes for access later

    def _create_register_tree(self, structure: TREE_STRUCTURE_TYPE, parent_item: QTreeWidgetItem) -> None:
        """
        Recursively creates the register tree from the given structore object and the root node.
        Doesn't initialize values, just the tree structure.
        """
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

    def _create_array_in_vector_view(self, array_item: QTreeWidgetItem, arr: list[CNumBase], reg_name: str, path_name: str) -> None:
        """
        Creates a specific array view for a vector register.
        gets the root node, the array if items, the name of register, and the name of the path (for saving in the _vector_nodes dict).
        """
        self._vector_nodes[reg_name][path_name] = []
        for i, val in enumerate(arr):
            cur_index_item = QTreeWidgetItem(array_item, [f"[{i}]"])
            cur_index_item.setText(1, str(val)) # set the text to the value
            cur_index_item.setFont(1, self._values_font) # use other font for array values
            # save data about this specific node with our roles, including reg name, path name nad index
            cur_index_item.setData(0, ROLE_REG_NAME, reg_name)
            cur_index_item.setData(0, ROLE_ARR_TYPE, path_name)
            cur_index_item.setData(0, ROLE_ARR_INDEX, i)
            cur_index_item.setData(0, ROLE_IS_VALID, True) # valid as isn't N/A
            # save in _vector_nodes in the appropriate place for easy update.
            self._vector_nodes[reg_name][path_name].append(cur_index_item)
    
    def _create_vector_view(self, reg_item: QTreeWidgetItem, vector_reg: VectorRegister, reg_name: str) -> None:
        """
        Creates a view for a vector register, including all its paths and array views.
        """
        self._vector_nodes[reg_name] = {} # initialize the dict for this vector register
        # single paths (sf32, sf64) are just a single item
        for path_name in ALL_SINGLE_PATHS:
            item = QTreeWidgetItem(reg_item, [path_name])
            val = getattr(vector_reg, path_name) # get the value from the vector register
            item.setText(1, str(val)) # text - set to the value
            item.setFont(1, self._values_font) # use other font for values
            # define data for this node with our custom roles, including name and type (no need for index as it's not an array)
            item.setData(0, ROLE_REG_NAME, reg_name)
            item.setData(0, ROLE_ARR_TYPE, path_name)
            item.setData(0, ROLE_IS_VALID, True) # valid as isn't N/A
            # save in _vector_nodes
            self._vector_nodes[reg_name][path_name] = item
        # array views
        for path_name in ALL_ARRAY_PATHS:
            if path_name == "f64" and vector_reg.size == 8:
                continue # skip f64 view for 64-bit vectors, as it's already covered by the sf64 view
            item = QTreeWidgetItem(reg_item, [path_name])
            val = getattr(vector_reg, path_name) # get the array from the vector register
            self._create_array_in_vector_view(item, val, reg_name, path_name)
    
    def _update_vector_view(self, vector_reg: VectorRegister, reg_name: str) -> None:
        """
        Updates the view for a vector register with new values, including all its paths and array views.
        Assumes the structure of the view is already created (it wasn't N/A), and just updates the values.
        """
        # single number views
        for path_name in ALL_SINGLE_PATHS:
            val = getattr(vector_reg, path_name) # get the value from the vector register
            # update the saved node for this path with the new value
            self._vector_nodes[reg_name][path_name].setText(1, str(val))
        for path_name in ALL_ARRAY_PATHS: # iterate over all array views
            if path_name not in self._vector_nodes[reg_name]: # if this view doesn't exist for this register, skip it
                continue
            # update the view for each item in the array
            arr_val = getattr(vector_reg, path_name) # get the array from the vector register
            for i, item in enumerate(self._vector_nodes[reg_name][path_name]):
                item.setText(1, str(arr_val[i])) # set the text to the new value

    
    async def _update_register_value(self, reg_item: QTreeWidgetItem, reg_name: str) -> None:
        """
        Updates the value of a single register in the view by getting its current value from the debugger.
        If the register isn't available, marks it as N/A and invalid.
        If it's a vector register, updates its entire subtree.
        """
        # fetch the register value from the debugger worker asynchronously.
        # We fetch it here instead of saving it in the state because this is the only place where it's used, so there's no need to save it and emit it with every state update.
        try:
            reg_value = await self._debugger_worker.call_async(self._debugger_worker.get_register, reg_name)
        except Exception:
            # register isn't available
            reg_item.setText(1, f"N/A")
            reg_item.setFont(1, self._values_font) # use other font for register values
            reg_item.setData(0, ROLE_IS_VALID, False) # mark as invalid to prevent editing
            reg_item.takeChildren() # clear all children, relevant for vector registers
            if reg_name in self._vector_nodes: # delete its vector nodes if we saved them
                del self._vector_nodes[reg_name]
            return
        if isinstance(reg_value, VectorRegister):
            # vector register - we need to update every single value in the subtree
            reg_item.setText(1, "") # clear the text if it was N/A
            if reg_name in self._vector_nodes: # it already exists, just need to update
                self._update_vector_view(reg_value, reg_name)
            else: # it doesn't exist, we need to create the entire subtree for this register
                self._create_vector_view(reg_item, reg_value, reg_name)
        else:
            # a normal register, just editing the data
            reg_item.setData(0, ROLE_IS_VALID, True) # mark as valid to allow editing if it was previously N/A
            reg_item.setText(1, str(reg_value))

    async def _update_register_values(self) -> None:
        """
        Updates all the register values in the view.
        Should be called every time we get a new state update from the debugger to refresh the values.
        """
        for reg_name in REGISTER_LIST:
            reg_item = self._register_nodes[reg_name]
            await self._update_register_value(reg_item, reg_name)

    @async_slot
    async def _on_state_update(self, state: DebuggerState):
        """
        Callback for when we get a new state update from the debugger worker.
        """
        if self._main_window.debugger_busy or not self._main_window.process_running:
            return # if the debugger is busy or not running don't try to update as we can't call it
        self._tree.setUpdatesEnabled(False) # disable updates while we update to improve performance and prevent flickering
        await self._update_register_values()
        self._tree.setUpdatesEnabled(True) # reenable updates after we're done
    
    @async_slot
    async def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Double click callback for the tree items.
        Prompts the user to enter a new value for the register, and updates it in the debugger if they do.
        Handles specific views for vector registers.
        """
        if self._main_window.debugger_busy:
            return # if the debugger is busy, don't allow editing as we can't call the thread
        reg_name = item.data(0, ROLE_REG_NAME)
        if reg_name is None:
            return # if the item doesn't have a register associated with it, ignore the double click
        is_valid = item.data(0, ROLE_IS_VALID)
        if not is_valid:
            return # if the item is marked as invalid (e.g. N/A), ignore the double click
        existing_val = item.text(1) # take the value text as the existing value to show
        if reg_name in self._vector_nodes:
            # if it's a vector register, we need to check the specific view we are updating
            view_name = item.data(0, ROLE_ARR_TYPE)
            if view_name in ALL_SINGLE_PATHS:
                # single value view, we can just update this specific path for the register
                new_val = await prompt_for_expression(self, f"Edit {reg_name} {view_name}", f"Enter new value for {reg_name} {view_name}:", self._debugger_worker, existing_val)
                if new_val is not None:
                    # if we got a value, update the specific path for this vector register with the new value
                    await self._debugger_worker.call_async(self._debugger_worker.update_vector_register, reg_name, view_name, None, new_val)
            else:
                # array view, we need to get the index to update the specific item in the array
                index = item.data(0, ROLE_ARR_INDEX)
                new_val = await prompt_for_expression(self, f"Edit {reg_name} {view_name}[{index}]", f"Enter new value for {reg_name} {view_name}[{index}]:", self._debugger_worker, existing_val)
                if new_val is not None:
                    await self._debugger_worker.call_async(self._debugger_worker.update_vector_register, reg_name, view_name, index, new_val)
        else:
            # normal register, we just prompt for the new value and update it
            new_val = await prompt_for_expression(self, f"Edit {reg_name}", f"Enter new value for {reg_name}:", self._debugger_worker, existing_val)
            if new_val is not None:
                await self._debugger_worker.call_async(self._debugger_worker.set_register, reg_name, new_val)
        
