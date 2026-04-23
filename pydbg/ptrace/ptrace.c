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

static PyObject *method_peekdata(PyObject *self, PyObject *args)
{
    int child_pid;
    size_t address;
    if (!PyArg_ParseTuple(args, "ik", &child_pid, &address))
    {
        return NULL;
    }
    errno = 0;
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

static PyObject *method_get_standard_regs(PyObject *self, PyObject *args)
{
    int child_pid;
    if (!PyArg_ParseTuple(args, "i", &child_pid))
    {
        return NULL;
    }
    struct user_regs_struct regs;
    struct iovec iov;
    iov.iov_base = &regs;
    iov.iov_len = sizeof(regs);
    int ptrace_res = ptrace(PTRACE_GETREGSET, child_pid, NT_PRSTATUS, &iov);
    if (ptrace_res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
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


static PyObject *method_get_extended_regs(PyObject *self, PyObject *args)
{
    int child_pid;
    if (!PyArg_ParseTuple(args, "i", &child_pid))
    {
        return NULL;
    }
    char *xstate_buffer = NULL;
    size_t xstate_size = 0;
    if (get_xstate_buffer_from_child(child_pid, &xstate_buffer, &xstate_size) == -1)
    {
        return NULL;
    }
    PyObject *res = PyDict_New();
    parse_xstate_buffer_to_dict(xstate_buffer, xstate_size, res);
    free(xstate_buffer);
    return res;
}

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
    if (get_xstate_buffer_from_child(child_pid, &xstate_buffer, &xstate_size) == -1)
    {
        return NULL;
    }
    int status = modify_xstate_buffer_from_dict(xstate_buffer, xstate_size, regs_dict);
    if (status == -1)
    {
        free(xstate_buffer);
        return NULL;
    }
    struct iovec iov;
    iov.iov_base = xstate_buffer;
    iov.iov_len = xstate_size;
    int res = ptrace(PTRACE_SETREGSET, child_pid, NT_X86_XSTATE, &iov);
    free(xstate_buffer);
    if (res == -1)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *method_get_memory_range(PyObject *self, PyObject *args)
{
    int child_pid;
    size_t address;
    size_t length;
    if (!PyArg_ParseTuple(args, "ikk", &child_pid, &address, &length))
    {
        return NULL;
    }
    PyObject *buffer = PyBytes_FromStringAndSize(NULL, length);
    if (buffer == NULL)
    {
        return NULL;
    }
    struct iovec local_iov[1];
    local_iov[0].iov_base = PyBytes_AS_STRING(buffer);
    local_iov[0].iov_len = length;
    struct iovec remote_iov[1];
    remote_iov[0].iov_base = (void *)address;
    remote_iov[0].iov_len = length;
    ssize_t nread = process_vm_readv(child_pid, local_iov, 1, remote_iov, 1, 0);
    if (nread == -1 || nread < (ssize_t) length)
    {
        Py_DECREF(buffer);
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    return buffer;
}

static PyObject *method_write_memory_range(PyObject *self, PyObject *args)
{
    int child_pid;
    size_t address;
    Py_buffer buf;
    if (!PyArg_ParseTuple(args, "iky*", &child_pid, &address, &buf))
    {
        return NULL;
    }

    struct iovec local_iov[1];
    local_iov[0].iov_base = buf.buf;
    local_iov[0].iov_len = buf.len;
    struct iovec remote_iov[1];
    remote_iov[0].iov_base = (void *)address;
    remote_iov[0].iov_len = buf.len;
    ssize_t nwritten = process_vm_writev(child_pid, local_iov, 1, remote_iov, 1, 0);
    PyBuffer_Release(&buf);
    if (nwritten == -1 || nwritten < buf.len)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}

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