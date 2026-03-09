import argparse
from debugger import Debugger


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='dbg',
                                     description='A simple debugger written in python')
    parser.add_argument("filename")
    args = parser.parse_args()
    return args

def main():
    args = parse_arguments()
    file_name = args.filename
    debugger = Debugger.start_and_debug(file_name)
    debugger.cont()

if __name__ == "__main__":
    main()