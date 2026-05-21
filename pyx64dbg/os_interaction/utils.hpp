#pragma once
#include <pybind11/pybind11.h>
#include <stddef.h>

namespace py = pybind11;

/*
A utility function to raise a python OSError exception from the current value of errno.
Equivalent of PyErr_SetFromErrno(PyExc_OSError) but uses c++ exceptions.
*/
void raise_errno_as_os_error();

/*
An utility function to convert a field of the user_regs_struct to a python bytes object, given a pointer to the field and its size.
*/
py::bytes bytes_from_field(void *field_ptr, size_t field_size);

/*
An utility function to read a bytes object from a python dictionary and write it to a destination buffer.
Does nothing if the key isn't present, as it is used to update a register if it exists in the dictionary
*/
void read_bytes_field_from_dict(py::dict dict, const std::string &key, void *destination, const size_t size);
