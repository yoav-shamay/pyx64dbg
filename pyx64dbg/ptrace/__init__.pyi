"""
C++ wrapper for system interaction to control the process using ptrace, procfs and related syscalls.
"""
from typing import Optional

def traceme() -> None:
    """
    ptrace call with PTRACE_TRACEME
    """
    ...
def cont(pid: int, signal: Optional[int] = None) -> None:
    """
    ptrace call with PTRACE_CONT
    """
    ...
def get_standard_regs(pid: int) -> dict[str, bytes]:
    """
    ptrace call with PTRACE_GETREGSET on NT_PRSTATUS
    """
    ...
def get_extended_regs(pid: int) -> dict[str, bytes]:
    """
    ptrace call with PTRACE_GETREGSET on NT_X86_XSTATE
    """
    ...
def set_standard_regs(pid: int, regs: dict[str, bytes]) -> None:
    """
    ptrace call with PTRACE_SETREGSET on NT_PRSTATUS
    """
    ...
def set_extended_regs(pid: int, regs: dict[str, bytes]) -> None:
    """
    ptrace call with PTRACE_SETREGSET on NT_X86_XSTATE
    """
    ...
def single_step(pid: int, signal: Optional[int]=None) -> None:
    """
    ptrace call with PTRACE_SINGLESTEP
    """
    ...
def get_memory_range(pid: int, start_address: int, length: int) -> bytes:
    """
    read memory range of the child process using process_vm_readv
    """
    ...
def write_memory_range(pid: int, start_address: int, data: bytes) -> None:
    """
    write memory range of the child process using /proc/<pid>/mem
    """
    ...
def kill(pid: int) -> None:
    """
    ptrace call with PTRACE_KILL
    """
    ...
def get_auxv(pid: int) -> dict[int, int]:
    """
    read the auxiliary vector of the child process from /proc/<pid>/auxv
    """
    ...