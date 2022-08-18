
void* malloc(size_t size) {
    void* new_ptr = NULL;
    void* tmp_ptr = NULL; /* for CHERI alignment */
    size_t rounded_len; /* for CHERI alignment */

    // skip one-time init code ... calls mmap

    // align pointer and size for CHERI
    tmp_ptr = __builtin_align_up(heap_current,
        ~cheri_representable_alignment_mask(size) + 1);
    rounded_size = cheri_representable_length(size);

    
    if (tmp_ptr+rounded_size < heap_end) {
      // enough space to satisfy malloc
      heap_current = tmp_ptr+rounded_size; // bump
      new_ptr = cheri_bounds_set_exact(tmp_ptr, rounded_len); // restrict
    }

    return new_ptr;
}
