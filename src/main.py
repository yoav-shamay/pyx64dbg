import argparse
from debugger import Debugger

from interactive_console import InteractiveConsole


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='dbg',
                                     description='A debugger written in python')
    parser.add_argument("filename")
    args = parser.parse_args()
    return args

def main():
    args = parse_arguments()
    file_name = args.filename
    debugger = Debugger.start_and_debug(file_name)
    console = InteractiveConsole(debugger)
    console.run()

if __name__ == "__main__":
    main()