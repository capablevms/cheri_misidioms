#include <string.h>
#include <stdio.h>
#include <sys/mman.h>
#include <cheriintrin.h>
#include <stddef.h>

char *heap = NULL;
char *heap_start = NULL;
size_t HEAP_SIZE = 0x1000000000;

void *malloc_init() {
  heap = heap_start = mmap(NULL, HEAP_SIZE,
    PROT_READ | PROT_WRITE,
    MAP_PRIVATE | MAP_ANON, -1, 0);
  return heap;
}

void free(void *ptr) { }

#ifdef CHERI_AWARE
void *malloc(size_t size) {
  if (heap == NULL && !malloc_init())
    return NULL;

  char *new_ptr = __builtin_align_up(
    heap,
    -cheri_representable_alignment_mask(size));
  size_t alloc_size =
    cheri_representable_length(size);
  size_t size_on_heap =
    __builtin_align_up(
      size, _Alignof(max_align_t));

  if (new_ptr + size_on_heap >
      heap_start + HEAP_SIZE)
    return NULL;
  heap = new_ptr + size_on_heap;
#ifdef __CHERI_PURE_CAPABILITY__
  return cheri_bounds_set_exact(
    new_ptr, alloc_size);
#else
  return new_ptr;
#endif
}

void *realloc(void *ptr, size_t size) {
  void *new_ptr = malloc(size);
  if (new_ptr == NULL) return NULL;
  memcpy(new_ptr, ptr,
#ifdef __CHERI_PURE_CAPABILITY__
    cheri_length_get(ptr) < size
    ? cheri_length_get(ptr) : size);
#else
    size);
#endif
  return new_ptr;
}
#else
void *malloc(size_t size) {
  if (heap == NULL && !malloc_init())
    return NULL;
  size = __builtin_align_up(size,
    _Alignof(max_align_t));
  if (heap + size >
      heap_start + HEAP_SIZE)
    return NULL;
  heap += size;
  return heap - size;
}

void *realloc(void *ptr, size_t size) {
  void *new_ptr = malloc(size);
  if (new_ptr == NULL) return NULL;
  memcpy(new_ptr, ptr, size);
  return new_ptr;
}
#endif
