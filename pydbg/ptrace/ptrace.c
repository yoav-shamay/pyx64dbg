#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <sys/ptrace.h>
#include <sys/user.h>
#include <sys/uio.h>
#include <elf.h>

// an upper bound to the auxiliary vector entries. In practice, the number of auxv entries is usually around 20-30, but we set a higher limit just in case.
#define MAX_AUXV_ENTRIES 64


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
    PyDict_SetItemString(res, "rax", PyLong_FromUnsignedLong(regs.rax));
    PyDict_SetItemString(res, "rbx", PyLong_FromUnsignedLong(regs.rbx));
    PyDict_SetItemString(res, "rcx", PyLong_FromUnsignedLong(regs.rcx));
    PyDict_SetItemString(res, "rdx", PyLong_FromUnsignedLong(regs.rdx));
    PyDict_SetItemString(res, "rsi", PyLong_FromUnsignedLong(regs.rsi));
    PyDict_SetItemString(res, "rdi", PyLong_FromUnsignedLong(regs.rdi));
    PyDict_SetItemString(res, "rsp", PyLong_FromUnsignedLong(regs.rsp));
    PyDict_SetItemString(res, "rbp", PyLong_FromUnsignedLong(regs.rbp));
    PyDict_SetItemString(res, "r8", PyLong_FromUnsignedLong(regs.r8));
    PyDict_SetItemString(res, "r9", PyLong_FromUnsignedLong(regs.r9));
    PyDict_SetItemString(res, "r10", PyLong_FromUnsignedLong(regs.r10));
    PyDict_SetItemString(res, "r11", PyLong_FromUnsignedLong(regs.r11));
    PyDict_SetItemString(res, "r12", PyLong_FromUnsignedLong(regs.r12));
    PyDict_SetItemString(res, "r13", PyLong_FromUnsignedLong(regs.r13));
    PyDict_SetItemString(res, "r14", PyLong_FromUnsignedLong(regs.r14));
    PyDict_SetItemString(res, "r15", PyLong_FromUnsignedLong(regs.r15));
    PyDict_SetItemString(res, "rip", PyLong_FromUnsignedLong(regs.rip));
    PyDict_SetItemString(res, "eflags", PyLong_FromUnsignedLong(regs.eflags));
    PyDict_SetItemString(res, "cs", PyLong_FromUnsignedLong(regs.cs));
    PyDict_SetItemString(res, "ss", PyLong_FromUnsignedLong(regs.ss));
    PyDict_SetItemString(res, "ds", PyLong_FromUnsignedLong(regs.ds));
    PyDict_SetItemString(res, "es", PyLong_FromUnsignedLong(regs.es));
    PyDict_SetItemString(res, "fs", PyLong_FromUnsignedLong(regs.fs));
    PyDict_SetItemString(res, "gs", PyLong_FromUnsignedLong(regs.gs));
    PyDict_SetItemString(res, "fs_base", PyLong_FromUnsignedLong(regs.fs_base));
    PyDict_SetItemString(res, "gs_base", PyLong_FromUnsignedLong(regs.gs_base));
    PyDict_SetItemString(res, "orig_rax", PyLong_FromUnsignedLong(regs.orig_rax));
    return res;
}

static PyObject *method_get_extended_regs(PyObject *self, PyObject *args)
{
    //TODO implement this function, using ptrace with PTRACE_GETREGSET and NT_X86_XSTATE
}

static PyObject *method_get_debug_regs(PyObject *self, PyObject *args)
{
    //TODO implement this function, using ptrace with PTRACE_GETREGSET and NT_X86_IOTRAP
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
    regs.rax = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rax"));
    regs.rbx = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rbx"));
    regs.rcx = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rcx"));
    regs.rdx = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rdx"));
    regs.rsi = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rsi"));
    regs.rdi = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rdi"));
    regs.rsp = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rsp"));
    regs.rbp = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rbp"));
    regs.r8 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r8"));
    regs.r9 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r9"));
    regs.r10 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r10"));
    regs.r11 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r11"));
    regs.r12 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r12"));
    regs.r13 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r13"));
    regs.r14 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r14"));
    regs.r15 = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "r15"));
    regs.rip = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "rip"));
    regs.eflags = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "eflags"));
    regs.cs = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "cs"));
    regs.ss = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "ss"));
    regs.ds = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "ds"));
    regs.es = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "es"));
    regs.fs = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "fs"));
    regs.gs = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "gs"));
    regs.fs_base = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "fs_base"));
    regs.gs_base = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "gs_base"));
    regs.orig_rax = PyLong_AsUnsignedLong(PyDict_GetItemString(regs_dict, "orig_rax"));
    struct iovec iov;
    iov.iov_base = &regs;
    iov.iov_len = sizeof(regs);
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
    //TODO implement this function, using ptrace with PTRACE_SETREGSET and NT_X86_XSTATE
}

static PyObject *method_set_debug_regs(PyObject *self, PyObject *args)
{
    //TODO implement this function, using ptrace with PTRACE_SETREGSET and NT_X86_IOTRAP
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
    {"get_debug_regs", method_get_debug_regs, METH_VARARGS, "ptrace call with PTRACE_GETREGSET on NT_X86_IOTRAP"},
    {"set_standard_regs", method_set_standard_regs, METH_VARARGS, "ptrace call with PTRACE_SETREGSET on NT_PRSTATUS"},
    {"set_extended_regs", method_set_extended_regs, METH_VARARGS, "ptrace call with PTRACE_SETREGSET on NT_X86_XSTATE"},
    {"set_debug_regs", method_set_debug_regs, METH_VARARGS, "ptrace call with PTRACE_SETREGSET on NT_X86_IOTRAP"},
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