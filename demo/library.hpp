#pragma once

#include <algorithm>
#include <concepts>
#include <cstddef>
#include <cstdint>
#include <string_view>
#include <utility>

/// @brief A global function that is not part of any namespace.
void global_function() {}

/// @addtogroup demo Demo Group
/// This is a @b demo library to showcase documentation features.
/// @{

/// @brief Library version
/// @version 1.0.0
/// @since Initial release
#define LIBRARY_VERSION "1.0.0"

// Namespace for the demo library
namespace ns
{

    /// @ingroup inheritance
    struct Base
    {
    };

    /// @ingroup inheritance
    struct Derived : public Base
    {
    };

    /// @brief A free function in the ns namespace.
    void free_function(int x);

    /// @copybrief free_function
    void another_function(int x);

    /// Simple struct
    struct Demo
    {
        int value; ///< An integer value
        char symbol; ///< A character symbol
    };

    /**
     * @brief A union to hold different types of data.
     */
    union Data
    {
        int i; ///< Integer data
        float f; ///< Float data
        double d; ///< Double data
        char c[8]; ///< Character array
    };

    /// This function will be excluded from documentation
    void excluded_function();

    /// @brief An inner namespace
    namespace inner
    {
        /// @brief A function in the inner namespace
        void some_function();
    } // namespace inner

    /**
     * @brief Enumeration of colors.
     *
     * This enum class defines a set of colors with specific underlying type.
     * @enum Color
     */
    enum class Color : uint8_t
    {
        Red   = 1, ///< Red color
        Green = 2, ///< Green color
        Blue  = 4 ///< Blue color
    };

    /**
     * @brief Converts a @ref Color enum to its string representation.
     *
     * @param color The Color enum value.
     * @return A string view representing the color name.
     * @retval "Red"   For @ref Color::Red.
     * @retval "Green" For @ref Color::Green.
     * @retval "Blue"  For @ref Color::Blue.
     * @retval "Unknown" For any invalid value.
     */
    inline constexpr std::string_view to_name(Color color) noexcept
    {
        switch (color)
        {
        case Color::Red:
            return "Red";
        case Color::Green:
            return "Green";
        case Color::Blue:
            return "Blue";
        default:
            return "Unknown";
        }
    }

    /// @brief  Template alias for a pair of types
    /// @tparam A
    /// @tparam B
    /// @typedef Pair
    template <typename A, typename B>
    using Pair = std::pair<A, B>;

    /**
     * @brief A 3D point structure.
     *
     * This templated struct represents a point in 3D space with coordinates x,
     * y, and z.
     * @tparam T The type of the coordinates (e.g., int, float, double).
     * @struct Point
     */
    template <typename T>
    struct Point
    {
        T x, y, z;
    };

    /// @brief Deduction guide for Point
    template <typename T>
    Point(T, T, T) -> Point<T>;

    /// Type alias for size_t
    using std::size_t;

    /// @brief Inline variable example
    inline constexpr size_t max_size = 1024; ///< Maximum size constant

    /// @brief Templated inline variable
    /// @details Represents the mathematical constant pi
    /// @tparam T The numeric type (e.g., float, double)
    /// @note This is a note about the pi variable
    template <typename T>
    inline constexpr T pi = T(3.1415926535897932385);

    /**
     * @brief Example class demonstrating documentation.
     *
     * This class serves as an example for documenting C++ code using
     * Doxygen-style comments.
     * @note This is a note about the Example class.
     * @warning This is a warning about the Example class.
     * @ingroup example
     * @class Example
     * @copydoc Example::multiply
     */
    class Example
    {
    public:
        /// @brief Constructor
        /// @details Initializes the Example class.
        /// @see @ref ~Example()
        Example();

        /// @brief Parameterized constructor
        /// @param val An integer to initialize the data member.
        Example(int val);

        /// @brief Destructor
        ~Example();

        /// It's member typedef
        using value_type = int;

        /// It's member enum
        enum Status
        {
            Ok    = 0,
            Error = 1
        };

        /// Nested struct
        struct Nested
        {
            int id; ///< Identifier
            std::string_view name; ///< Name
        };

        /**
         * @brief Performs an action and return @ref Demo .
         *
         * @code
         * x.doSomething(3.14, 2.71);
         * @endcode
         *
         * @return @ref Demo
         */
        Demo doSomething(double, double);

        /**
         * @brief Multiplies two values.
         *
         * @tparam T A numeric type.
         * @param a First value.
         * @param b Second value.
         * @return The product of a and b.
         * @remarks Markdown formula: $a \cdot b$
         */
        template <typename T>
        T multiply(T a, T b)
        {
            return a * b;
        }

    private:
        int data; ///< Internal data member
    };

    /**
     * First paragraph will automatically be the brief description.
     *
     * Detailed description goes here.
     *
     * @tparam N Number of elements in the array
     */
    template <int N>
    struct array
    {
        char data[N];
    };

