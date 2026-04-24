from setuptools import setup, Extension

ext_modules = [
    Extension('pyx64dbg.ptrace', sources=['pyx64dbg/ptrace/ptrace.c', 'pyx64dbg/ptrace/utils.c', 'pyx64dbg/ptrace/xstate.c']),
]

setup(
    ext_modules=ext_modules,
)