#include <assert.h>
#include <cheriintrin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if !defined(__CHERI_PURE_CAPABILITY__) || __CHERI_CAPABILITY_WIDTH__ != 128
#  error This example must be run on a CHERI purecap system with 128 bit capabilities
#endif

// On a CHERI system using CHERI Concentrate (CC) and the encoding system from
// the 2019 Woodruf et al. paper, this simple example shows that narrowing a
// capabilities bounds does not necessarily narrow the bounds. See also the
// `unrepresentable_length` program which, for a given CHERI system, prints out
// the first bounds length which is not precisely representable.
//
// Note that there are no guarantees about which minimum bounds will trigger
// issues under different CHERI implementations. As of the time of writing, a
// bound of 4097 bytes cannot be represented accurately on RISC-V CHERI but can
// on Morello -- the smallest unrepresentable bound on Morello is 16385 bytes.

uint8_t *array_with_hidden_secret(size_t size) {
    assert(size > 1);
    uint8_t *arr = malloc(size);
    for (size_t i = 0; i < size; i++) {
        arr[i] = i % 256;
    }
    return cheri_bounds_set(arr, size - 1);
}

int main() {
#if defined(__aarch64__)
    // If we allocate 16385 bytes, we get back a capability which precisely
    // forbids us from accessing the last byte...
    uint8_t *arr = array_with_hidden_secret(16385);
    assert(cheri_length_get(arr) == 16384);

    // ...however, if we allocate 16386 bytes, we get back a capability which
    // allows us to access the last byte.
    arr = array_with_hidden_secret(16386);
    assert(cheri_length_get(arr) == 16392);

#elif defined(__riscv)
    // If we allocate 4097 bytes, we get back a capability which precisely
    // forbids us from accessing the last byte...
    uint8_t *arr = array_with_hidden_secret(4097);
    assert(cheri_length_get(arr) == 4096);

    // ...however, if we allocate 4098 bytes, we get back a capability which
    // allows us to access the last byte.
    arr = array_with_hidden_secret(4098);
    assert(cheri_length_get(arr) == 4104);
#endif
}
