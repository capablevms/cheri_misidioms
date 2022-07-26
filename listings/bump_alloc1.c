void* heap_start = NULL;
size_t allocated = 0;

void* malloc(size_t size) {
    if (heap_start == NULL) {
        heap_start = mmap(NULL, 0x1000000UL,
                PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    }
    void* new_ptr = heap_start + allocated;
    allocated += size;
    return new_ptr;

void free(void *ptr) { }
