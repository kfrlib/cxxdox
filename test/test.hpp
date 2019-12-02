#include <cstdio>
#include <cstdlib>

/// regular variable
int regular_variable;

/// regular constant
const int regular_constant = 1;

/// template variable
template <typename T>
T template_variable;

/// template constant
template <typename T>
const T template_constant = T(1);

/// regular typedef
using regular_typedef = int;

/// template typedef
template <typename T>
using template_typedef = T;

/// Struct
struct aaa;

/// regular function
void regular_function(int, float f);

/// template function
template <typename T>
T template_function(int, T);

/// overloaded function 1
void overloaded_function(int, int, int);

/// overloaded `function` 2
void overloaded_function(int, int, const char*);

/// overloaded @c function 3
void overloaded_function(int, regular_typedef);

/// @copybrief overloaded_function
void overloaded_function(int, aaa*);

/// regular class
class regular_class
{
public:
    /// regular class constructor
    regular_class();
    /// regular class destructor
    ~regular_class();

    /// regular class constructor
    regular_class(regular_class&&);

    /// regular class constructor
    regular_class(const regular_class&);

    /// regular class regular method
    int regular_method();

    /// regular class template method
    template <typename T>
    T template_method();

    /// regular class template struct
    template <typename T>
    struct template_nested_struct
    {
    };
};

/// class enum
enum class class_enum
{
    A = 0, ///< value of A
    B = 1 ///< value of B
};

/// template class
template <typename T>
class template_class
{
public:
    /// template class constructor
    template_class();
    /// template class destructor
    ~template_class();

    /// template class constructor
    template_class(template_class&&);

    /// template class constructor
    template_class(const template_class&);

    /// template class regular method
    int regular_method();

    /// template class template method
    template <typename U>
    U template_method(T);

    /// template class template struct
    template <typename U, int n, class_enum e>
    struct template_nested_struct
    {
    };
};

/// regular namespace
namespace regular_namespace
{
/// regular namespace functions
void namespace_function();
} // namespace regular_namespace

/// formula: 
/// \f[
///    E=mc^2
/// \f]
void math();


inline void test_output()
{
    std::printf("Hello, world!\n");
}