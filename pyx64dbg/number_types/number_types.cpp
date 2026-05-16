#include <pybind11/pybind11.h>
#include <pybind11/operators.h>
#include <functional>
#include <algorithm>
#include <string>
#include <cstring>
#include <type_traits>
#include <limits>

namespace py = pybind11;

/*
In C++, long double is considered to be 16 bytes.
But it is 10 bytes with 6 bytes of padding in x86-64 so we want to treat it like this
So we create a true_size method for true sizeof()
*/
template<class T>
int true_size()
{
    if constexpr (std::is_same_v<T, long double>) return 10;
    return sizeof(T);
}

/*
An enum of all supported CNums, used as unique identifier.
*/
enum CNumTypeID {
    INT8 = 0, UINT8 = 1,
    INT16 = 2, UINT16 = 3,
    INT32 = 4, UINT32 = 5,
    INT64 = 6, UINT64 = 7,
    FLOAT32 = 8, FLOAT64 = 9, FLOAT80 = 10
};

/*
A non-templated base class for all CNum types.
This allows performing generic operations on CNum types without knowing the actual object.
*/
struct CNumBase {
    // define a virtual destructor to prevent UB when deleting derived classes through a pointer to CNumBase
    virtual ~CNumBase() = default;
    // returns arithmetic priority
    virtual int priority() const = 0;
    // returns size in bytes
    virtual size_t size() const = 0;
    // returns whether the type is signed or not
    virtual bool is_signed() const = 0;
    // ID for determining the type from an instance
    virtual CNumTypeID type_id() const = 0;
    // converts to a python object
    virtual py::object as_python_object() const = 0;

    // returns the number as int64_t, for easy type conversion
    virtual int64_t as_integer() const = 0;
    // returns the number as long double, for easy type conversion
    virtual long double as_float() const = 0;
};

/*
Base classes for specific categories of C numeric types.
This allows Python to distinguish between C-style integers and floats.
*/
struct CIntBase : public CNumBase {};
struct CFloatBase : public CNumBase {};

/*
A templated CNum class that represents a C numeric type.
Inherits from CNumBase and implements the virtual methods.
The template parameter T is the actual C type (e.g. int32_t, float, etc.).
Requires priority and type_id to initialize, which is used for operator dispatching.
*/
template <typename T>
struct CNum : public std::conditional_t<std::is_floating_point_v<T>, CFloatBase, CIntBase> {
    T value;
    int _priority; // priority in arithmetic operations
    CNumTypeID _id;
    CNum(T v, int p, CNumTypeID id) : value(v), _priority(p), _id(id) {}

    int priority() const override
    {
        return _priority;
    }
    size_t size() const override
    {
        return true_size<T>(); // use true_size to determine size of class in bytes
    }
    bool is_signed() const override
    {
        return std::is_signed_v<T>; // use type traits to determine if the type is signed
    }
    CNumTypeID type_id() const override
    {
        return _id;
    }
    py::object as_python_object() const override
    {
        return py::cast(value);
    }
    int64_t as_integer() const override
    {
        return static_cast<int64_t>(value);
    }
    long double as_float() const override
    {
        return static_cast<long double>(value);
    }
};

/*
An helper to generate T from a python object, with proper handling of CNum types and Python built-in numeric types.
*/
template <typename T>
T py_object_to_cpp_type(py::handle h) {
    // if we are given a CNum type, don't go through python types - extract as the type we want and cast it.
    if (py::isinstance<CNumBase>(h)) {
        if constexpr(std::is_floating_point_v<T>) {
            return static_cast<T>(py::cast<CNumBase*>(h)->as_float());
        }
        else
        {
            return static_cast<T>(py::cast<CNumBase*>(h)->as_integer());
        }
    }
    if (py::isinstance<py::float_>(h))
    {
        // if it's a python float, we just convert it to double (as it's the same type) without worries
        return static_cast<T>(py::cast<double>(h));
    }

    if (py::isinstance<py::int_>(h))
    {
        if constexpr(std::is_floating_point_v<T>)
        {
            // If we are a floating point type, we'll try to cast it directly from python (except for long double)
            if constexpr(std::is_same_v<T, long double>)
            {
                // for long doubles, pybind doesn't support casting directly, so we'll convert it to string first
                std::string s = py::str(h).cast<std::string>();
                // we'll use strtold as it correctly handles inf/-inf
                return std::strtold(s.c_str(), nullptr);
            }
            else
            {
                try {
                    return py::cast<T>(h);
                } catch (py::cast_error& e) {
                    // A casting error for float / double can only be caused by overflow, so we'll check the sign and return the appropriate infinity
                    if (h < py::int_(0)) {
                        return -std::numeric_limits<T>::infinity();
                    }
                    else {
                        return std::numeric_limits<T>::infinity();
                    }
                }
            }
        }
        else
        {
            // If our type is an integer type, we want to handle overflow in conversion.
            // first convert it to uint64_t to avoid overflow when our type is signed.
            // This type is guaranteed to be big enough for anything.
            // Use PyLong_AsUnsignedLongLongMask to do the conversion with overflow handling.
            uint64_t val = PyLong_AsUnsignedLongLongMask(h.ptr());
            return static_cast<T>(val);
        }
    }
    throw py::type_error("Expected a numeric type");
}

