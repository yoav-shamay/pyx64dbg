#pragma once
#include <pybind11/pybind11.h>
#include <stdint.h>

namespace py = pybind11;
/*
An utility function to get the xstate buffer of the child process using ptrace, given the child process id.
Returns the xstate buffer as a std::string.
Throws an exception if there was an error.
*/
std::string get_xstate_buffer_from_child(int child_pid);
/*
An utility function to modify the xstate buffer given a dict containing the registers to be modified and their new values.
The keys of the dict are strings with the register names, and the values are bytes objects with the register values.
Can contain any subset of registers (as it will first get the current ones and just then modify).
Throws an exception if there was an error.
Does it in-place on the given buffer.
*/
void modify_xstate_buffer_from_dict(std::string &xstate_buffer, const py::dict &regs_dict);
/*
An utility function to parse the xstate buffer and create a python dictionary with the register values.
The keys of the dict are strings with the register names, and the values are bytes with the register values.
Returns the created dictionary.
*/
py::dict parse_xstate_buffer_to_dict(std::string &xstate_buffer);