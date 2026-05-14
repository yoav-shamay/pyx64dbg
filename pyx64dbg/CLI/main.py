"""
The entry point for the CLI tool.
Parses command line arguments and starts the IPython CLI for the debugger.
"""
from __future__ import annotations
import argparse
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
    console = IPythonCLI(file_name, verbose=args.verbose)
    console.start_console()

if __name__ == "__main__":
    main()