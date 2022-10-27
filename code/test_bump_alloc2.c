// <CHERI_OUTPUT_DIR>/morello-sdk/bin/clang --config cheribsd-morello-purecap.cfg ./test_bump_alloc2.c

#include <assert.h>
#include <stddef.h>
#include <sys/mman.h>
#include <stdio.h>
#include "cheriintrin.h"

// From `bump_alloc1.c`
void* heap_start = NULL; // FIXME - do we need to retain start address?
void* heap_current = NULL; // the bump pointer
void* heap_end = NULL;
size_t HEAP_SIZE = 0x1000000UL;
// End from

/*******************************************************************************
 * Tested listing
 */

void* malloc(size_t size) {
    void* new_ptr = NULL;
    void* tmp_ptr = NULL; /* for CHERI alignment */
    size_t rounded_len; /* for CHERI alignment */

    // skip one-time init code ... calls mmap
    // From `bump_alloc1.c`
    if (heap_start == NULL) {
        // first call of malloc - init
        heap_start = mmap(NULL, HEAP_SIZE,
                PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        heap_current = heap_start;
        heap_end = heap_start + HEAP_SIZE;
    }
    // End from

    // align pointer and size for CHERI
    tmp_ptr = __builtin_align_up(heap_current,
        ~cheri_representable_alignment_mask(size) + 1);
    rounded_len = cheri_representable_length(size);

    if (tmp_ptr + rounded_len < heap_end) {
      // enough space to satisfy malloc
      heap_current = tmp_ptr+rounded_len; // bump
      new_ptr = cheri_bounds_set_exact(tmp_ptr, rounded_len); // restrict
    }

    return new_ptr;
}

/******************************************************************************/

int
sum_arr(int* arr, size_t arr_size)
{
    int sum = 0;
    for (size_t i = 0; i < arr_size; ++i)
    {
        sum += arr[i];
    }
    return sum;
}

int
main()
{
    const size_t vars_count = 10;
    int* vars = malloc(vars_count * sizeof(int));
    assert(vars != NULL);
    printf("Allocated new array of size %d at pointer %p.\n", vars_count, vars);
    for (size_t i = 0; i < vars_count; ++i)
    {
        vars[i] = i * i;
    }
    assert(sum_arr(vars, vars_count) == 285);
    int* ptr_var = malloc(sizeof(int));
    assert(ptr_var != NULL);
    assert(ptr_var != vars);
    printf("Allocated new pointer %p.\n", ptr_var);
    return 0;
}