// Global helper to help with manual dispatch logic
int get_priority(py::handle h) {
    if (py::isinstance<CNumBase>(h)) return py::cast<CNumBase*>(h)->priority(); // for c nums use the priority method
    if (py::isinstance<py::float_>(h)) return 9; // above all integers but below CNum floats
    if (py::isinstance<py::int_>(h)) return 0; // below everything
    return -1;
}

// Safety wrappers around Div/Mod/Shifts, to behave like hardware (in shifts masking) and raise an exception when dividing by zero or overflow (otherwise it'll raise a signal and crash instead of raising a python exception).
struct SafeDiv { 
    template<typename T> T operator()(T a, T b) const {
        if constexpr(std::is_integral_v<T>)
        {
            // we only need to do those checks on integers, as floats will be inf/-inf/nan instead of crashing
            if (b == 0)
            {
                // throw zero division error. we need this way as pybind11 doesn't have a py::zero_division_error
                py::set_error(PyExc_ZeroDivisionError, "division by zero");
                throw py::error_already_set();
            }
            if constexpr (std::is_signed_v<T>) {
                if (a == std::numeric_limits<T>::min() && b == -1) {
                    // throw overflow error if we divide the minimum by -1
                    py::set_error(PyExc_OverflowError, "integer overflow in division");
                    throw py::error_already_set();
                }
            }
        }
        return a / b; 
    }
};
struct SafeMod {
    template<typename T> T operator()(T a, T b) const {
        if (b == 0)
        {
            // throw zero division error. we need this way as pybind11 doesn't have a py::zero_division_error
            py::set_error(PyExc_ZeroDivisionError, "modulo by zero");
            throw py::error_already_set();
        }
        if constexpr (std::is_signed_v<T> && std::is_integral_v<T>) {
            if (a == std::numeric_limits<T>::min() && b == -1) {
                // throw overflow error if we divide the minimum by -1 (mod is division)
                py::set_error(PyExc_OverflowError, "integer overflow in division");
                throw py::error_already_set();
            }
        }
        return a % b;
    }
};
struct SafeLShift {
    template<typename T> T operator()(T a, T b) const {
        // The mask is 31 bits for non 64-bit types and 63 bits for 64-bit types in x86_64 hardware
        int mask = (sizeof(T) == 8) ? 0x3F : 0x1F;
        return a << (b & mask);
    }
};
struct SafeRShift {
    template<typename T> T operator()(T a, T b) const {
        // The mask is 31 bits for non 64-bit types and 63 bits for 64-bit types in x86_64 hardware
        int mask = (sizeof(T) == 8) ? 0x3F : 0x1F;
        return a >> (b & mask);
    }
};

// There's no abs operator in C++ to use so we have to define it ourselves
struct OpAbs { 
    template<typename T> T operator()(T a) const { 
        if constexpr (std::is_unsigned_v<T>) return a; // if it's unsigned abs does nothing
        else return std::abs(a); // otherwise return abs(a)
    } 
};
/*
An helper function that determines the type of a CNum from its ID and dispatches to a given function with an instance of that type.
Used to prevent typing the entire switch-case logic multiple times for different operations.
*/
template<typename F>
py::object dispatch_callback_with_type_by_id(CNumTypeID id, F&& func) {
    switch (id)
    {
        case CNumTypeID::INT8:
            return func(int8_t{});
        case CNumTypeID::UINT8:
            return func(uint8_t{});
        case CNumTypeID::INT16:
            return func(int16_t{});
        case CNumTypeID::UINT16:
            return func(uint16_t{});
        case CNumTypeID::INT32:
            return func(int32_t{});
        case CNumTypeID::UINT32:
            return func(uint32_t{});
        case CNumTypeID::INT64:
            return func(int64_t{});
        case CNumTypeID::UINT64:
            return func(uint64_t{});
        case CNumTypeID::FLOAT32:
            return func(float{});
        case CNumTypeID::FLOAT64:
            return func(double{});
        case CNumTypeID::FLOAT80:
            return func((long double){});
    }
    throw std::runtime_error("Invalid type id");
}

