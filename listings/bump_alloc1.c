void* heap_start = NULL; // FIXME - do we need to retain start address?
void* heap_current = NULL; // the bump pointer
void* heap_end = NULL;
size_t HEAP_SIZE = 0x1000000UL;

void* malloc(size_t size) {
    void* new_ptr = NULL;
    if (heap_start == NULL) {
        // first call of malloc - init
        heap_start = mmap(NULL, HEAP_SIZE,
                PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        heap_current = heap_start;
        heap_end = heap_start + HEAP_SIZE;
    }
    // FIXME - should we check mmap returns valid pointer?
    if (heap_current+size < heap_end) {
      new_ptr = heap_current;
      heap_current += size; // bump
    }
    return new_ptr;
}

void free(void *ptr) { assert(0); }

void* realloc(void* p, size_t size) { return malloc(size); }

