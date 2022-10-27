// gcc -I../listings ./test_bump_alloc1.c

#include <assert.h>
#include <stddef.h>
#include <sys/mman.h>
#include <stdio.h>

#include "../listings/bump_alloc1.c"

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
