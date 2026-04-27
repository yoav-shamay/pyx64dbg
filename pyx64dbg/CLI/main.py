import argparse
from pyx64dbg.CLI.ipython_cli import IPythonCLI


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='pyx64dbg',
                                     description='A debugger written in python')
    parser.add_argument("filename")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output in case of errors, including full traceback")
    args = parser.parse_args()
    return args

def main():
    args = parse_arguments()
    file_name = args.filename
    console = IPythonCLI(file_name, verbose=args.verbose)
    console.start_console()

if __name__ == "__main__":
    main()