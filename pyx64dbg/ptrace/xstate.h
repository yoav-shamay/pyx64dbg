#ifndef PYX64DBG_PTRACE_XSTATE_H
#define PYX64DBG_PTRACE_XSTATE_H

#include <Python.h>
/*
An utility function to get the xstate buffer of the child process using ptrace, given the child process id.
The buffer is allocated in this function and needs to be freed by the caller
Returns 0 on success and -1 on failure, and sets a python exception on failure.
Returns the buffer and its size in the output parameters (pointers).
*/
int get_xstate_buffer_from_child(int child_pid, char **xstate_buffer_out, size_t *xstate_size_out);
/*
An utility function to modify the xstate buffer given a dict containing the registers to be modified and their new values.
The keys of the dict are python strings with the register names, and the values are bytes objects with the register values.
Can contain any subset of registers (as it will first get the current ones and just then modify).
Returns 0 on success and -1 on failure, and sets a python exception on failure.
Does it in-place on the given buffer.
*/
int modify_xstate_buffer_from_dict(char *xstate_buffer, size_t xstate_size, PyObject *regs_dict);
/*
An utility function to parse the xstate buffer and populate a python dictionary with the register values.
The keys of the dict are python strings with the register names, and the values are bytes objects with the register values.
Returns nothing.
Puts the output in the res_dict parameter.
*/
void parse_xstate_buffer_to_dict(char *buffer, size_t size, PyObject *res_dict);

#endif