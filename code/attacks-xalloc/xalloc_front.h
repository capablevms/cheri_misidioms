#include "xalloc.h"

#define malloc xmalloc
#define realloc xrealloc
#define calloc xcalloc
#define strdup xstrdup
