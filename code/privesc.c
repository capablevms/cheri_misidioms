#include <assert.h>
#include <cheriintrin.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if !defined(__CHERI_PURE_CAPABILITY__)
#  error This example must be run on a CHERI purecap system
#endif

// On CheriBSD, if a capability's bounds include the base pointer to a
// `malloc`d block we can use `realloc` to launder a narrow capability into a
// wider one. In other words if:
//   1. malloc returns a capability C1 to a block 0..n bytes long
//   2. we create a capability C2 with bounds 0..m where m < n
//   3. realloc allows us to launder C2 back into C1

int main() {
int32_t array[16] = {0};
	int32_t *array_ptr = &array;
	uint32_t bounds = 64;
	// Get a valid capability from the DDC
	void *__capability ddc_cap = (void *__capability) cheri_ddc_get();
	assert(cheri_tag_get(ddc_cap));
	// Set its address to array_ptr
	ddc_cap = cheri_address_set(ddc_cap, array_ptr);
	// Reduce its bounds
	ddc_cap = cheri_bounds_set(ddc_cap, bounds);
	// Check whether it is still valid
	assert(cheri_tag_get(ddc_cap));
	// Write it back
	// FIXME: CHERI PROTECTION VIOLATION
	// Capability bounds fault
	write_ddc(ddc_cap);
	return 0;
}
