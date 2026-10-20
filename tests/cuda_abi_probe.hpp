// CT-owned structural ABI probe. Vendor headers are included by a separate TU.
#pragma once
#include <cstdio>
#include <type_traits>

template <class T, class = void> struct Complete : std::false_type {};
template <class T> struct Complete<T, std::void_t<decltype(sizeof(T))>> : std::true_type {};

template <class T> void abi_type() {
    if constexpr (std::is_const_v<T>) {
        std::printf("const-");
        abi_type<std::remove_const_t<T>>();
    } else if constexpr (std::is_pointer_v<T>) {
        std::printf("ptr[");
        abi_type<std::remove_pointer_t<T>>();
        std::printf("]");
    } else if constexpr (std::is_void_v<T>) {
        std::printf("void");
    } else if constexpr (!Complete<T>::value) {
        std::printf("opaque");
    } else if constexpr (std::is_enum_v<T>) {
        // CUDA's enum values used here are nonnegative and fit CT's signed int.
        // Windows x64 passes both representations identically; values tested below.
        std::printf("int:%zu:%zu", sizeof(T), alignof(T));
    } else {
        std::printf("%s:%zu:%zu", std::is_signed_v<T> ? "int" : "uint", sizeof(T), alignof(T));
    }
}

template <class R, class... Args> void abi_function(const char *name, R (*)(Args...)) {
    std::printf("%s:", name);
    abi_type<R>();
    std::printf("(");
    ((abi_type<Args>(), std::printf(";")), ...);
    std::printf(")\n");
}

static_assert(sizeof(void *) == 8, "This probe targets the Windows x64 ABI only");
