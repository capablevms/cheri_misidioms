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

#define NUM_UNREPRESENTABLES 512
#define MAX_SIZE (24*1024)
#define NUM_MALLOCS 100000
#define NUM_TRIES 1000

int cmp(const void *a, const void *b) {
    ptraddr_t aw = cheri_base_get(((void **) a)[0]);
    ptraddr_t bw = cheri_base_get(((void **) b)[0]);
    return aw < bw ? -1 : aw > bw;
}

bool overlaps(void *x, void *y) {
    assert(cheri_tag_get(x) && cheri_tag_get(y));
    if (   cheri_base_get(x) < cheri_base_get(y)
        && cheri_base_get(x) + cheri_length_get(x) > cheri_base_get(y))
        return true;
    if (   cheri_base_get(y) < cheri_base_get(x)
        && cheri_base_get(y) + cheri_length_get(y) > cheri_base_get(x))
        return true;
    return false;
}

int main() {
    size_t *unrepresentables = calloc(NUM_UNREPRESENTABLES, sizeof(size_t));
    size_t num_unrepresentables = 0;
    for (size_t i = 0; num_unrepresentables < NUM_UNREPRESENTABLES; i++) {
        size_t rl = cheri_representable_length(i);
        if (rl > i)
            unrepresentables[num_unrepresentables++] = rl;
    }

    for (int i = 0; i < NUM_TRIES; i++) {
        printf("ITERATION %lu (of %d)\r", i, NUM_TRIES);
        fflush(NULL);
        size_t num_mallocs = arc4random_uniform(NUM_MALLOCS);
        void **mallocs = calloc(num_mallocs, sizeof(void *));
        assert(mallocs);
        for (int j = 0; j < num_mallocs; j++) {
            mallocs[j] = malloc(unrepresentables[arc4random_uniform(num_unrepresentables)]);
            assert(mallocs[j]);
        }

        qsort(mallocs, num_mallocs, sizeof(void *), cmp);

        for (int j = 0; j < num_mallocs - 1; j++) {
            assert(cheri_base_get(mallocs[j]) < cheri_base_get(mallocs[j + 1]));
            if (overlaps(mallocs[j], mallocs[j + 1])) {
                printf("MATCH - %lu\n", i);
                exit(1);
            }
        }

        for (int j = 0; j < num_mallocs; j++) {
            free(mallocs[j]);
        }
        free(mallocs);
    }
    printf("\nDONE\n");
}
