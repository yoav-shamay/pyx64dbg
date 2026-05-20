"""
Utility functions for pyx64dbg, used in multiple places across the codebase.
Currently has only a validate_file function, which checks that a given file name is valid for debugging (exists, is a regular file and is executable).
"""
from __future__ import annotations
import os

def validate_file(file_name: str) -> None:
    """
    Validates that the given file name is valid for debugging.
    Checks that the file exists, is a regular file and is executable.
    Raises a FileNotFoundError if the file doesn't exist, an IsADirectoryError if it's a directory, and a PermissionError if it's not executable or readable.
    """
    if not os.path.exists(file_name):
        raise FileNotFoundError(f"File {file_name} doesn't exist")
    if os.path.isdir(file_name):
        raise IsADirectoryError(f"File {file_name} is a directory.")
    if not os.access(file_name, os.X_OK | os.R_OK):
        raise PermissionError(f"File {file_name} isn't readable or executable")