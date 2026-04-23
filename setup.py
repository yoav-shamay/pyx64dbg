from setuptools import setup, Extension

ext_modules = [
    Extension('pydbg.ptrace', sources=['pydbg/ptrace/ptrace.c', 'pydbg/ptrace/utils.c', 'pydbg/ptrace/xstate.c']),
]

setup(
    ext_modules=ext_modules,
)