    /**
     * @brief Concept that checks if a type supports addition.
     *
     * @tparam T concept parameter
     */
    template <typename T>
    concept Addable = requires(T a, T b) {
        { a + b } -> std::same_as<T>;
    };

    /// @brief Computes the absolute value of an integer.
    /// @param x Input integer value.
    /// @return The absolute value of @p x.
    /// @since 1.0.0
    /// @sa @ref abs(double)
    constexpr int abs(int x) { return (x < 0) ? -x : x; }

    /// @brief Computes the absolute value of a floating-point number.
    /// @param x Input floating-point value.
    /// @return The absolute value of @p x.
    /// @since 1.1.0
    /// @deprecated Prefer @c std::abs for floating-point types.
    /// @sa @ref abs(int)
    constexpr double abs(double x) { return (x < 0.0) ? -x : x; }

    template <int N>
    struct Tpl;

    template <>
    struct Tpl<1>
    {
        void tpl_foo();
    };

    /// @brief See @ref Tpl<1>
    /// @note This is a note
    /// DFT equation is
    /// \f[
    /// X[k] = \sum_{n=0}^{N-1} x[n] , e^{-j \frac{2\pi}{N} k n}
    /// \f]
    template <>
    struct Tpl<2>
    {
        void tpl_foo();
    };

    /**
     * @brief Returns the factorial of a number.
     *
     * @param n Input number
     * @return int
     * @retval 1 For @p n <= 1.
     * @since 1.0.0
     */
    constexpr int factorial(int n) noexcept
    {
        using number = int;
        return (n <= 1) ? 1 : n * factorial(n - 1);
    }

    constexpr void fn1(std::byte a, Color b) noexcept { return a; }

    /// @brief A wrapper that forwards any argument into its stored value.
    /// @details This utility struct uses a perfect-forwarding constructor to
    ///          initialize its data member from any compatible type, making it
    ///          useful for type erasure or generic factory patterns where the
    ///          exact construction site is separated from the call site.
    /// @tparam T The type of the wrapped value.
    /// @note This is a note about the C class.
    /// @warning This is a warning about the C class.
    template <typename T>
    struct C
    {
        template <typename U>
        C(U&& u) : value(std::forward<U>(u))
        {
        }
        T value;
    };

    /**
     * @brief Multiplies two matrices.
     * @details Performs a standard matrix multiplication on the given input
     *          and stores the result in the output buffer. All matrices are
     *          assumed to be stored in row-major order.
     * @tparam T The numeric type of the matrix elements.
     * @param out  Pointer to the output matrix buffer.
     * @param in   Pointer to the input matrix buffer.
     * @param rows Number of rows in both matrices.
     * @param cols Number of columns in both matrices.
     * @pre @p out, @p in must point to valid buffers.
     * @pre @p rows and @p cols must be greater than zero.
     * @post On return, @p out contains the matrix product of @p in.
     * @exception std::invalid_argument if @p rows or @p cols are zero.
     * @throws std::bad_alloc if internal allocation fails.
     * @since 1.2.0
     * @version 1.2.1
     */
    template <typename T>
    void multiply_matrix(T* out, const T* in, size_t rows, size_t cols);

    /// @brief A structure demonstrating anonymous unions and structs.
    /// @details This example shows how to document a struct that contains
    ///          anonymous nested union and struct members, allowing multiple
    ///          ways to access the same underlying data (e.g., individual
    ///          fields vs. a combined value).
    struct Win32Structure
    {
        union
        {
            struct
            {
                uint16_t field1;
                uint16_t field2;
            };
            uint32_t combined;
        };
    };

    struct ConflictingName
    {
    };

    /// @unknowntag This tag is not recognized and should be handled gracefully
    struct conflictingName
    {
    };

    inline namespace inl
    {
        /// @brief Inline namespace function
        void inline_function();
    } // namespace inl

    /// @brief A generic filter interface.
    /// @details This abstract base class defines the interface for filters
    ///          that can process data arrays of a given type.
    /// @tparam T The data type of the elements to filter.
    template <typename T>
    class filter
    {
    public:
        /// @brief Virtual destructor.
        virtual ~filter() {}

        /// @brief Applies the filter to a data array.
        /// @param data Pointer to the input/output data buffer.
        /// @param size Number of elements in the buffer.
        virtual void apply(T* data, size_t size) = 0;
    };

    /// Platform-independent error codes
    enum
    {
        SUCCESS       = 0, ///< Operation completed successfully
        ERR_GENERIC   = -1, ///< Generic / unspecified error
        ERR_TIMEOUT   = -2, ///< Operation timed out
        ERR_INVALID   = -3, ///< Invalid argument or state
        ERR_NOT_FOUND = -4, ///< Resource not found
        ERR_ACCESS    = -5, ///< Permission / access denied
        ERR_BUSY      = -6, ///< Resource is busy
    };

} // namespace ns

/** @}*/