/*
An helper function that dispatches a binary operation with a known type (after we determined the type from the ID).
Used both in dispatch_binary_op and dispatch_binary_integer_op after determining the type from the ID, to prevent code duplication.
Gets a (must be a CNum), b (a python object), and whether the order is swapped (for non-commutative operations, to prevent duplication for both cases)
*/
template<typename T, typename Op>
py::object dispatch_binary_op_known_type(CNumBase *a, py::object b, bool order_swapped)
{
    auto* typed_a = static_cast<CNum<T>*>(a); // static cast a to the known type T
    T va = typed_a->value;
    T vb = py_object_to_cpp_type<T>(b);
    if (order_swapped) std::swap(va, vb); // swap the order of operands if needed 
    T res = Op{}(va, vb);
    CNum<T> resCNum = CNum<T>(res, typed_a->priority(), typed_a->type_id()); // create a CNum of the appropriate type
    return py::cast(resCNum);
}

/*
A template dispatcher for binary operations.
Determines the type of the result based on priorities and performs the operation with apprropriate type conversions.
Attempts to mimic C type promotion rules.
*/
template <typename Op>
py::object dispatch_binary_op(py::object self, py::object other) {
    int p1 = get_priority(self), p2 = get_priority(other);
    if (p1 == -1 || p2 == -1) return py::reinterpret_borrow<py::object>(Py_NotImplemented);
    bool order_swapped = false; // we need to keep track of whether we swapped the order as not all operations are commutative
    if (p1 < p2)
    {
        // make it so the higher priority type is always on the left to simplify logic
        std::swap(p1, p2);
        std::swap(self, other);
        order_swapped = true;
    }
    if (py::isinstance<py::float_>(self))
    {
        // if the highest priority is a python float, do the operations as double (equivalent) and return a python float
        double a = py::cast<double>(self);
        double b = py::cast<double>(other);
        if (order_swapped) std::swap(a, b);
        return py::cast(Op{}(a, b));
    }
    // Otherwise, we'll divide into cases based on the ID of self (it's the higher priority one and now guaranteed to be a CNumBase)
    auto* s = py::cast<CNumBase*>(self);
    CNumTypeID id = s->type_id();
    return dispatch_callback_with_type_by_id(id, [&](auto type_instance) {
        using T = decltype(type_instance); // get a type template parameter for the type we are dispatching on
        return dispatch_binary_op_known_type<T, Op>(s, other, order_swapped);
    });
}

/*
A dispatcher for binary operations that only applies to integer types.
This prevents invalid operations on floats (such as bitwise operations), which would compile error if we attempted to perform with the normal dispatcher.
*/
template <typename Op>
py::object dispatch_binary_integer_op(py::object self, py::object other) {
    int p1 = get_priority(self), p2 = get_priority(other);
    // check if one of the types isn't supported
    if (p1 == -1 || p2 == -1) return py::reinterpret_borrow<py::object>(Py_NotImplemented);

    bool order_swapped = false;
    if (p1 < p2)
    {
        // make it so the higher priority type is always on the left to simplify logic
        std::swap(p1, p2);
        std::swap(self, other);
        order_swapped = true;
    }
    if (py::isinstance<py::float_>(self))
    {
        // if the higher priority type is a float, these operations are not supported.
        // as float types are higher priority than int types, this practically checks both operands.
        return py::reinterpret_borrow<py::object>(Py_NotImplemented);
    }
    // Once we ruled out floats, the higher priority number has to be a CNum integer (as python ints are lowest priority)
    auto *self_cnumbase = py::cast<CNumBase *>(self);
    CNumTypeID id = self_cnumbase->type_id();
    return dispatch_callback_with_type_by_id(id, [&](auto type_instance) {
        using T = decltype(type_instance); // get a type template parameter for the type we are dispatching on
        if constexpr (!std::is_integral_v<T>) {
            // if the type we are dispatching on is not an integer type, these operations are not supported.
            return py::reinterpret_borrow<py::object>(Py_NotImplemented);
        }
        else
        {
            return dispatch_binary_op_known_type<T, Op>(self_cnumbase, other, order_swapped);
        }
    });
}

