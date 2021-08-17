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

int main() {
    // If we allocate 4112 bytes, the capability we get from malloc has a
    // bounds length of 4112 bytes...
    uint8_t *arr = malloc(16400);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) == 16400);
    // ...if we realloc it down to 4104 bytes, the capability we get from
    // realloc has a bounds length of 4104 bytes...
    arr = realloc(arr, 16392);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) == 16392);
    // ...but if we realloc it down to 4097 bytes, the capability we get from
    // realloc still has a bounds of length of 4104 bytes.
    arr = realloc(arr, 16385);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) == 16392);
}
