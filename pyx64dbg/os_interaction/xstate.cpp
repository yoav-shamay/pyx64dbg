#include <pybind11/pybind11.h>
#include <elf.h>
#include <cpuid.h>
#include <stdint.h>
#include <sys/ptrace.h>
#include <sys/uio.h>
#include <stdint.h>
#include <stdio.h>
#include <string>

#include "xstate.hpp"
#include "utils.hpp"

namespace py = pybind11;

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

/* The XSAVE header offset is fixed at 512 bytes in the area. */
constexpr size_t XSAVE_HEADER_OFFSET = 512;

/*
An utility function to get the offset of an xstate component in the xstate buffer, given its component id.
It uses the CPUID instruction with leaf 0xD and the component id as subleaf to get the offset from the EBX register.
*/
uint32_t get_offset(int component_id)
{
    uint32_t eax, ebx, ecx, edx;
    __cpuid_count(0x0D, component_id, eax, ebx, ecx, edx);
    return ebx;
}

/*
An utility function to get the maximum size of the xstate buffer output from ptrace.
Uses the CPUID instruction with leaf 0xD and subleaf 0 to get the size from the EBX register.
*/
uint32_t get_max_xsave_size() {
    uint32_t eax, ebx, ecx, edx;
    // Leaf 0xD, Sub-leaf 0: EBX returns the max size required by all supported features in the current XCR0.
    __cpuid_count(0x0D, 0, eax, ebx, ecx, edx);
    return ebx;
}

std::string get_xstate_buffer_from_child(int child_pid)
{
    size_t xstate_size = get_max_xsave_size();
    std::string xstate_buffer(xstate_size, '\0'); // allocate a buffer of the maximum size
    // create an iov and use ptrace getregset to fill the buffer
    struct iovec iov;
    iov.iov_base = (void *)xstate_buffer.data();
    iov.iov_len = xstate_size;
    long ptrace_res = ptrace(PTRACE_GETREGSET, child_pid, NT_X86_XSTATE, &iov);
    if (ptrace_res == -1)
    {
        raise_errno_as_os_error();
    }
    xstate_buffer.resize(iov.iov_len); // resize the string to the actual size of the data read
    return xstate_buffer;
}

void modify_xstate_buffer_from_dict(std::string &xstate_buffer, const py::dict &regs_dict)
{
    // verify the buffer is large enough to hold the legavy region
    if (xstate_buffer.size() < sizeof(xstate_legacy_region)) {
        throw std::runtime_error("XSAVE buffer too small for legacy region");
    }
    // convert the data to a xstate_legacy_region struct
    xstate_legacy_region *legacy_region = (xstate_legacy_region *)xstate_buffer.data();
    // write the legacy region from the dict
    read_bytes_field_from_dict(regs_dict, "fcw", &legacy_region->fcw, sizeof(legacy_region->fcw));
    read_bytes_field_from_dict(regs_dict, "fsw", &legacy_region->fsw, sizeof(legacy_region->fsw));
    read_bytes_field_from_dict(regs_dict, "ftw", &legacy_region->ftw, sizeof(legacy_region->ftw));
    read_bytes_field_from_dict(regs_dict, "fop", &legacy_region->fop, sizeof(legacy_region->fop));
    read_bytes_field_from_dict(regs_dict, "fip", &legacy_region->fip, sizeof(legacy_region->fip));
    read_bytes_field_from_dict(regs_dict, "fdp", &legacy_region->fdp, sizeof(legacy_region->fdp));
    read_bytes_field_from_dict(regs_dict, "mxcsr", &legacy_region->mxcsr, sizeof(legacy_region->mxcsr));
    read_bytes_field_from_dict(regs_dict, "mxcsr_mask", &legacy_region->mxcsr_mask, sizeof(legacy_region->mxcsr_mask));
    // use a loop with snprintf for the st_mm registers as they are equivalent except for index
    for (int i = 0; i < 8; i++)
    {
        std::string st_mm_key = "st_mm" + std::to_string(i);
        read_bytes_field_from_dict(regs_dict, st_mm_key, legacy_region->st_mm[i].st_mm, sizeof(legacy_region->st_mm[i].st_mm));
    }
    // similarly use a loop for xmm
    for (int i = 0; i < 16; i++)
    {
        std::string xmm_key = "xmm" + std::to_string(i);
        read_bytes_field_from_dict(regs_dict, xmm_key, legacy_region->xmm[i], sizeof(legacy_region->xmm[i]));
    }
    // xsave header - contains what fields are present
    // verify the buffer is large enough
    if (xstate_buffer.size() < XSAVE_HEADER_OFFSET + sizeof(xsave_header)) {
        throw std::runtime_error("XSAVE buffer too small for xsave header");
    }
    struct xsave_header *xsave_hdr = (struct xsave_header *)(xstate_buffer.data() + XSAVE_HEADER_OFFSET);
    uint64_t xstate_bv = xsave_hdr->xstate_bv;
    if (xstate_bv & (1 << 2)) // if the AVX state bit is on (if it's present)
    {
        // verify the buffer is large enough
        if (xstate_buffer.size() < get_offset(2) + sizeof(avx_state)) {
            throw std::runtime_error("XSAVE buffer too small for AVX state");
        }
        struct avx_state *avx = (struct avx_state *)(xstate_buffer.data() + get_offset(2)); // get the avx state at the offset given from the helper method
        // use a loop to get all ymm registers, similar to xmm and st_mm
        for (int i = 0; i < 16; i++)
        {
            std::string ymmh_key = "ymm" + std::to_string(i) + "_h";
            read_bytes_field_from_dict(regs_dict, ymmh_key, avx->ymm_h[i], sizeof(avx->ymm_h[i]));
        }
    }
}

