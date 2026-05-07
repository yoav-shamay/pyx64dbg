from PySide6.QtWidgets import QInputDialog, QMessageBox
from pyx64dbg.GUI.debugger_worker import DebuggerWorker 
from typing import Any

async def prompt_for_expression(self, title: str, label: str, debugger_worker: DebuggerWorker) -> Any:
    """
    Prompts the user for an expression using a QInputDialog, evaluates it using the provided debugger worker, and returns the result.
    If the user cancels the dialog or enters an invalid expression, returns None.
    """
    expr_str, ok = QInputDialog.getText(None, title, label)
    if ok and expr_str.strip(): # if the user clicked OK and the expression is not empty
        try:
            result = await debugger_worker.call_async(debugger_worker.evaluate_expression, expr_str.strip())
            return result
        except Exception as e:
            # show an error dialog if the expression couldn't be evaluated
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Error")
            # show the exception type and message in the error dialog
            error_dialog.setText(f"<b>{e.__class__.__name__}</b>: {str(e)}")
            error_dialog.exec()
    return None