// <CHERI_OUTPUT_DIR>/morello-sdk/bin/clang --config cheribsd-morello-purecap.cfg ./test_bump_alloc2.c

#include <assert.h>
#include <stddef.h>
#include <limits.h>
#include <sys/mman.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include "cheriintrin.h"

void *malloc(size_t);
void *malloc_init();
// From `bump_alloc1.c`
char *heap = NULL;
char *heap_start = NULL;
size_t HEAP_SIZE = 0x1000000;

void *malloc_init() {
  heap = heap_start = mmap(NULL, HEAP_SIZE,
    PROT_READ | PROT_WRITE,
    MAP_PRIVATE | MAP_ANON, -1, 0);
  return heap;
}

void free(void *ptr) { }
// End from

#include "bump_alloc2.c"

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
    printf("Allocated new array of size %lu at pointer %p.\n", vars_count, vars);
    for (size_t i = 0; i < vars_count; ++i)
    {
        vars[i] = i * i;
    }
    assert(sum_arr(vars, vars_count) == 285);
    int* ptr_var = malloc(sizeof(int));
    assert(ptr_var != NULL);
    assert(ptr_var != vars);
    printf("Allocated new pointer %p.\n", ptr_var);
    assert(malloc(0x1000000UL) == NULL);

    char *m = malloc(16);
    m = realloc(m, 32);
    assert(m != NULL);
    return 0;
}

