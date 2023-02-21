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
