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
// `malloc`d block we can use `free` to recover the original capability. This
// is inherently fragile, and relies on the underlying malloc reusing memory
// (which CheriBSD's jemalloc currently does).

int main() {
    // malloc returns a capability C1 to a block 0..n bytes long
    uint8_t *arr = malloc(16);
    // Separate out the pointer from the capability so that we can check it
    // later.
    vaddr_t arr_addr = cheri_address_get(arr);

    // Create a capability C2 with bounds 0..m where m < n
    arr = cheri_bounds_set(arr, 8);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) == 8);

    // We first free C2...
    free(arr);
    // ...and then immediately allocate a block the same size as C1.
    arr = malloc(16);
    // We get back a capability C3 that is identical to C1.
    assert(cheri_address_get(arr) == arr_addr);
    assert(cheri_tag_get(arr) && cheri_length_get(arr) == 16);
}