/*
An helper function for dispatch_unary, to dispatch unary operations on known CNum type.
Used after determining the type from id in dispatch_unary and dispatch_int_unary, to avoid code duplication.
Gets a (must be a CNumBase)
*/
template<typename T, typename Op>
py::object dispatch_unary_known_type(CNumBase *a) {
    auto* typed_a = static_cast<CNum<T>*>(a); // static cast a to the known type T
    T va = typed_a->value;
    T res = Op{}(va);
    CNum<T> resCNum = CNum<T>(res, typed_a->priority(), typed_a->type_id()); // create a CNum of the appropriate type
    return py::cast(resCNum);
}

template <typename Op>
py::object dispatch_unary(py::object self) {
    auto* self_cnumbase = py::cast<CNumBase*>(self);
    CNumTypeID id = self_cnumbase->type_id();
    return dispatch_callback_with_type_by_id(id, [&](auto type_instance) {
        using T = decltype(type_instance); // get a type template parameter for the type we are dispatching on
        return dispatch_unary_known_type<T, Op>(self_cnumbase);
    });
}

template <typename Op>
py::object dispatch_int_unary(py::object self) {
    auto* self_cnumbase = py::cast<CNumBase*>(self);
    CNumTypeID id = self_cnumbase->type_id();
    return dispatch_callback_with_type_by_id(id, [&](auto type_instance) {
        using T = decltype(type_instance); // get a type template parameter for the type we are dispatching on
        if constexpr (!std::is_integral_v<T>) {
            // if the type we are dispatching on is not an integer type, these operations are not supported.
            return py::reinterpret_borrow<py::object>(Py_NotImplemented);
        }
        else
        {
            return dispatch_unary_known_type<T, Op>(self_cnumbase);
        }
    });
}

/*
A dispatcher for comparison operations.
This is needed as unlike other binary operations, comparison operations need to return a boolean and not a CNum.
This is the only difference.
*/
template<typename Op>
py::object dispatch_comparision(py::object self, py::object other)
{
    int p1 = get_priority(self), p2 = get_priority(other);
    if (p1 == -1 || p2 == -1) return py::reinterpret_borrow<py::object>(Py_NotImplemented);
    bool order_swapped = false; // we need to keep track of whether we swapped the order as not all operations are commutative
    if (p1 < p2)
    {
        // make it so the higher priority type is always on the left to simplify logic
        std::swap(p1, p2);
        std::swap(self, other);
        order_swapped = true;
    }
    if (py::isinstance<py::float_>(self))
    {
        double a = py::cast<double>(self);
        double b = py::cast<double>(other);
        if (order_swapped) std::swap(a, b);
        return py::bool_(a == b);
    }
    auto* s = py::cast<CNumBase*>(self);
    CNumTypeID id = s->type_id();
    return dispatch_callback_with_type_by_id(id, [&](auto type_instance) {
        using T = decltype(type_instance); // get a type template parameter for the type we are dispatching on
        auto* typed_a = static_cast<CNum<T>*>(s); // static cast a to the known type T
        T va = typed_a->value;
        T vb = py_object_to_cpp_type<T>(other);
        if (order_swapped) std::swap(va, vb); // swap the order of operands if needed 
        bool res = Op{}(va, vb);
        return py::cast(res);
    });
}

