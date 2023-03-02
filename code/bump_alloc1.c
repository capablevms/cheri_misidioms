#include <string.h>
#include <sys/mman.h>

char *heap = NULL;
char *heap_start = NULL;
size_t HEAP_SIZE = 0x1000000000;

void *malloc_init() {
  heap = heap_start = mmap(NULL, HEAP_SIZE,
    PROT_READ | PROT_WRITE,
    MAP_PRIVATE | MAP_ANON, -1, 0);
  return heap;
}

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

void free(void *ptr) { }

void *realloc(void *ptr, size_t size) {
  void *new_ptr = malloc(size);
  if (new_ptr == NULL) return NULL;
  memcpy(new_ptr, ptr, size);
  return new_ptr;
}
