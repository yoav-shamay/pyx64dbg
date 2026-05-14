"""
A script to generate the stubs for the number types in the cnum module, using a Jinja2 template.
The template is located at tools/templates/number_types.pyi.j2.
Requires the jinja2 and black libraries to be installed.
"""
from __future__ import annotations

import os
from jinja2 import Environment, FileSystemLoader
import black
import argparse
from pathlib import Path

# Metadata on each type - name, priority, float/int, size in bytes, signed/unsigned
TYPES =[
    {"name": "Int8",    "prio": 1,  "is_float": False, "size": 1,  "signed": True, "docstring": "Signed 8-bit C-like integer"},
    {"name": "UInt8",   "prio": 2,  "is_float": False, "size": 1,  "signed": False, "docstring": "Unsigned 8-bit C-like integer"},
    {"name": "Int16",   "prio": 3,  "is_float": False, "size": 2,  "signed": True, "docstring": "Signed 16-bit C-like integer"},
    {"name": "UInt16",  "prio": 4,  "is_float": False, "size": 2,  "signed": False, "docstring": "Unsigned 16-bit C-like integer"},
    {"name": "Int32",   "prio": 5,  "is_float": False, "size": 4,  "signed": True, "docstring": "Signed 32-bit C-like integer"},
    {"name": "UInt32",  "prio": 6,  "is_float": False, "size": 4,  "signed": False, "docstring": "Unsigned 32-bit C-like integer"},
    {"name": "Int64",   "prio": 7,  "is_float": False, "size": 8,  "signed": True, "docstring": "Signed 64-bit C-like integer"},
    {"name": "UInt64",  "prio": 8,  "is_float": False, "size": 8,  "signed": False, "docstring": "Unsigned 64-bit C-like integer"},
    {"name": "Float32", "prio": 10, "is_float": True,  "size": 4,  "signed": True, "docstring": "32-bit floating point C-like number"},
    {"name": "Float64", "prio": 11, "is_float": True,  "size": 8,  "signed": True, "docstring": "64-bit floating point C-like number"},
    {"name": "Float80", "prio": 12, "is_float": True,  "size": 10, "signed": True, "docstring": "80-bit floating point C-like number"},
]

# Standard Arithmetic (Binary)
UNIVERSAL_OPS = ["add", "sub", "mul", "truediv"]

# Integer-only (Binary)
INTEGER_OPS =["floordiv", "mod", "lshift", "rshift", "and", "or", "xor"]

# Comparisons (Binary -> bool)
COMPARISON_OPS =["lt", "le", "gt", "ge"]

# all aliases of types
ALIASES =[
    ("Char", "Int8"), ("UChar", "UInt8"),
    ("Short", "Int16"), ("UShort", "UInt16"),
    ("Int", "Int32"), ("UInt", "UInt32"),
    ("Long", "Int64"), ("ULong", "UInt64"),
    ("Float", "Float32"), ("Double", "Float64"), ("LongDouble", "Float80"),
]


def main(template_path: Path, output_path: Path) -> None:
    # create an environment and load the template.
    env = Environment(loader=FileSystemLoader(template_path.parent))
    template = env.get_template(template_path.name)
    # setup global context for the template
    data = {
        "types": TYPES,
        "aliases": ALIASES,
        "universal_ops": UNIVERSAL_OPS,
        "integer_ops": INTEGER_OPS,
        "comparison_ops": COMPARISON_OPS,
        "python_float_prio": 9
    }
    # render the template
    output = template.render(data)
    # format the output using black, in pyi mode
    output = black.format_str(output, mode=black.FileMode(is_pyi=True))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)
    # print a message with the absolute path to the generated file
    print(f"Generated stubs at: {os.path.abspath(output_path)}")


if __name__ == "__main__":
    # parse the output path from arguments
    parser = argparse.ArgumentParser(description="Generate Python stubs for CNum types.")
    parser.add_argument(
        "-o", "--output", 
        type=Path,
        default=Path("output.pyi"),
        help="Path to the output stub file (default: output.pyi)"
    )
    parser.add_argument(
        "-t", "--template",
        type=Path,
        default=Path("templates/number_types.pyi.j2"),
        help="Path to the Jinja2 template file (default: templates/number_types.pyi.j2)"
    )
    args = parser.parse_args()
    main(args.template, args.output)