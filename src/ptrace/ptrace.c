#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <sys/ptrace.h>
#include <sys/user.h>
#include <sys/uio.h>


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
    if (!PyArg_ParseTuple(args, "i", &child_pid))
    {
        return NULL;
    }
    int res = ptrace(PTRACE_CONT, child_pid, NULL, NULL);
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
    int res = ptrace(PTRACE_PEEKDATA, child_pid, (void *)address, NULL);
    if (errno == 0)
    {
        return PyLong_FromLong(res);
    }
    else
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
}

static PyObject *method_pokedata(PyObject *self, PyObject *args)
{
    int child_pid, data;
    size_t address;
    if (!PyArg_ParseTuple(args, "iki", &child_pid, &address, &data))
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

static PyObject *method_getregs(PyObject *self, PyObject *args)
{

}

static PyObject *method_setregs(PyObject *self, PyObject *args)
{

}

static PyObject *method_single_step(PyObject *self, PyObject *args)
{
    int child_pid;
    if (!PyArg_ParseTuple(args, "i", &child_pid))
    {
        return NULL;
    }
    int res = ptrace(PTRACE_SINGLESTEP, child_pid, NULL, NULL);
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
    {"getregs", method_getregs, METH_VARARGS, "ptrace call with PTRACE_GETREGS"},
    {"setregs", method_setregs, METH_VARARGS, "ptrace call with PTRACE_SETREGS"},
    {"single_step", method_single_step, METH_VARARGS, "ptrace call with PTRACE_SINGLESTEP"},
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