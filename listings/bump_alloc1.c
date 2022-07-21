void* heap_start = 0x100000UL;
size_t allocated = 0;

void* malloc(size_t size) {
    void* new_alloc = mmap(heap_start + allocated, size);
    allocated += size;
    return new_alloc; }

void free(void *ptr) { }
