#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stddef.h>
#include <string.h>

#include "utils.h"

PyObject *bytes_from_field(const void *field, size_t size)
{
    return PyBytes_FromStringAndSize((const char *)field, size);
}

int read_bytes_field(PyObject *source, void *destination, size_t size, const char *field_name)
{
    if (!PyBytes_Check(source)) // first check if it's a bytes object
    {
        PyErr_Format(PyExc_TypeError, "%s must be bytes", field_name);
        return -1;
    }

    char *buffer = NULL;
    Py_ssize_t buffer_size = 0;
    if (PyBytes_AsStringAndSize(source, &buffer, &buffer_size) == -1) // use PyBytes_AsStringAndSize to get the buffer and its size
    {
        PyErr_Format(PyExc_TypeError, "Failed to read bytes from %s", field_name);
        return -1;
    }

    if ((size_t)buffer_size != size) // compare the size with the expected size
    {
        PyErr_Format(PyExc_ValueError, "%s must be exactly %zu bytes", field_name, size);
        return -1;
    }

    memcpy(destination, buffer, size); // copy the data to the destination buffer
    return 0;
}

int read_bytes_field_from_dict(PyObject *regs_dict, const char *field_name, void *destination, size_t size)
{
    PyObject *value = PyDict_GetItemString(regs_dict, field_name);
    if (value == NULL)
    {
        // if the field is not present in the dict, we leave it unchanged, so it's not an error
        return 0;
    }
    return read_bytes_field(value, destination, size, field_name);
}