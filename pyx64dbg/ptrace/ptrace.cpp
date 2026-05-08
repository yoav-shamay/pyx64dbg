#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <sys/ptrace.h>
#include <sys/user.h>
#include <sys/uio.h>
#include <elf.h>
#include <vector>
#include <system_error>
#include <unistd.h>
#include <errno.h>
#include <string.h>

#include "utils.hpp"
#include "xstate.hpp"

namespace py = pybind11;

/*
Implementation of the traceme method for the python binding.
Gets no parameter and returns nothing.
calls ptrace with PTRACE_TRACEME.
*/
static void traceme()
{
    int res = ptrace(PTRACE_TRACEME, 0, NULL, NULL);
    if (res == -1)
        raise_errno_as_os_error();
}

/*
Implementation of the cont method for the python binding.
Gets the child process id and an optional signal number to be sent to the child process when continued, and returns nothing.
calls ptrace with PTRACE_CONT.
*/
static void cont(int child_pid, std::optional<long> signal)
{
    void *sig = nullptr;
    if (signal.has_value()) // cast the signal to void * if it has a value
    {
        long sig_number = *signal;                  // get the signal number from the optional
        sig = reinterpret_cast<void *>(sig_number); // cast the signal number to void *
    }
    long res = ptrace(PTRACE_CONT, child_pid, NULL, sig);
    if (res == -1)
        raise_errno_as_os_error();
}

/*
An implementation of the peekdata method for the python binding.
Gets the child process id and the address to peek, and returns the data at that address in the child process as a python integer.
calls ptrace with PTRACE_PEEKDATA.
*/
static unsigned long peekdata(int child_pid, uintptr_t address)
{
    errno = 0; // set errno to 0 so we can accurately tell if ptrace failed or if the data at the address is actually -1
    unsigned long res = ptrace(PTRACE_PEEKDATA, child_pid, (void *)address, NULL);
    if (errno != 0)
    {
        raise_errno_as_os_error();
    }
    return res;
}

/*
Implementation of the pokedata method for the python binding.
Gets the child process id, the address to poke and the data to poke, and returns nothing.
calls ptrace with PTRACE_POKEDATA.
*/
static void pokedata(int child_pid, uintptr_t address, unsigned long data)
{
    long res = ptrace(PTRACE_POKEDATA, child_pid, (void *)address, (void *)data);
    if (res == -1)
        raise_errno_as_os_error();
}

/*
Implementation of the single_step method for the python binding.
Gets the child process id and an optional signal number to be sent to the child process when continued, and returns nothing.
calls ptrace with PTRACE_SINGLESTEP.
*/
static void single_step(int child_pid, std::optional<long> signal)
{
    void *sig = nullptr;
    if (signal.has_value()) // if the signal has a value, cast it to void *
    {
        long s = *signal;
        sig = reinterpret_cast<void *>(s);
    }
    long res = ptrace(PTRACE_SINGLESTEP, child_pid, NULL, sig);
    if (res == -1)
        raise_errno_as_os_error();
}

