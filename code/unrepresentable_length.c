#include <cheriintrin.h>
#include <stddef.h>
#include <stdio.h>

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

// This program prints out the first capability length which cannot be
// precisely represented. See the 2019 Woodruf et al. paper.

int main() {
    for (size_t i = 0; ; i++) {
        size_t rl = cheri_representable_length(i);
        if (rl > i) {
            printf("The first unrepresentable length is %lu: "
                   "it has been rounded up to %lu\n", i, rl);
            break;
        }
    }
    return 0;
}
