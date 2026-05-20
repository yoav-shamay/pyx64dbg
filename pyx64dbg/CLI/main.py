"""
The entry point for the CLI tool.
Parses command line arguments and starts the IPython CLI for the debugger.
"""
from __future__ import annotations
import argparse
import sys
import os
from pyx64dbg.utils import validate_file
from pyx64dbg.CLI.ipython_cli import IPythonCLI


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments for the CLI tool.
    Returns an argparse.Namespace object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(prog='pyx64dbg',
                                     description='A debugger for x64 Linux binaries, written in Python')
    # optional filename argument
    parser.add_argument("filename", nargs="?", default=None, help="The file to debug")
    # verbose option (full tracebacks)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output in case of errors, including full traceback")
    args = parser.parse_args()
    return args

def main():
    """
    The entry point for the CLI tool.
    """
    args = parse_arguments()
    file_name = args.filename
    if file_name is not None:
        # validate the file if it exists, to give the user immediate feedback if they provided an invalid file
        try:
            validate_file(file_name)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(os.EX_NOINPUT)
        except IsADirectoryError as e:
            print(f"Error: {e}")
            sys.exit(os.EX_NOINPUT)
        except PermissionError as e:
            print(f"Error: {e}")
            sys.exit(os.EX_NOPERM)
    console = IPythonCLI(file_name, verbose=args.verbose)
    console.start_console()

if __name__ == "__main__":
    main()