/*
An helper function that casts a binary operation result to the type of the base
This is used in in place dispatchers, as the result is casted to the type of the base object (a in a += b)
This is used to prevent code repetition, as this is used in both dispatch_inplace_binary_op and dispatch_inplace_binary_integer_op
*/
py::object cast_result_to_base_type(py::object base, py::object res)
{
    // if the result is NotImplemented, return it
    if (res.ptr() == Py_NotImplemented)
    {
        return res;
    }
    // now we need to cast it to self type
    auto* base_cnumbase = py::cast<CNumBase*>(base);
    CNumTypeID base_id = base_cnumbase->type_id();
    return dispatch_callback_with_type_by_id(base_id, [&](auto type_instance) {
        using T = decltype(type_instance); // get a type template parameter for the type we are dispatching on
        auto *typed_base = static_cast<CNum<T>*>(base_cnumbase); // static cast base to the known type T
        T res_T = py_object_to_cpp_type<T>(res); // use py_object_to_cpp_res which already has the casting logic we need
        CNum<T> res_cnum = CNum<T>(res_T, typed_base->priority(), typed_base->type_id()); // create a CNum of the appropriate type
        return py::cast(res_cnum);
    }); 
}

/*
A dispatcher for inplace binary operations (like __iadd__)
This mimics c behavior for those operations, which acts like (base_type)(a op b)
For example, if a is int, a *= 2.5 makes a = (int)(a * 2.5).
We mimic this by using dispatch_binary_op, then casting the result using py_object_to_cpp_type.
*/
template <typename Op>
py::object dispatch_inplace_binary_op(py::object self, py::object other) {
    // Use dispatch binary op to evaluate the result
    py::object res = dispatch_binary_op<Op>(self, other);
    return cast_result_to_base_type(self, res);
}

/*
Similar to dispatch_inplace_binary_op but only for integer operations, to prevent invalid operations on floats.
*/
template <typename Op>
py::object dispatch_inplace_binary_integer_op(py::object self, py::object other)
{
    py::object res = dispatch_binary_integer_op<Op>(self, other);
    return cast_result_to_base_type(self, res);
}

// define __r<operator>__ function for pybind initialization
// binary
template <typename Op>
py::object dispatch_r_binary_op(py::object self, py::object other) {
    return dispatch_binary_op<Op>(other, self); // just swap the order of operands and call the normal dispatcher
}
// Integer Binary
template <typename Op>
py::object dispatch_r_binary_integer_op(py::object self, py::object other) {
    return dispatch_binary_integer_op<Op>(other, self); // just swap the order of operands and call the normal dispatcher
}

/*
An implementation of the __int__ method for the python binding.
*/
py::object cnum_int(CNumBase *self) {
    py::object self_pyobject = self->as_python_object(); // use as_python_object, which returns either int or float
    return py::int_(self_pyobject); // convert to pybind int_
}

/*
An implementation of the __float__ method for the python binding.
*/
py::object cnum_float(CNumBase *self) {
    py::object self_pyobject = self->as_python_object(); // use as_python_object, which returns either int or float
    return py::float_(self_pyobject); // convert to pybind float_
}

/*
An implementation of the __bool__ method for the python binding.
Uses cpp built-in bool conversion to mimic its behavior.
*/
bool cnum_bool(CNumBase *self) {
    if (dynamic_cast<CFloatBase*>(self)) // separate check for float types and integer types, so we cast it to the right thing
    {
        return (bool)self->as_float();
    }
    else
    {
        return (bool)self->as_integer();
    }
}

/*
An implementation of the from_bytes method for the python binding.
Gets a bytes object and returns a CNum python object of the given type.
*/
template<typename T, int P, CNumTypeID ID>
CNum<T> cnum_from_bytes(py::bytes b)
{
    std::string_view s_view = b;
    std::string s(s_view); // convert to string for easier manipulation
    if (s.size() != true_size<T>())
    {
        // If we are given the wrong number of bytes, raise an error.
        // We want to be given the true size amount of bytes
        throw py::value_error("Invalid number of bytes for type");
    }
    // We need to provide enough bytes for the type, so for the case where the true size is less than the c++ size, we pad it
    if (s.size() < sizeof(T))
    {
        s += std::string(sizeof(T) - s.size(), '\0');
    }
    T val;
    std::memcpy(&val, s.data(), sizeof(T));
    return CNum<T>(val, P, ID);
}

/*
An implementation of the CNum constructor for the python binding.
Gets a python object, which can be either a CNum, a built-in numeric type, or bytes.
*/
template<typename T, int P, CNumTypeID ID>
CNum<T> cnum_create(py::object v) {
    if (py::isinstance<py::bytes>(v)) {
        // if it's bytes, use cnum_from_bytes
        return cnum_from_bytes<T, P, ID>(v.cast<py::bytes>());
    }
    // otherwise, use py_object_to_cpp_type which handles python numeric types to create the T value, and then create the CNum from it
    T val = py_object_to_cpp_type<T>(v);
    return CNum<T>(val, P, ID);
}

