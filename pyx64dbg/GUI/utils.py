"""
This module contains utility functions for the GUI.
Currently only contains a function to prompt the user for an expression and evaluate it.
"""
from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget
from pyx64dbg.GUI.debugger_worker import DebuggerWorker 
from typing import Any

async def prompt_for_expression(parent_object: QWidget, title: str, label: str, debugger_worker: DebuggerWorker, existing_value: str = "") -> Any:
    """
    Prompts the user for an expression using a QInputDialog, evaluates it using the provided debugger worker, and returns the result.
    If the user cancels the dialog or enters an invalid expression, returns None.
    Shows an error dialog if the expression couldn't be evaluated, with the exception type and message.
    Parameters:
    - parent_object: The parent widget for the dialogs.
    - title: The title for the input dialog.
    - label: The label for the input dialog.
    - debugger_worker: Reference to the debugger worker, used to evaluate the expression.
    - existing_value: An optional existing value to pre-fill in the input dialog.
    """
    expr_str, ok = QInputDialog.getText(parent_object, title, label, text=existing_value)
    if ok and expr_str.strip(): # if the user clicked OK and the expression is not empty
        try: # try to evaluate the expression using the debugger worker
            result = await debugger_worker.call_async(debugger_worker.evaluate_expression, expr_str.strip())
            return result # if evaluation succeeded, return the result
        except Exception as e:
            # show an error dialog if the expression couldn't be evaluated
            error_dialog = QMessageBox(parent_object)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Error")
            # show the exception type and message in the error dialog
            error_dialog.setText(f"<b>{e.__class__.__name__}</b>: {str(e)}")
            error_dialog.exec()
    return None