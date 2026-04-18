from setuptools import setup, Extension

ext_modules = [
    Extension('pydbg.ptrace', sources=['pydbg/ptrace/ptrace.c']),
]

setup(
    ext_modules=ext_modules,
)