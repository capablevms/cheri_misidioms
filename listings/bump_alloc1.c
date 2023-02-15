#include <string.h>
#include <sys/mman.h>

void *heap_start = NULL;
void *heap_current = NULL;
void *heap_end = NULL;
size_t HEAP_SIZE = 0x1000000UL;

void *malloc(size_t size) {
  if (heap_start == NULL) {
    heap_current = mmap(NULL, HEAP_SIZE,
      PROT_READ | PROT_WRITE,
      MAP_PRIVATE | MAP_ANON, -1, 0);
    if (heap_start == MAP_FAILED) return NULL;
    heap_start = heap_current;
  }
  if (heap_current+size > heap_start + HEAP_SIZE)
    return NULL;
  heap_current += size;
  return heap_current - size;
}

void free(void *ptr) { }

void *realloc(void *ptr, size_t size) {
  void *new_ptr = malloc(size);
  if (new_ptr == NULL) return NULL;
  memcpy(new_ptr, ptr, size);
  return new_ptr;
}
