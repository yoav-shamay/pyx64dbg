from setuptools import setup, find_packages
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        'pyx64dbg.ptrace',
        sources=[
            'pyx64dbg/ptrace/ptrace.cpp', 
            'pyx64dbg/ptrace/utils.cpp', 
            'pyx64dbg/ptrace/xstate.cpp'
        ],
        # Include the directory where utils.hpp and xstate.hpp are
        include_dirs=["pyx64dbg/ptrace"],
        # Use C++20 standard for compilation
        cxx_std=20,
    ),
    Pybind11Extension(
        'pyx64dbg.number_types',
        sources=[
            'pyx64dbg/number_types/number_types.cpp',
        ],
        include_dirs=["pyx64dbg/number_types"],
        cxx_std=20,
    )
]

setup(
    ext_modules=ext_modules,
    packages=find_packages(), 
    # Use the pybind11 build_ext which optimizes for smaller binaries
    cmdclass={"build_ext": build_ext},
)