/*
Implementation of the get_standard_regs method for the python binding.
Gets the child process id and returns a dict containing the standard registers of the child process.
The keys are python strings with the register names, and the values are bytes objects.
calls ptrace with PTRACE_GETREGSET on NT_PRSTATUS.
*/
static py::dict get_standard_regs(int child_pid)
{
    struct user_regs_struct regs;
    struct iovec iov;
    iov.iov_base = &regs;
    iov.iov_len = sizeof(regs);
    long ptrace_res = ptrace(PTRACE_GETREGSET, child_pid, (void *)NT_PRSTATUS, &iov);
    if (ptrace_res == -1)
        raise_errno_as_os_error();
    // create a dictionary with all fields of the regs struct, converted to strings (char *)
    py::dict res;
    res["rax"] = bytes_from_field(&regs.rax, sizeof(regs.rax));
    res["rbx"] = bytes_from_field(&regs.rbx, sizeof(regs.rbx));
    res["rcx"] = bytes_from_field(&regs.rcx, sizeof(regs.rcx));
    res["rdx"] = bytes_from_field(&regs.rdx, sizeof(regs.rdx));
    res["rsi"] = bytes_from_field(&regs.rsi, sizeof(regs.rsi));
    res["rdi"] = bytes_from_field(&regs.rdi, sizeof(regs.rdi));
    res["rsp"] = bytes_from_field(&regs.rsp, sizeof(regs.rsp));
    res["rbp"] = bytes_from_field(&regs.rbp, sizeof(regs.rbp));
    res["r8"] = bytes_from_field(&regs.r8, sizeof(regs.r8));
    res["r9"] = bytes_from_field(&regs.r9, sizeof(regs.r9));
    res["r10"] = bytes_from_field(&regs.r10, sizeof(regs.r10));
    res["r11"] = bytes_from_field(&regs.r11, sizeof(regs.r11));
    res["r12"] = bytes_from_field(&regs.r12, sizeof(regs.r12));
    res["r13"] = bytes_from_field(&regs.r13, sizeof(regs.r13));
    res["r14"] = bytes_from_field(&regs.r14, sizeof(regs.r14));
    res["r15"] = bytes_from_field(&regs.r15, sizeof(regs.r15));
    res["rip"] = bytes_from_field(&regs.rip, sizeof(regs.rip));
    res["eflags"] = bytes_from_field(&regs.eflags, sizeof(regs.eflags));
    res["cs"] = bytes_from_field(&regs.cs, sizeof(regs.cs));
    res["ss"] = bytes_from_field(&regs.ss, sizeof(regs.ss));
    res["ds"] = bytes_from_field(&regs.ds, sizeof(regs.ds));
    res["es"] = bytes_from_field(&regs.es, sizeof(regs.es));
    res["fs"] = bytes_from_field(&regs.fs, sizeof(regs.fs));
    res["gs"] = bytes_from_field(&regs.gs, sizeof(regs.gs));
    res["fs_base"] = bytes_from_field(&regs.fs_base, sizeof(regs.fs_base));
    res["gs_base"] = bytes_from_field(&regs.gs_base, sizeof(regs.gs_base));
    res["orig_rax"] = bytes_from_field(&regs.orig_rax, sizeof(regs.orig_rax));
    return res;
}
/*
Implementation of the get_extended_regs method for the python binding.
Gets the child process id and returns a dict containing the extended registers of the child process.
Currently only contains the legacy region and YMM registers, can be extended to contain more registers in the future if needed.
The keys are python strings with the register names, and the values are bytes objects.
calls ptrace with PTRACE_GETREGSET on NT_X86_XSTATE.
*/
static py::dict get_extended_regs(int child_pid)
{
    std::string buffer = get_xstate_buffer_from_child(child_pid); // get the buffer using an helper function
    py::dict res = parse_xstate_buffer_to_dict(buffer); // parse it to a dict using the helper method
    return res;
}

