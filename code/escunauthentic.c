#include <assert.h>
#include <cheriintrin.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

int main() {
    uint8_t *arr = malloc(16);
    assert(cheri_tag_get(arr));
    arr = cheri_tag_clear(arr);
    assert(!cheri_tag_get(arr));
    arr = realloc(arr, 16);
    if (cheri_tag_get(arr)) {
	printf("Attack successful\n");
    } else {
        printf("Attack unsuccessful\n");
    }
    return 0;
}
