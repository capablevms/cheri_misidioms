#include <assert.h>
#include <cheriintrin.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

bool overlaps(void *x, void *y) {
    assert(cheri_tag_get(x) && cheri_tag_get(y));
    return
       (cheri_base_get(x) >= cheri_base_get(y) && cheri_base_get(x) < cheri_base_get(y) + cheri_length_get(y))
    || (cheri_base_get(y) >= cheri_base_get(x) && cheri_base_get(y) < cheri_base_get(x) + cheri_length_get(x));
}

int main() {
    size_t sz = 20000000000489;
    void *b1 = malloc(sz);
    void *b2 = malloc(sz);
    printf("%lu (%lu)\n", cheri_base_get(b1), cheri_length_get(b1));
    printf("%lu (%lu)\n", cheri_base_get(b2), cheri_length_get(b2));
    printf("%lu\n", cheri_base_get(b2) - (cheri_base_get(b1) + cheri_length_get(b2)));
    return overlaps(b1, b2);
}
