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
    uint8_t *arr = malloc(256);
    for (uint8_t i = 0; i < 255; i++)
        arr[i] = i;

    arr = realloc(arr, 1);
    assert(arr);
    free(arr);
    arr = malloc(256);

    for (uint8_t i = 1; i < 255; i++) {
        if (arr[i] != i) {
            printf("Attack unsuccessful\n");
            return 0;
        }
    }

    printf("Attack successful\n");
    return 0;
}
