
/// Supported architectures enumeration
enum
{
    KFR_ARCH_X86    = 0,
    KFR_ARCH_SSE2   = 1,
    KFR_ARCH_SSE3   = 2,
    KFR_ARCH_SSSE3  = 3,
    KFR_ARCH_SSE41  = 4,
    KFR_ARCH_SSE42  = 5,
    KFR_ARCH_AVX    = 6,
    KFR_ARCH_AVX2   = 7,
    KFR_ARCH_AVX512 = 8,
};

struct 
{
    int x, y;
} s;

union {
    int i;
    float f;
} u;
