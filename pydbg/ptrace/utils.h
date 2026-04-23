#ifndef PYDBG_PTRACE_UTILS_H
#define PYDBG_PTRACE_UTILS_H

#include <Python.h>
#include <stddef.h>

PyObject *bytes_from_field(const void *field, size_t size);
int read_bytes_field(PyObject *source, void *destination, size_t size, const char *field_name);
int read_bytes_field_from_dict(PyObject *regs_dict, const char *field_name, void *destination, size_t size);

#endif