py::dict parse_xstate_buffer_to_dict(std::string &buffer)
{
    py::dict res_dict;
    // legacy region parsing
    // verify the buffer is large enough to hold the legavy region
    if (buffer.size() < sizeof(xstate_legacy_region)) {
        throw std::runtime_error("XSAVE buffer too small for legacy region");
    }
    struct xstate_legacy_region *legacy_region = (struct xstate_legacy_region *)buffer.data();
    res_dict["fcw"] = bytes_from_field(legacy_region->fcw, sizeof(legacy_region->fcw));
    res_dict["fsw"] = bytes_from_field(legacy_region->fsw, sizeof(legacy_region->fsw));
    res_dict["ftw"] = bytes_from_field(legacy_region->ftw, sizeof(legacy_region->ftw));
    res_dict["fop"] = bytes_from_field(legacy_region->fop, sizeof(legacy_region->fop));
    res_dict["fip"] = bytes_from_field(legacy_region->fip, sizeof(legacy_region->fip));
    res_dict["fdp"] = bytes_from_field(legacy_region->fdp, sizeof(legacy_region->fdp));
    res_dict["mxcsr"] = bytes_from_field(legacy_region->mxcsr, sizeof(legacy_region->mxcsr));
    res_dict["mxcsr_mask"] = bytes_from_field(legacy_region->mxcsr_mask, sizeof(legacy_region->mxcsr_mask));
    // use a loop with snprintf for the st_mm registers as they are equivalent except for index
    for (int i = 0; i < 8; i++)
    {
        std::string st_mm_key = "st_mm" + std::to_string(i);
        res_dict[st_mm_key.data()] = bytes_from_field(legacy_region->st_mm[i].st_mm, sizeof(legacy_region->st_mm[i].st_mm));
    }
    // similarly use a loop for xmm
    for (int i = 0; i < 16; i++)
    {
        std::string xmm_key = "xmm" + std::to_string(i);
        res_dict[xmm_key.data()] = bytes_from_field(legacy_region->xmm[i], sizeof(legacy_region->xmm[i]));
    }
    // xsave header - contains what fields are present
    // verify the buffer is large enough
    if (buffer.size() < XSAVE_HEADER_OFFSET + sizeof(xsave_header)) {
        throw std::runtime_error("XSAVE buffer too small for xsave header");
    }
    struct xsave_header *xsave_hdr = (struct xsave_header *)(buffer.data() + XSAVE_HEADER_OFFSET);
    uint64_t xstate_bv = xsave_hdr->xstate_bv;
    if (xstate_bv & (1 << 2)) // if the AVX state bit is on (if it's present)
    {
        // verify the buffer is large enough
        if (buffer.size() < get_offset(2) + sizeof(avx_state)) {
            throw std::runtime_error("XSAVE buffer too small for AVX state");
        }
        struct avx_state *avx = (struct avx_state *)(buffer.data() + get_offset(2)); // get the avx state at the offset given from the helper method
        // use a loop to get all ymm registers, similar to xmm and st_mm
        for (int i = 0; i < 16; i++)
        {
            std::string ymmh_key = "ymm" + std::to_string(i) + "_h";
            res_dict[ymmh_key.data()] = bytes_from_field(avx->ymm_h[i], sizeof(avx->ymm_h[i]));
        }
    }
    return res_dict;
}
