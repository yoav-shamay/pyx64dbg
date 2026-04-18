import argparse
from debugger import Debugger

from interactive_console.interactive_console import InteractiveConsole


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='pydbg',
                                     description='A debugger written in python')
    parser.add_argument("filename")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output in case of errors, including full traceback")
    args = parser.parse_args()
    return args

def main():
    args = parse_arguments()
    file_name = args.filename
    console = InteractiveConsole(file_name, verbose=args.verbose)
    console.start_console()

if __name__ == "__main__":
    main()