/*
Implementation of the set_standard_regs method for the python binding.
Gets the child process id and a dict containing the standard registers to be set in the child process, and returns nothing.
The keys of the dict are python strings with the register names, and the values are bytes objects with the register values.
Can contain any subset of registers (as it will first get the current ones and just then modify).
calls ptrace with PTRACE_SETREGSET on NT_PRSTATUS.
*/
static void set_standard_regs(int child_pid, py::dict regs_dict)
{
    struct user_regs_struct regs;
    struct iovec iov;
    iov.iov_base = &regs;
    iov.iov_len = sizeof(regs);
    if (ptrace(PTRACE_GETREGSET, child_pid, (void *)NT_PRSTATUS, &iov) == -1)
        raise_errno_as_os_error();

    read_bytes_field_from_dict(regs_dict, "rax", &regs.rax, sizeof(regs.rax));
    read_bytes_field_from_dict(regs_dict, "rbx", &regs.rbx, sizeof(regs.rbx));
    read_bytes_field_from_dict(regs_dict, "rcx", &regs.rcx, sizeof(regs.rcx));
    read_bytes_field_from_dict(regs_dict, "rdx", &regs.rdx, sizeof(regs.rdx));
    read_bytes_field_from_dict(regs_dict, "rsi", &regs.rsi, sizeof(regs.rsi));
    read_bytes_field_from_dict(regs_dict, "rdi", &regs.rdi, sizeof(regs.rdi));
    read_bytes_field_from_dict(regs_dict, "rsp", &regs.rsp, sizeof(regs.rsp));
    read_bytes_field_from_dict(regs_dict, "rbp", &regs.rbp, sizeof(regs.rbp));
    read_bytes_field_from_dict(regs_dict, "r8", &regs.r8, sizeof(regs.r8));
    read_bytes_field_from_dict(regs_dict, "r9", &regs.r9, sizeof(regs.r9));
    read_bytes_field_from_dict(regs_dict, "r10", &regs.r10, sizeof(regs.r10));
    read_bytes_field_from_dict(regs_dict, "r11", &regs.r11, sizeof(regs.r11));
    read_bytes_field_from_dict(regs_dict, "r12", &regs.r12, sizeof(regs.r12));
    read_bytes_field_from_dict(regs_dict, "r13", &regs.r13, sizeof(regs.r13));
    read_bytes_field_from_dict(regs_dict, "r14", &regs.r14, sizeof(regs.r14));
    read_bytes_field_from_dict(regs_dict, "r15", &regs.r15, sizeof(regs.r15));
    read_bytes_field_from_dict(regs_dict, "rip", &regs.rip, sizeof(regs.rip));
    read_bytes_field_from_dict(regs_dict, "eflags", &regs.eflags, sizeof(regs.eflags));
    read_bytes_field_from_dict(regs_dict, "cs", &regs.cs, sizeof(regs.cs));
    read_bytes_field_from_dict(regs_dict, "ss", &regs.ss, sizeof(regs.ss));
    read_bytes_field_from_dict(regs_dict, "ds", &regs.ds, sizeof(regs.ds));
    read_bytes_field_from_dict(regs_dict, "es", &regs.es, sizeof(regs.es));
    read_bytes_field_from_dict(regs_dict, "fs", &regs.fs, sizeof(regs.fs));
    read_bytes_field_from_dict(regs_dict, "gs", &regs.gs, sizeof(regs.gs));
    read_bytes_field_from_dict(regs_dict, "fs_base", &regs.fs_base, sizeof(regs.fs_base));
    read_bytes_field_from_dict(regs_dict, "gs_base", &regs.gs_base, sizeof(regs.gs_base));
    read_bytes_field_from_dict(regs_dict, "orig_rax", &regs.orig_rax, sizeof(regs.orig_rax));
    long res = ptrace(PTRACE_SETREGSET, child_pid, (void *)NT_PRSTATUS, &iov);
    if (res == -1)
        raise_errno_as_os_error();
}
/*
Implementation of the set_extended_regs method for the python binding.
Gets the child process id and a dict containing the extended registers to be set in the child process, and returns nothing.
The keys of the dict are python strings with the register names, and the values are bytes objects with the register values.
Currently only supports the legacy region and YMM registers, can be extended to support more registers in the future if needed.
Can contain any subset of registers (as it will first get the current ones and just then modify).
calls ptrace with PTRACE_SETREGSET on NT_X86_XSTATE.
*/
static void set_extended_regs(int child_pid, py::dict regs_dict)
{
    // get the xstate buffer from the child process using the helper method
    std::string xstate_buffer = get_xstate_buffer_from_child(child_pid);
    // modify the xstate buffer according to the dict using helper function
    modify_xstate_buffer_from_dict(xstate_buffer, regs_dict);
    // use ptrace to write the modified xstate buffer back to the child process
    struct iovec iov;
    iov.iov_base = xstate_buffer.data();
    iov.iov_len = xstate_buffer.size();
    long res = ptrace(PTRACE_SETREGSET, child_pid, (void *)NT_X86_XSTATE, &iov);
    if (res == -1)
        raise_errno_as_os_error();
}

