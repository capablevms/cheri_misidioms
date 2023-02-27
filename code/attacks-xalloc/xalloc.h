/* $Id: xalloc.h,v 1.2 1995/08/04 10:14:53 sverrehu Exp $ */
#ifndef XALLOC_H
#define XALLOC_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>   /* size_t */

void xaSetErrFunc(void (*f)(void));
void *xmalloc(size_t size);
void *xcalloc(size_t nmemb, size_t size);
void *xrealloc(void *ptr, size_t size);
char *xstrdup(const char *s);

#ifdef __cplusplus
}
#endif

#endif
