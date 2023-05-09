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
    char * secret = malloc(4242);
    char ** arr = malloc(256 * sizeof(arr[0]));
    for (int i = 0; i < 256; i++) {
        arr[i] = secret + i;
    }
    arr = realloc(arr, 1 * sizeof(arr[0]));
    assert(cheri_tag_get(arr) && cheri_length_get(arr) >= (1 * sizeof(arr[0])));
    // We cannot increase the bounds of a capability, so the following line
    // should fail
    arr = realloc(arr, 256 * sizeof(arr[0]));
    if (arr == NULL) {
        // Out of memory: we can't attempt the attack.
        return 1;
    }
    printf("Original capability should remain unchanged:\n");
    printf("  arr[0] = %#lp\n", arr[0]);
    assert(cheri_is_equal_exact(arr[0], secret));
    printf("No other capabilities should be exposed by the realloc:\n");
    for (int i = 1; i < 256; i++) {
        if (cheri_tag_get(arr[i])) {
            printf("  arr[%u] = %#lp\n", i, arr[i]);
            printf("Attack successful\n");
            return 0;
        }
    }

    printf("Attack unsuccessful\n");
    return 0;
}
