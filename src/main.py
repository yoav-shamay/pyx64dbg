import argparse
import os
import termios
import pty
import ptrace
from debugger import Debugger


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='dbg',
                                     description='A simple debugger written in python')
    parser.add_argument("filename")
    args = parser.parse_args()
    return args


def start_as_child(file_name : str):
    # disable pty echo
    attrs = termios.tcgetattr(0)
    attrs[3] &= ~termios.ECHO
    termios.tcsetattr(0, termios.TCSANOW, attrs)
    # start ptrace on this process
    ptrace.traceme()
    # execve file_name
    os.execve(file_name, [file_name], {})


def start_and_debug_process(file_name : str):
    child_pid, pty_fd = pty.fork()
    if child_pid == 0: # running as child
        start_as_child(file_name)
    # running as parent
    os.wait() # wait for child to start execve, raising a signal
    return child_pid, pty_fd

def main():
    args = parse_arguments()
    file_name = args.filename
    child_pid, pty = start_and_debug_process(file_name)
    debugger = Debugger(child_pid, pty)

    ptrace.cont(child_pid)
    os.write(pty, b"1234\n")
    print(os.read(pty, 1024))

if __name__ == "__main__":
    main()