/*
Implementation of the get_memory_range method for the python binding.
Gets the child process id, the start address and the length of the memory range to read, and returns the data in that memory range as a bytes object.
calls process_vm_readv to read the memory range from the child process.
*/
static py::bytes get_memory_range(int child_pid, uintptr_t address, size_t length)
{
    // allocate a local buffer of the requested size
    std::vector<char> buf(length);
    // local iov - output buffer
    struct iovec local_iov[1];
    local_iov[0].iov_base = (void *)buf.data();
    local_iov[0].iov_len = length;
    // remote iov - address pointer in the child process
    struct iovec remote_iov[1];
    remote_iov[0].iov_base = (void *)address;
    remote_iov[0].iov_len = length;
    ssize_t nread = process_vm_readv(child_pid, local_iov, 1, remote_iov, 1, 0);
    if (nread == -1) // if we got -1, throw an error
    {
        raise_errno_as_os_error();
    }
    if (nread < (ssize_t)length) // if we read less than the requested length, also throw an error (though this time errno won't reflect an error)
    {
        throw std::runtime_error("Could not read the entire memory range from the child process");
    }
    py::bytes res(buf.data(), length); // create bytes from res buffer
    return res;
}

/*
Implementation of the write_memory_range method for the python binding.
Gets the child process id, the start address and a bytes object containing the data to write,and returns nothing.
calls process_vm_writev to write the memory range to the child process.
*/
static void write_memory_range(int child_pid, size_t address, std::string data)
{
    // local iov - buffer containing the data to write
    struct iovec local_iov[1];
    local_iov[0].iov_base = const_cast<char *>(data.data());
    local_iov[0].iov_len = data.size();
    // remote iov - address pointer in the child process
    struct iovec remote_iov[1];
    remote_iov[0].iov_base = (void *)address;
    remote_iov[0].iov_len = data.size();
    ssize_t nwritten = process_vm_writev(child_pid, local_iov, 1, remote_iov, 1, 0);
    if (nwritten == -1) // if we got -1, throw an error
    {
        raise_errno_as_os_error();
    }
    if (nwritten < (ssize_t)data.size()) // if we wrote less than the requested length, also throw an error (though this time errno won't reflect an error)
    {
        throw std::runtime_error("Could not write the entire memory range to the child process");
    }
}
/*
Implementation of the kill method for the python binding.
Gets the child process id and returns nothing.
calls ptrace with PTRACE_KILL to kill the child process.
*/
static void kill_child(int child_pid)
{
    long res = ptrace(PTRACE_KILL, child_pid, NULL, NULL);
    if (res == -1)
        raise_errno_as_os_error();
}

PYBIND11_MODULE(ptrace, m)
{
    m.doc() = "C++ ptrace wrapper";
    m.def("traceme", &traceme, "ptrace call with PTRACE_TRACEME");
    m.def("cont", &cont, "ptrace call with PTRACE_CONT", py::arg("child_pid"), py::arg("signal") = py::none());
    m.def("peekdata", &peekdata, "ptrace call with PTRACE_PEEKDATA");
    m.def("pokedata", &pokedata, "ptrace call with PTRACE_POKEDATA");
    m.def("single_step", &single_step, "ptrace call with PTRACE_SINGLESTEP", py::arg("child_pid"), py::arg("signal") = py::none());
    m.def("get_standard_regs", &get_standard_regs, "ptrace call with PTRACE_GETREGSET on NT_PRSTATUS");
    m.def("get_extended_regs", &get_extended_regs, "ptrace call with PTRACE_GETREGSET on NT_X86_XSTATE");
    m.def("set_standard_regs", &set_standard_regs, "ptrace call with PTRACE_SETREGSET on NT_PRSTATUS");
    m.def("set_extended_regs", &set_extended_regs, "ptrace call with PTRACE_SETREGSET on NT_X86_XSTATE");
    m.def("get_memory_range", &get_memory_range, "read memory range of the child process using process_vm_readv");
    m.def("write_memory_range", &write_memory_range, "write memory range of the child process using process_vm_writev");
    m.def("kill", &kill_child, "ptrace call with PTRACE_KILL");
}
