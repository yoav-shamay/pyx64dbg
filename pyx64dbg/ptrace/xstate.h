#ifndef PYX64DBG_PTRACE_XSTATE_H
#define PYX64DBG_PTRACE_XSTATE_H

#include <Python.h>

int get_xstate_buffer_from_child(int child_pid, char **xstate_buffer_out, size_t *xstate_size_out);
int modify_xstate_buffer_from_dict(char *xstate_buffer, size_t xstate_size, PyObject *regs_dict);
void parse_xstate_buffer_to_dict(char *buffer, size_t size, PyObject *res_dict);

#endif