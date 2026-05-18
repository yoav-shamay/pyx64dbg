from __future__ import annotations

from setuptools import setup, find_packages
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        'pyx64dbg.number_types',
        sources=[
            'pyx64dbg/number_types/number_types.cpp',
        ],
        # Include the directory where the header file is located
        include_dirs=["pyx64dbg/number_types"],
        # Use C++20 standard for compilation
        cxx_std=20,
    ),
    Pybind11Extension(
        'pyx64dbg.os_interaction',
        sources=[
            'pyx64dbg/os_interaction/os_interaction.cpp', 
            'pyx64dbg/os_interaction/utils.cpp', 
            'pyx64dbg/os_interaction/xstate.cpp'
        ],
        include_dirs=["pyx64dbg/os_interaction"],
        cxx_std=20,
    )
]

setup(
    ext_modules=ext_modules,
    packages=find_packages(include=["pyx64dbg", "pyx64dbg.*"]), 
    # Use the pybind11 build_ext which optimizes for smaller binaries
    cmdclass={"build_ext": build_ext},
)