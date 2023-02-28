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
    uint8_t *arr = malloc(256);
    for (uint8_t i = 0; i < 255; i++)
        arr[i] = i;
    arr = realloc(arr, 1);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) >= 1);
    // We cannot increase the bounds of a capability, so the following line
    // should fail
    arr = realloc(arr, 256);
    if (arr == NULL) {
        printf("Attack unsuccessful\n");
        return 0;
    }
    for (uint8_t i = 0; i < 255; i++)
        assert(arr[i] == i);

    printf("Attack successful\n");
    return 0;
}
