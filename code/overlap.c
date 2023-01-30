#include <assert.h>
#include <cheriintrin.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

// Check whether malloc() returns blocks that overlap.

#define MAX_SIZE (24*1024)
#define NUM_MALLOCS 10000

int cmp(const void *a, const void *b) {
    ptraddr_t aw = cheri_base_get(((void **) a)[0]);
    ptraddr_t bw = cheri_base_get(((void **) b)[0]);
    return aw < bw ? -1 : aw > bw;
}

bool overlaps(void *x, void *y) {
    if (   cheri_base_get(x) < cheri_base_get(y)
        && cheri_base_get(x) + cheri_length_get(x) > cheri_base_get(y))
        return true;
    if (   cheri_base_get(y) < cheri_base_get(x)
        && cheri_base_get(y) + cheri_length_get(y) > cheri_base_get(x))
        return true;
    return false;
}

int main() {
    for (size_t i = 0; i < MAX_SIZE; i++) {
        size_t rl = cheri_representable_length(i);
        if (rl > i) {
            printf("%lu ", i);
            fflush(NULL);
            void **mallocs = calloc(NUM_MALLOCS, sizeof(void *));
            for (int j = 0; j < NUM_MALLOCS; j++) {
                mallocs[j] = malloc(i);
            }

            qsort(mallocs, NUM_MALLOCS, sizeof(void *), cmp);

            for (int j = 0; j < NUM_MALLOCS - 1; j++) {
                if (overlaps(mallocs[j], mallocs[j + 1])) {
                    printf("match! %lu\n", i);
                    exit(0);
                }
            }

            for (int j = 0; j < NUM_MALLOCS; j++) {
                free(mallocs[j]);
            }
            free(mallocs);
        }
    }
}
