#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <sys/user.h>
#include <sys/uio.h>
#include <elf.h>
#include <string.h>

#include "utils.h"
#include "xstate.h"

/*
Implementation of the traceme method for the python binding.
Gets no parameter and returns nothing.
calls ptrace with PTRACE_TRACEME.
*/
static PyObject *method_traceme(PyObject *self, PyObject *ignored)
{
    int res = ptrace(PTRACE_TRACEME, 0, NULL, NULL);
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

/*
Implementation of the cont method for the python binding.
Gets the child process id and an optional signal number to be sent to the child process when continued, and returns nothing.
calls ptrace with PTRACE_CONT.
*/
static PyObject *method_cont(PyObject *self, PyObject *args)
{
    int child_pid;
    void *signal = NULL;

    if (!PyArg_ParseTuple(args, "i|l", &child_pid, &signal))
    {
        return NULL;
    }
    int res = ptrace(PTRACE_CONT, child_pid, NULL, (void *)signal);
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

/*
An implementation of the peekdata method for the python binding.
Gets the child process id and the address to peek, and returns the data at that address in the child process as a python integer.
calls ptrace with PTRACE_PEEKDATA.
*/
static PyObject *method_peekdata(PyObject *self, PyObject *args)
{
    int child_pid;
    size_t address;
    if (!PyArg_ParseTuple(args, "ik", &child_pid, &address))
    {
        return NULL;
    }
    errno = 0; // reset errno so we can accurately tell if ptrace failed or if the data at the address is actually -1
    unsigned long res = ptrace(PTRACE_PEEKDATA, child_pid, (void *)address, NULL);
    if (errno == 0)
    {
        return PyLong_FromUnsignedLong(res);
    }
    else
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
}

/*
Implementation of the pokedata method for the python binding.
Gets the child process id, the address to poke and the data to poke, and returns nothing.
calls ptrace with PTRACE_POKEDATA.
*/
static PyObject *method_pokedata(PyObject *self, PyObject *args)
{
    int child_pid;
    unsigned long data;
    size_t address;
    if (!PyArg_ParseTuple(args, "ikk", &child_pid, &address, &data))
    {
        return NULL;
    }
    int res = ptrace(PTRACE_POKEDATA, child_pid, (void *)address, (void *)data);
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

/*
Implementation of the single_step method for the python binding.
Gets the child process id and an optional signal number to be sent to the child process when continued, and returns nothing.
calls ptrace with PTRACE_SINGLESTEP.
*/
static PyObject *method_single_step(PyObject *self, PyObject *args)
{
    int child_pid;
    void *signal = NULL;

    if (!PyArg_ParseTuple(args, "i|l", &child_pid, &signal))
    {
        return NULL;
    }
    int res = ptrace(PTRACE_SINGLESTEP, child_pid, NULL, signal);
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

/*
Implementation of the get_standard_regs method for the python binding.
Gets the child process id and returns a dict containing the standard registers of the child process.
The keys are python strings with the register names, and the values are bytes objects.
calls ptrace with PTRACE_GETREGSET on NT_PRSTATUS.
*/
static PyObject *method_get_standard_regs(PyObject *self, PyObject *args)
{
    int child_pid;
    if (!PyArg_ParseTuple(args, "i", &child_pid))
    {
        return NULL;
    }
    struct user_regs_struct regs;
    // init an iov pointing to the regs struct
    struct iovec iov;
    iov.iov_base = &regs;
    iov.iov_len = sizeof(regs);

    int ptrace_res = ptrace(PTRACE_GETREGSET, child_pid, NT_PRSTATUS, &iov);
    if (ptrace_res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    // create a dictionary with all fields of the regs struct, with the field names as keys and the field values as bytes objects
    PyObject *res = PyDict_New();
    PyDict_SetItemString(res, "rax", bytes_from_field(&regs.rax, sizeof(regs.rax)));
    PyDict_SetItemString(res, "rbx", bytes_from_field(&regs.rbx, sizeof(regs.rbx)));
    PyDict_SetItemString(res, "rcx", bytes_from_field(&regs.rcx, sizeof(regs.rcx)));
    PyDict_SetItemString(res, "rdx", bytes_from_field(&regs.rdx, sizeof(regs.rdx)));
    PyDict_SetItemString(res, "rsi", bytes_from_field(&regs.rsi, sizeof(regs.rsi)));
    PyDict_SetItemString(res, "rdi", bytes_from_field(&regs.rdi, sizeof(regs.rdi)));
    PyDict_SetItemString(res, "rsp", bytes_from_field(&regs.rsp, sizeof(regs.rsp)));
    PyDict_SetItemString(res, "rbp", bytes_from_field(&regs.rbp, sizeof(regs.rbp)));
    PyDict_SetItemString(res, "r8", bytes_from_field(&regs.r8, sizeof(regs.r8)));
    PyDict_SetItemString(res, "r9", bytes_from_field(&regs.r9, sizeof(regs.r9)));
    PyDict_SetItemString(res, "r10", bytes_from_field(&regs.r10, sizeof(regs.r10)));
    PyDict_SetItemString(res, "r11", bytes_from_field(&regs.r11, sizeof(regs.r11)));
    PyDict_SetItemString(res, "r12", bytes_from_field(&regs.r12, sizeof(regs.r12)));
    PyDict_SetItemString(res, "r13", bytes_from_field(&regs.r13, sizeof(regs.r13)));
    PyDict_SetItemString(res, "r14", bytes_from_field(&regs.r14, sizeof(regs.r14)));
    PyDict_SetItemString(res, "r15", bytes_from_field(&regs.r15, sizeof(regs.r15)));
    PyDict_SetItemString(res, "rip", bytes_from_field(&regs.rip, sizeof(regs.rip)));
    PyDict_SetItemString(res, "eflags", bytes_from_field(&regs.eflags, sizeof(regs.eflags)));
    PyDict_SetItemString(res, "cs", bytes_from_field(&regs.cs, sizeof(regs.cs)));
    PyDict_SetItemString(res, "ss", bytes_from_field(&regs.ss, sizeof(regs.ss)));
    PyDict_SetItemString(res, "ds", bytes_from_field(&regs.ds, sizeof(regs.ds)));
    PyDict_SetItemString(res, "es", bytes_from_field(&regs.es, sizeof(regs.es)));
    PyDict_SetItemString(res, "fs", bytes_from_field(&regs.fs, sizeof(regs.fs)));
    PyDict_SetItemString(res, "gs", bytes_from_field(&regs.gs, sizeof(regs.gs)));
    PyDict_SetItemString(res, "fs_base", bytes_from_field(&regs.fs_base, sizeof(regs.fs_base)));
    PyDict_SetItemString(res, "gs_base", bytes_from_field(&regs.gs_base, sizeof(regs.gs_base)));
    PyDict_SetItemString(res, "orig_rax", bytes_from_field(&regs.orig_rax, sizeof(regs.orig_rax)));
    return res;
}

/*
Implementation of the get_extended_regs method for the python binding.
Gets the child process id and returns a dict containing the extended registers of the child process.
Currently only contains the legacy region and YMM registers, can be extended to contain more registers in the future if needed.
The keys are python strings with the register names, and the values are bytes objects.
calls ptrace with PTRACE_GETREGSET on NT_X86_XSTATE.
*/
static PyObject *method_get_extended_regs(PyObject *self, PyObject *args)
{
    int child_pid;
    if (!PyArg_ParseTuple(args, "i", &child_pid))
    {
        return NULL;
    }
    char *xstate_buffer = NULL;
    size_t xstate_size = 0;
    if (get_xstate_buffer_from_child(child_pid, &xstate_buffer, &xstate_size) == -1) // first get the xstate buffer using the get_xstate_buffer_from_child function
    {
        return NULL;
    }
    PyObject *res = PyDict_New();
    parse_xstate_buffer_to_dict(xstate_buffer, xstate_size, res); // call parse_xstate_buffer_to_dict to parse the buffer and fill the dict.
    free(xstate_buffer); // free the xstate buffer now that it's unused.
    return res;
}

/*
Implementation of the set_standard_regs method for the python binding.
Gets the child process id and a dict containing the standard registers to be set in the child process, and returns nothing.
The keys of the dict are python strings with the register names, and the values are bytes objects with the register values.
Can contain any subset of registers (as it will first get the current ones and just then modify).
calls ptrace with PTRACE_SETREGSET on NT_PRSTATUS.
*/
static PyObject *method_set_standard_regs(PyObject *self, PyObject *args)
{
    int child_pid;
    PyObject *regs_dict;
    if (!PyArg_ParseTuple(args, "iO!", &child_pid, &PyDict_Type, &regs_dict))
    {
        return NULL;
    }
    struct user_regs_struct regs;
    // first get the current registers, so that we only modify the fields that are present in the input dict, and leave the rest unchanged
    struct iovec iov;
    iov.iov_base = &regs;
    iov.iov_len = sizeof(regs);
    if (ptrace(PTRACE_GETREGSET, child_pid, NT_PRSTATUS, &iov) == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    // now modify the registers according to the input dict, only for the fields that are present in the dict
    if (read_bytes_field_from_dict(regs_dict, "rax", &regs.rax, sizeof(regs.rax)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rbx", &regs.rbx, sizeof(regs.rbx)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rcx", &regs.rcx, sizeof(regs.rcx)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rdx", &regs.rdx, sizeof(regs.rdx)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rsi", &regs.rsi, sizeof(regs.rsi)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rdi", &regs.rdi, sizeof(regs.rdi)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rsp", &regs.rsp, sizeof(regs.rsp)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rbp", &regs.rbp, sizeof(regs.rbp)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r8", &regs.r8, sizeof(regs.r8)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r9", &regs.r9, sizeof(regs.r9)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r10", &regs.r10, sizeof(regs.r10)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r11", &regs.r11, sizeof(regs.r11)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r12", &regs.r12, sizeof(regs.r12)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r13", &regs.r13, sizeof(regs.r13)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r14", &regs.r14, sizeof(regs.r14)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "r15", &regs.r15, sizeof(regs.r15)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "rip", &regs.rip, sizeof(regs.rip)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "eflags", &regs.eflags, sizeof(regs.eflags)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "cs", &regs.cs, sizeof(regs.cs)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "ss", &regs.ss, sizeof(regs.ss)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "ds", &regs.ds, sizeof(regs.ds)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "es", &regs.es, sizeof(regs.es)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "fs", &regs.fs, sizeof(regs.fs)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "gs", &regs.gs, sizeof(regs.gs)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "fs_base", &regs.fs_base, sizeof(regs.fs_base)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "gs_base", &regs.gs_base, sizeof(regs.gs_base)) == -1) return NULL;
    if (read_bytes_field_from_dict(regs_dict, "orig_rax", &regs.orig_rax, sizeof(regs.orig_rax)) == -1) return NULL;
    // now write the modified registers back to the child process
    int res = ptrace(PTRACE_SETREGSET, child_pid, NT_PRSTATUS, &iov);
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

/*
Implementation of the set_extended_regs method for the python binding.
Gets the child process id and a dict containing the extended registers to be set in the child process, and returns nothing.
The keys of the dict are python strings with the register names, and the values are bytes objects with the register values.
Currently only supports the legacy region and YMM registers, can be extended to support more registers in the future if needed.
Can contain any subset of registers (as it will first get the current ones and just then modify).
calls ptrace with PTRACE_SETREGSET on NT_X86_XSTATE.
*/
static PyObject *method_set_extended_regs(PyObject *self, PyObject *args)
{
    int child_pid;
    PyObject *regs_dict;
    if (!PyArg_ParseTuple(args, "iO!", &child_pid, &PyDict_Type, &regs_dict))
    {
        return NULL;
    }
    char *xstate_buffer = NULL;
    size_t xstate_size = 0;
    // first we need to get the xstate buffer, as we don't recieve every register and need to modify an existing buffer.
    if (get_xstate_buffer_from_child(child_pid, &xstate_buffer, &xstate_size) == -1)
    {
        return NULL;
    }
    // call modify_xstate_buffer_from_dict to modify it. It returns -1 if it failed.
    int status = modify_xstate_buffer_from_dict(xstate_buffer, xstate_size, regs_dict);
    if (status == -1)
    {
        free(xstate_buffer);
        return NULL;
    }
    // create an iov pointing to the modified buffer
    struct iovec iov;
    iov.iov_base = xstate_buffer;
    iov.iov_len = xstate_size;
    // call ptrace to write it to the child process
    int res = ptrace(PTRACE_SETREGSET, child_pid, NT_X86_XSTATE, &iov);
    free(xstate_buffer); // free the xstate buffer now that it's unused. We do it before checking for an error as it needs to be done anyway.
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

/*
Implementation of the get_memory_range method for the python binding.
Gets the child process id, the start address and the length of the memory range to read, and returns the data in that memory range as a bytes object.
calls process_vm_readv to read the memory range from the child process.
*/
static PyObject *method_get_memory_range(PyObject *self, PyObject *args)
{
    int child_pid;
    size_t address;
    size_t length;
    if (!PyArg_ParseTuple(args, "ikk", &child_pid, &address, &length))
    {
        return NULL;
    }
    // create a python bytes object to hold the data
    PyObject *buffer = PyBytes_FromStringAndSize(NULL, length);
    if (buffer == NULL)
    {
        return NULL;
    }
    // create an iov for the local buffer
    struct iovec local_iov[1];
    local_iov[0].iov_base = PyBytes_AS_STRING(buffer);
    local_iov[0].iov_len = length;
    // create an iov for the remote buffer
    struct iovec remote_iov[1];
    remote_iov[0].iov_base = (void *)address;
    remote_iov[0].iov_len = length;
    ssize_t nread = process_vm_readv(child_pid, local_iov, 1, remote_iov, 1, 0);
    if (nread == -1 || nread < (ssize_t) length) // if we failed to read or we read less than the required length, error
    {
        Py_DECREF(buffer); // free the buffer we created, as it's unused in case of an error
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    return buffer;
}

/*
Implementation of the write_memory_range method for the python binding.
Gets the child process id, the start address and a bytes object containing the data to write,and returns nothing.
calls process_vm_writev to write the memory range to the child process.
*/
static PyObject *method_write_memory_range(PyObject *self, PyObject *args)
{
    int child_pid;
    size_t address;
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "iky*", &child_pid, &address, &buf))
    {
        return NULL;
    }
    // local buffer iov (parameter we are given)
    struct iovec local_iov[1];
    local_iov[0].iov_base = buf.buf;
    local_iov[0].iov_len = buf.len;
    // remote iov (the address we want to write to in the child process)
    struct iovec remote_iov[1];
    remote_iov[0].iov_base = (void *)address;
    remote_iov[0].iov_len = buf.len;
    ssize_t nwritten = process_vm_writev(child_pid, local_iov, 1, remote_iov, 1, 0);
    PyBuffer_Release(&buf); // release the buffer we got from the parameters, as it's unused after this point. We do it before checking for an error as it needs to be done anyway.
    if (nwritten == -1 || nwritten < buf.len) // If we failed to write or we wrote less than the required length, error
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

/*
Implementation of the kill method for the python binding.
Gets the child process id and returns nothing.
calls ptrace with PTRACE_KILL to kill the child process.
*/
static PyObject *method_kill(PyObject *self, PyObject *args)
{
    int child_pid;
    if (!PyArg_ParseTuple(args, "i", &child_pid))
    {
        return NULL;
    }
    int res = ptrace(PTRACE_KILL, child_pid, NULL, NULL);
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}
static PyMethodDef Ptrace_methods[] = {
    {"traceme", method_traceme, METH_NOARGS, "ptrace call with PTRACE_TRACEME"},
    {"cont", method_cont, METH_VARARGS, "ptrace call with PTRACE_CONT"},
    {"peekdata", method_peekdata, METH_VARARGS, "ptrace call with PTRACE_PEEKDATA"},
    {"pokedata", method_pokedata, METH_VARARGS, "ptrace call with PTRACE_POKEDATA"},
    {"single_step", method_single_step, METH_VARARGS, "ptrace call with PTRACE_SINGLESTEP"},
    {"get_standard_regs", method_get_standard_regs, METH_VARARGS, "ptrace call with PTRACE_GETREGSET on NT_PRSTATUS"},
    {"get_extended_regs", method_get_extended_regs, METH_VARARGS, "ptrace call with PTRACE_GETREGSET on NT_X86_XSTATE"},
    {"set_standard_regs", method_set_standard_regs, METH_VARARGS, "ptrace call with PTRACE_SETREGSET on NT_PRSTATUS"},
    {"set_extended_regs", method_set_extended_regs, METH_VARARGS, "ptrace call with PTRACE_SETREGSET on NT_X86_XSTATE"},
    {"get_memory_range", method_get_memory_range, METH_VARARGS, "read memory range of the child process using process_vm_readv"},
    {"write_memory_range", method_write_memory_range, METH_VARARGS, "write memory range of the child process using process_vm_writev"},
    {"kill", method_kill, METH_VARARGS, "kill the child process"},
    {NULL, NULL, 0, NULL}
};

static PyModuleDef Ptrace_module = {
    PyModuleDef_HEAD_INIT,
    "ptrace",
    "C ptrace wrapper module",
    -1,
    Ptrace_methods
};

PyMODINIT_FUNC
PyInit_ptrace(void)
{
    return PyModule_Create(&Ptrace_module);
}