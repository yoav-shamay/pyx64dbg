#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <elf.h>
#include <cpuid.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <sys/uio.h>
#include <stdio.h>
#include <string.h>

#include "utils.h"
/*
A struct to hold a single st/mm register part of the legacy region.
This part is 10 bytes long with 6 bytes padding.
This allows making an array of st_mm registers without worrying about the padding between them.
*/
struct st_mm_reg
{
    uint8_t st_mm[10];
    uint8_t rsv[6];
};

/*
A struct to parse the legacy region of the xstate area. It contains the x87 FPU registers and the XMM registers.
Taken from Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, section 13.4.1 "Legacy Region of an XSAVE Area".
*/
struct xstate_legacy_region
{
    uint8_t fcw[2];
    uint8_t fsw[2];
    uint8_t ftw[1];
    uint8_t _rsv_1[1];
    uint8_t fop[2];
    uint8_t fip[8];
    uint8_t fdp[8];
    uint8_t mxcsr[4];
    uint8_t mxcsr_mask[4];
    struct st_mm_reg st_mm[8];
    uint8_t xmm[16][16];
};

/*
A struct to parse the header part of the xstate area.
Contains information about the present extended state components and their offsets in the buffer.
Taken from Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, Section 13.4.2, "XSAVE Header"
*/
struct xsave_header
{
    uint64_t xstate_bv;
    uint64_t xcomp_bv;
    uint64_t reserved[6];
};

/*
A struct to parse the AVX state component of the xstate area, which contains the upper parts of the YMM registers.
Taken from Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, Section 13.5.3, "AVX State".
Contains an array of 16 128-bit ymm_h registers.
*/
struct avx_state
{
    uint8_t ymm_h[16][16];
};

/*
An utility function to get the offset of an xstate component in the xstate buffer, given its component id.
It uses the CPUID instruction with leaf 0xD and the component id as subleaf to get the offset from the EBX register.
*/
static uint32_t get_offset(int component_id)
{
    uint32_t eax, ebx, ecx, edx;
    __cpuid_count(0x0D, component_id, eax, ebx, ecx, edx);
    return ebx;
}

// The offset of the XSAVE Header in the xstate buffer. Always 512.
#define XSAVE_HEADER_OFFSET 512

void parse_xstate_buffer_to_dict(char *buffer, size_t size, PyObject *res_dict)
{
    // take all registers from the legacy region
    struct xstate_legacy_region *legacy_region = (struct xstate_legacy_region *)buffer;
    PyDict_SetItemString(res_dict, "fcw", PyBytes_FromStringAndSize((char *)legacy_region->fcw, 2));
    PyDict_SetItemString(res_dict, "fsw", PyBytes_FromStringAndSize((char *)legacy_region->fsw, 2));
    PyDict_SetItemString(res_dict, "ftw", PyBytes_FromStringAndSize((char *)legacy_region->ftw, 2));
    PyDict_SetItemString(res_dict, "fop", PyBytes_FromStringAndSize((char *)legacy_region->fop, 8));
    PyDict_SetItemString(res_dict, "fip", PyBytes_FromStringAndSize((char *)legacy_region->fip, 8));
    PyDict_SetItemString(res_dict, "fdp", PyBytes_FromStringAndSize((char *)legacy_region->fdp, 8));
    PyDict_SetItemString(res_dict, "mxcsr", PyBytes_FromStringAndSize((char *)legacy_region->mxcsr, 4));
    PyDict_SetItemString(res_dict, "mxcsr_mask", PyBytes_FromStringAndSize((char *)legacy_region->mxcsr_mask, 4));
    // for the st/mm registers, we use a loop with sprintf to generate the dictionary keys, as there are 8 of them.
    for (int i = 0; i < 8; i++)
    {
        char st_key[16];
        snprintf(st_key, sizeof(st_key), "st_mm%d", i);
        PyDict_SetItemString(res_dict, st_key, PyBytes_FromStringAndSize((char *)legacy_region->st_mm[i].st_mm, 10));
    }
    // for the the xmm registers we also use a loop
    for (int i = 0; i < 16; i++)
    {
        char xmm_key[16];
        snprintf(xmm_key, sizeof(xmm_key), "xmm%d", i);
        PyDict_SetItemString(res_dict, xmm_key, PyBytes_FromStringAndSize((char *)legacy_region->xmm[i], 16));
    }
    // parse the xsave header to check which extended state components are present
    struct xsave_header *xsave_hdr = (struct xsave_header *)(buffer + XSAVE_HEADER_OFFSET);
    uint64_t xstate_bv = xsave_hdr->xstate_bv;
    if (xstate_bv & (1 << 2)) // AVX state bit - on means it's present
    {
        // This component is numbered 2. use get_offset to get its offset.
        struct avx_state *avx = (struct avx_state *)(buffer + get_offset(2));
        // Use a loop with sprintf to print the keys as there are 16 identical ymmh registers (high bits of the ymm registers, the low ones are in xmm)
        for (int i = 0; i < 16; i++)
        {
            char ymmh_key[16];
            snprintf(ymmh_key, sizeof(ymmh_key), "ymm%d_h", i);
            PyDict_SetItemString(res_dict, ymmh_key, PyBytes_FromStringAndSize((char *)avx->ymm_h[i], 16));
        }
    }
    // only the legacy region and AVX are handled for now, but more can be added here in the future
}

