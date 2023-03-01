#include <string.h>
#include <stdio.h>
#include <sys/mman.h>
#include <cheriintrin.h>

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

#ifdef CHERI_AWARE
void *malloc(size_t size) {
  if (heap == NULL && !malloc_init())
    return NULL;

  char *new_ptr = __builtin_align_up(
    heap,
    ~cheri_representable_alignment_mask(size)
    + 1);
  size_t rounded =
    cheri_representable_length(size);
  if (new_ptr + rounded <
      heap_start + HEAP_SIZE) {
    heap = new_ptr + rounded;
    new_ptr = cheri_bounds_set_exact(
      new_ptr, rounded);
  } else new_ptr = NULL;
  return new_ptr;
}

void *realloc(void *ptr, size_t size) {
  void *new_ptr = malloc(size);
  if (new_ptr == NULL) return NULL;
  memcpy(new_ptr, ptr,
    cheri_length_get(ptr) < size
    ? cheri_length_get(ptr) : size);
  return new_ptr;
}
#else
void *malloc(size_t size) {
  if (heap == NULL && !malloc_init())
    return NULL;
  size = __builtin_align_up(size,
    sizeof(void *));
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
