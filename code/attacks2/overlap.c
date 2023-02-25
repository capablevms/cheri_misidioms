#include <assert.h>
#include <cheriintrin.h>
#include <err.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

// Check whether malloc() returns blocks that overlap.

#define NUM_UNREPRESENTABLES 512
#define NUM_MALLOCS 1000
#define NUM_TRIES 100

int cmp(const void *a, const void *b) {
    ptraddr_t aw = cheri_base_get(((void **) a)[0]);
    ptraddr_t bw = cheri_base_get(((void **) b)[0]);
    return aw < bw ? -1 : aw > bw;
}

bool overlaps(void *x, void *y) {
    assert(cheri_tag_get(x) && cheri_tag_get(y));
    return
       (cheri_base_get(x) >= cheri_base_get(y) && cheri_base_get(x) < cheri_base_get(y) + cheri_length_get(y))
    || (cheri_base_get(y) >= cheri_base_get(x) && cheri_base_get(y) < cheri_base_get(x) + cheri_length_get(x));
}

int main() {
    struct rlimit data_limits;
    if (getrlimit(RLIMIT_DATA, &data_limits) != 0)
        err(1, "Can't read ulimit");
    printf("Max data size %lu\n", data_limits.rlim_cur);

    size_t *unrepresentables = calloc(NUM_UNREPRESENTABLES, sizeof(size_t));
    size_t num_unrepresentables = 0;
    size_t i = data_limits.rlim_cur * 20;
    while (num_unrepresentables < NUM_UNREPRESENTABLES) {
        size_t rl = cheri_representable_length(i);
        if (rl > i) {
            unrepresentables[num_unrepresentables++] = i;
            i = rl;
        }
        i++;
    }

    for (size_t i = 0; i < NUM_TRIES; i++) {
        printf("ITERATION %lu (of %d)\r", i, NUM_TRIES);
        fflush(NULL);
        size_t num_mallocs = arc4random_uniform(NUM_MALLOCS);
        void **mallocs = calloc(num_mallocs, sizeof(void *));
        assert(mallocs);
        for (size_t j = 0; j < num_mallocs; j++) {
            size_t sz = unrepresentables[arc4random_uniform(num_unrepresentables)];
            mallocs[j] = malloc(sz);
            assert(mallocs[j]);
            assert(cheri_length_get(mallocs[j]) > sz);
        }

        qsort(mallocs, num_mallocs, sizeof(void *), cmp);

        for (size_t j = 0; j < num_mallocs - 1; j++) {
            assert(cheri_base_get(mallocs[j]) < cheri_base_get(mallocs[j + 1]));
            if (overlaps(mallocs[j], mallocs[j + 1])) {
                printf("(%lu, %lu) (%lu, %lu)", cheri_address_get(mallocs[j]), cheri_length_get(mallocs[j]), cheri_address_get(mallocs[j + 1]), cheri_length_get(mallocs[j + 1]));
                printf("\nAttack successful\n");
                return 0;
            }
        }

        for (size_t j = 0; j < num_mallocs; j++) {
            free(mallocs[j]);
        }
        free(mallocs);
    }

    printf("\nAttack unsuccessful\n");
    return 0;
}
