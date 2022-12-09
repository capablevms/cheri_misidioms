#include <assert.h>
#include <cheriintrin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
    char* str = "Hello world";
    char* str_copy = malloc(strlen(str) + 1);
    strcpy(str_copy, str);
    printf("Copy: %s\n", str_copy);
    assert(cheri_length_get(str_copy) == cheri_length_get(str));
}
