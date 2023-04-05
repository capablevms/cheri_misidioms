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
    uint8_t *arr = malloc(256);
    for (uint8_t i = 0; i < 255; i++)
        arr[i] = i;
    free(arr);

    for (size_t i = 0; i < 10000; i++) {
        arr = malloc(256);
        for (uint8_t j = 1; j < 255; j++) {
            if (arr[j] != j) {
                goto next;
            }
        }
        printf("Attack successful\n");
        return 0;

next:
        free(arr);
    }

    printf("Attack unsuccessful\n");
    return 0;
}
