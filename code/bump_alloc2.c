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
  return cheri_bounds_set_exact(
    new_ptr, alloc_size);
}

void *realloc(void *ptr, size_t size) {
  void *new_ptr = malloc(size);
  if (new_ptr == NULL) return NULL;
  memcpy(new_ptr, ptr,
    cheri_length_get(ptr) < size
    ? cheri_length_get(ptr) : size);
  return new_ptr;
}
