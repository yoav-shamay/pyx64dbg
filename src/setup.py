from setuptools import setup, Extension

ext_modules = [
    Extension('ptrace', sources=['ptrace/ptrace.c']),
]

setup(
    ext_modules=ext_modules,
)