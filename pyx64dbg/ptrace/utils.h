#ifndef PYX64DBG_PTRACE_UTILS_H
#define PYX64DBG_PTRACE_UTILS_H

#include <Python.h>
#include <stddef.h>
/*
An utility function to create a bytes object from a field in a struct, given the field's pointer and size.
*/
PyObject *bytes_from_field(const void *field, size_t size);
/*
An utility function to read a bytes object from a python object and copy it to a destination buffer, given the field name for error messages.
Returns 0 on success and -1 on failure, and sets a python exception on failure.
*/
int read_bytes_field(PyObject *source, void *destination, size_t size, const char *field_name);
/*
An utility function to read a bytes object from a dict given a field name, and copy it to a destination buffer.
If the field is not present in the dict, we leave the destination buffer unchanged and return success, as the caller might want to only update some fields and leave the rest unchanged.
Returns 0 on success and -1 on failure, and sets a python exception on failure.
*/
int read_bytes_field_from_dict(PyObject *regs_dict, const char *field_name, void *destination, size_t size);

#endif