/*
An implementation of the to_bytes method for the python binding.
Gets a CNum python object and returns its value as a bytes object.
*/
py::bytes cnum_to_bytes(const CNumBase &self) {
    CNumTypeID id = self.type_id();
    return dispatch_callback_with_type_by_id(id, [&](auto type_instance) {
        using T = decltype(type_instance); // get a type template parameter for the type we are dispatching on
        CNum<T> self_typed = static_cast<const CNum<T>&>(self); // cast to the known type T
        std::string res(true_size<T>(), '\0'); // initialize the string buffer
        std::memcpy(res.data(), &self_typed.value, true_size<T>()); // use memcpy to copy the bytes of the value into the string buffer
        return py::bytes(res); // convert it to python bytes
    });
}

/*
An implementation of the __hash__ method for the python binding.
Functions the same as the hash of the python object returned by as_python_object.
This allows accessing by cnum objects in python dicts or sets.
*/
size_t cnum_hash(const CNumBase& self) {
    py::object pyobj = self.as_python_object(); // convert to python object (int or float)
    return py::hash(pyobj); // use pybind's hash function, which will call
}

/*
An implementation of the __str__ method for the python binding.
Converts the CNum to the underlying C object and use stringstream to convert it to string.
*/
py::object cnum_str(CNumBase *self) {
    return dispatch_callback_with_type_by_id(self->type_id(), [&](auto type_instance) {
        using T = decltype(type_instance);
        auto* self_typed_cnum = static_cast<CNum<T>*>(self); // cast to typed CNum
        std::stringstream ss;
        ss << +self_typed_cnum->value; // use + to print uint8_t and int8_t as numbers instead of characters
        return py::cast(ss.str());
    });
}

/*
An implementation of the __repr__ method for the python binding.
Returns a string representation of the CNum object.
Shows both the integer and hexadecimal representation for integers
For floats, shows the float representation.
Has the class name in the beginning to indicate the type of the CNum.
*/
py::object cnum_repr(py::object self) {
    CNumBase *self_cnumbase = py::cast<CNumBase*>(self);
    return dispatch_callback_with_type_by_id(self_cnumbase->type_id(), [&](auto type_instance) {
        using T = decltype(type_instance);
        // cast to typed CNum
        auto* self_typed_cnum = static_cast<CNum<T>*>(self_cnumbase);
        // get the class name for the repr string, using self.__class__.__name__
        std::string name = self.attr("__class__").attr("__name__").cast<std::string>();
        // Uses stringstream to format the result
        std::stringstream ss;
        if constexpr (std::is_floating_point_v<T>)
        {
            // for floating point types, only show the float representation
            // format: ClassName(float_value)
            ss << name << "(" << self_typed_cnum->value << ")";
        }
        else
        {
            // for integer types, we also want hex representation
            // format: ClassName(int_value, hex_value)
            // We use + as value might be a char

            ss << name << "(" << +self_typed_cnum->value << ", 0x" << std::hex;
            if (self_typed_cnum->value < 0)
            {
                // for negative values, we want to show the hex of the 2's complement representation
                // However, std::hex converts types smaller than int to int before doing it
                // So we manually convert it to unsigned instead
                ss << +static_cast<std::make_unsigned_t<T>>(self_typed_cnum->value);
            }
            else
            {
                // Otherwise we can just show the hex of the value directly
                ss << +self_typed_cnum->value;
            }
            // close the hex (switch to dec) and the parentheses
            ss << std::dec << ")";
        }
        return py::cast(ss.str());
    });
}

/*
An implementation of the __format__ method for the python binding.
Uses the format of the matching python object (int or float).
*/
py::object cnum_format(CNumBase *self, py::object format_spec)
{
    py::object self_pyobject = self->as_python_object(); // use as_python_object, which returns either int or float
    return self_pyobject.attr("__format__")(format_spec); // use the __format__ method of the python object
}

