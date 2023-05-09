#include <stdio.h>
#include <string.h>
#include <errno.h>
#include "bench_harness.h"

int bmlog(BM_Harness *bmdata)
{
  FILE *fp ;
  int err = 0;

  fp = fopen(stringify_macro(BM_LOGFILE), "w");
  if (!fp) {
    error_log("Could not open <%s>. errno = %d", stringify_macro(BM_LOGFILE) , -errno);
    err = -1;
    goto err_bmlog;
  }

  fprintf(fp, "{\n");
  fprintf(fp, "  \"%s\" : \"%s\" ,\n", "bm", bmdata->bm );
  fprintf(fp, "  \"%s\" : %u ,\n", "gc_cycles", bmdata->gc_cycles );
  fprintf(fp, "  \"%s\" : %u\n", "gc_time_ms", bmdata->gc_time_ms );
  fprintf(fp, "}\n");

  fclose(fp);
  
err_bmlog: 
  return err;
}