/*
An utility function to get the maximum size of the xstate buffer output from ptrace.
Uses the CPUID instruction with leaf 0xD and subleaf 0 to get the size from the EBX register.
*/
static uint32_t get_max_xsave_size() {
    uint32_t eax, ebx, ecx, edx;
    // Leaf 0xD, Sub-leaf 0: EBX returns the max size required by all supported features in the current XCR0.
    __cpuid_count(0x0D, 0, eax, ebx, ecx, edx);
    return ebx;
}

int get_xstate_buffer_from_child(int child_pid, char **xstate_buffer_out, size_t *xstate_size_out)
{
    size_t xstate_size = get_max_xsave_size();
    char *xstate_buffer = malloc(xstate_size); // allocate a buffer of the maximum possible size
    if (xstate_buffer == NULL)
    {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    // create an iov and use ptrace getregset to fill the buffer
    struct iovec iov;
    iov.iov_base = xstate_buffer;
    iov.iov_len = xstate_size;
    long ptrace_res = ptrace(PTRACE_GETREGSET, child_pid, NT_X86_XSTATE, &iov);
    if (ptrace_res == -1)
    {
        free(xstate_buffer); // free the buffer in case of an error, as we don't return it
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    // place the outputs in the output parameters and return success
    *xstate_buffer_out = xstate_buffer;
    *xstate_size_out = xstate_size;
    return 0;
}

int modify_xstate_buffer_from_dict(char *xstate_buffer, size_t xstate_size, PyObject *regs_dict)
{
    // legacy region parsing and modifications - use read_bytes_field_from_dict for easy parsing, always check for errors and return -1
    struct xstate_legacy_region *legacy_region = (struct xstate_legacy_region *)xstate_buffer;
    if (read_bytes_field_from_dict(regs_dict, "fcw", &legacy_region->fcw, sizeof(legacy_region->fcw)) == -1) return -1;
    if (read_bytes_field_from_dict(regs_dict, "fsw", &legacy_region->fsw, sizeof(legacy_region->fsw)) == -1) return -1;
    if (read_bytes_field_from_dict(regs_dict, "ftw", &legacy_region->ftw, sizeof(legacy_region->ftw)) == -1) return -1;
    if (read_bytes_field_from_dict(regs_dict, "fop", &legacy_region->fop, sizeof(legacy_region->fop)) == -1) return -1;
    if (read_bytes_field_from_dict(regs_dict, "fip", &legacy_region->fip, sizeof(legacy_region->fip)) == -1) return -1;
    if (read_bytes_field_from_dict(regs_dict, "fdp", &legacy_region->fdp, sizeof(legacy_region->fdp)) == -1) return -1;
    if (read_bytes_field_from_dict(regs_dict, "mxcsr", &legacy_region->mxcsr, sizeof(legacy_region->mxcsr)) == -1) return -1;
    if (read_bytes_field_from_dict(regs_dict, "mxcsr_mask", &legacy_region->mxcsr_mask, sizeof(legacy_region->mxcsr_mask)) == -1) return -1;
    // Use a loop with sprintf for the keys for the repeating st/mm registers
    for (int i = 0; i < 8; i++)
    {
        char st_key[16];
        snprintf(st_key, sizeof(st_key), "st_mm%d", i);
        if (read_bytes_field_from_dict(regs_dict, st_key, &legacy_region->st_mm[i].st_mm, sizeof(legacy_region->st_mm[i].st_mm)) == -1)
            return -1;
    }
    // same for xmm registers
    for (int i = 0; i < 16; i++)
    {
        char xmm_key[16];
        snprintf(xmm_key, sizeof(xmm_key), "xmm%d", i);
        if (read_bytes_field_from_dict(regs_dict, xmm_key, &legacy_region->xmm[i], sizeof(legacy_region->xmm[i])) == -1)
            return -1;
    }
    // parse the xsave header to check which components are present before modifying them
    struct xsave_header *xsave_hdr = (struct xsave_header *)(xstate_buffer + XSAVE_HEADER_OFFSET);
    uint64_t xstate_bv = xsave_hdr->xstate_bv;
    if (xstate_bv & (1 << 2)) // AVX state bit - on means it's present, so we can try to modify it if needed
    {
        // get the avx state struct using get_offset to get the correct offset
        struct avx_state *avx = (struct avx_state *)(xstate_buffer + get_offset(2));
        // Use a loop to modify all identical ymmh registers, with sprintf for the keys
        for (int i = 0; i < 16; i++)
        {
            char ymmh_key[16];
            snprintf(ymmh_key, sizeof(ymmh_key), "ymm%d_h", i);
            if (read_bytes_field_from_dict(regs_dict, ymmh_key, &avx->ymm_h[i], sizeof(avx->ymm_h[i])) == -1)
                return -1;
        }
    }
    // only the legacy region and AVX are handled for now, but more can be added here in the future
    return 0;
}