/*
An helper function to fully bind a CNum of a specific type to python.
Binds all the functions and properties, and takes into consideration whether it's an integer or float to bind it to the appropriate base class.
*/
template <typename T, int P, CNumTypeID ID>
void bind_cnum(py::module_& m, const std::string name, const std::string& doc = "") {
    // determine the base class whether the type is floating point or not, using std::conditional_t
    using BaseType = std::conditional_t<std::is_floating_point_v<T>, CFloatBase, CIntBase>;
    // register the class to python with the appropriate base class
    py::class_<CNum<T>, BaseType> c(m, name.c_str(), doc.c_str());
    // define the constructor
    c.def(py::init(&cnum_create<T, P, ID>),
          "Initializes from either an int, float, bytes or another CNum");
    // define the static from_bytes method (as it actually needs to be defined there and not generically)
    c.def_static("from_bytes", &cnum_from_bytes<T, P, ID>, py::arg("data"),
                 "Creates an instance from a bytes object.\nThe number of bytes must match the size of the type.");
    // add size and is_signed as static class attributes as well
    c.attr("size") = true_size<T>();
    c.attr("is_signed") = std::is_signed_v<T>;
}


PYBIND11_MODULE(number_types, m) {
    // add module docstring
    m.doc() = R"pbdoc(
Provides C-like numeric types for python.
Handles overflow, C-like division / modulo and type promotion.
Each number type can be used in standard python syntax with normal operators.
Has both integer and floating point types.
Available types:
Int8 / Char, UInt8 / UChar,
Int16 / Short, UInt16 / UShort,
Int32 / Int, UInt32 / UInt,
Int64 / Long, UInt64 / ULong,
Float32 / Float,
Float64 / Double,
Float80 / LongDouble
    )pbdoc";
    // Expose base classes to python
    py::class_<CNumBase> base(m, "CNumBase", "Base class for all numeric types in this module.\nShouldn't be used directly.");
    py::class_<CIntBase, CNumBase> int_base(m, "CIntBase", "Base class for all integer types in this module.\nShouldn't be used directly.");
    py::class_<CFloatBase, CNumBase> float_base(m, "CFloatBase", "Base class for all floating point types in this module.\nShouldn't be used directly.");

    // Expose .value to as_python_object    
    base.def_property_readonly("value", &CNumBase::as_python_object); 

    // Bind all operators to the base classes
    // Arithmetic (Standard across all numbers)
    base.def("__add__", &dispatch_binary_op<std::plus<>>);
    base.def("__sub__", &dispatch_binary_op<std::minus<>>);
    base.def("__mul__", &dispatch_binary_op<std::multiplies<>>);
    base.def("__truediv__", &dispatch_binary_op<SafeDiv>);
    // Arithmetic right
    base.def("__radd__", &dispatch_r_binary_op<std::plus<>>);
    base.def("__rsub__", &dispatch_r_binary_op<std::minus<>>);
    base.def("__rmul__", &dispatch_r_binary_op<std::multiplies<>>);
    base.def("__rtruediv__", &dispatch_r_binary_op<SafeDiv>);
    // Arithmetic inplace
    base.def("__iadd__", &dispatch_inplace_binary_op<std::plus<>>);
    base.def("__isub__", &dispatch_inplace_binary_op<std::minus<>>);
    base.def("__imul__", &dispatch_inplace_binary_op<std::multiplies<>>);
    base.def("__itruediv__", &dispatch_inplace_binary_op<SafeDiv>);

    // Unary
    base.def("__neg__", &dispatch_unary<std::negate<>>);
    base.def("__abs__", &dispatch_unary<OpAbs>);

    // Comparison
    base.def("__eq__", &dispatch_comparision<std::equal_to<>>);
    base.def("__ne__", &dispatch_comparision<std::not_equal_to<>>);
    base.def("__lt__", &dispatch_comparision<std::less<>>);
    base.def("__le__", &dispatch_comparision<std::less_equal<>>);
    base.def("__gt__", &dispatch_comparision<std::greater<>>);
    base.def("__ge__", &dispatch_comparision<std::greater_equal<>>);

    // Integer/Bitwise Math (only to CIntBase)
    int_base.def("__floordiv__", &dispatch_binary_integer_op<SafeDiv>);
    int_base.def("__mod__", &dispatch_binary_integer_op<SafeMod>);
    int_base.def("__lshift__", &dispatch_binary_integer_op<SafeLShift>);
    int_base.def("__rshift__", &dispatch_binary_integer_op<SafeRShift>);
    int_base.def("__and__", &dispatch_binary_integer_op<std::bit_and<>>);
    int_base.def("__or__", &dispatch_binary_integer_op<std::bit_or<>>);
    int_base.def("__xor__", &dispatch_binary_integer_op<std::bit_xor<>>);
    // Integer right
    int_base.def("__rfloordiv__", &dispatch_r_binary_integer_op<SafeDiv>);
    int_base.def("__rmod__", &dispatch_r_binary_integer_op<SafeMod>);
    int_base.def("__rlshift__", &dispatch_r_binary_integer_op<SafeLShift>);
    int_base.def("__rrshift__", &dispatch_r_binary_integer_op<SafeRShift>);
    int_base.def("__rand__", &dispatch_r_binary_integer_op<std::bit_and<>>);
    int_base.def("__ror__", &dispatch_r_binary_integer_op<std::bit_or<>>);
    int_base.def("__rxor__", &dispatch_r_binary_integer_op<std::bit_xor<>>);
    // Integer inplace
    int_base.def("__ifloordiv__", &dispatch_inplace_binary_integer_op<SafeDiv>);
    int_base.def("__imod__", &dispatch_inplace_binary_integer_op<SafeMod>);
    int_base.def("__ilshift__", &dispatch_inplace_binary_integer_op<SafeLShift>);
    int_base.def("__irshift__", &dispatch_inplace_binary_integer_op<SafeRShift>);
    int_base.def("__iand__", &dispatch_inplace_binary_integer_op<std::bit_and<>>);
    int_base.def("__ior__", &dispatch_inplace_binary_integer_op<std::bit_or<>>);
    int_base.def("__ixor__", &dispatch_inplace_binary_integer_op<std::bit_xor<>>);
    // Integer unary
    int_base.def("__invert__", &dispatch_int_unary<std::bit_not<>>);
    int_base.def("__index__", &cnum_int); // Allow integers to be used for list indices/slicing

    // Other methods (such as type conversion and representation)
    base.def("__int__", &cnum_int);
    base.def("__float__", &cnum_float);
    base.def("__bool__", &cnum_bool);
    base.def("__repr__", &cnum_repr);
    base.def("__str__", &cnum_str);
    base.def("__hash__", &cnum_hash);
    base.def("__format__", &cnum_format);
    base.def("to_bytes", &cnum_to_bytes, "Returns the byte representation of the CNum.");


    // Bind all cnums to python
    bind_cnum<int8_t, 1, CNumTypeID::INT8>(m, "Int8", "Signed 8-bit C-like integer");
    bind_cnum<uint8_t, 2, CNumTypeID::UINT8>(m, "UInt8", "Unsigned 8-bit C-like integer");

    bind_cnum<int16_t, 3, CNumTypeID::INT16>(m, "Int16", "Signed 16-bit C-like integer");
    bind_cnum<uint16_t, 4, CNumTypeID::UINT16>(m, "UInt16", "Unsigned 16-bit C-like integer");

    bind_cnum<int32_t, 5, CNumTypeID::INT32>(m, "Int32", "Signed 32-bit C-like integer");
    bind_cnum<uint32_t, 6, CNumTypeID::UINT32>(m, "UInt32", "Unsigned 32-bit C-like integer");

    bind_cnum<int64_t, 7, CNumTypeID::INT64>(m, "Int64", "Signed 64-bit C-like integer");
    bind_cnum<uint64_t, 8, CNumTypeID::UINT64>(m, "UInt64", "Unsigned 64-bit C-like integer");

    bind_cnum<float, 10, CNumTypeID::FLOAT32>(m, "Float32", "32-bit floating-point C-like number");
    bind_cnum<double, 11, CNumTypeID::FLOAT64>(m, "Float64", "64-bit floating-point C-like number");
    bind_cnum<long double, 12, CNumTypeID::FLOAT80>(m, "Float80", "80-bit floating-point C-like number");

    // Aliases
    m.attr("Char") = m.attr("Int8");
    m.attr("UChar") = m.attr("UInt8");
    m.attr("Short") = m.attr("Int16");
    m.attr("UShort") = m.attr("UInt16");
    m.attr("Int") = m.attr("Int32");
    m.attr("UInt") = m.attr("UInt32");
    m.attr("Long") = m.attr("Int64");
    m.attr("ULong") = m.attr("UInt64");
    m.attr("Float") = m.attr("Float32"); 
    m.attr("Double") = m.attr("Float64");
    m.attr("LongDouble") = m.attr("Float80");
}