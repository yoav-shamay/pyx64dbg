#include <pybind11/pybind11.h>
#include <stddef.h>
#include <system_error>
#include <errno.h>

#include "utils.hpp"

namespace py = pybind11;


void raise_errno_as_os_error()
{
    throw std::system_error(errno, std::generic_category());
}


py::bytes bytes_from_field(void *field_ptr, size_t field_size)
{
    return py::bytes(reinterpret_cast<const char *>(field_ptr), field_size);
}

void read_bytes_field_from_dict(py::dict dict, const std::string &key, void *destination, const size_t size)
{
    if (!dict.contains(key)) return; // if the key is not present, do nothing
    py::bytes val = dict[py::str(key)].cast<py::bytes>(); // get the value as py::bytes
    std::string s = py::cast<std::string>(val); // convert it to std::string to easily get the size and data pointer
    if (s.size() != size)
    {
            throw py::value_error(key + " must be exactly " + std::to_string(size) + " bytes");
    }
    memcpy(destination, s.data(), size); // use memcpy to copy the data to the destination buffer
}