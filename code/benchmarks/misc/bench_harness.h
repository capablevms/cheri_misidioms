#ifndef BM_HARNESS
#define BM_HARNESS

#define stringify(arg) #arg
#define stringify_macro(arg) stringify(arg)
#define error_log(fmt, args...) printf("[%s:%d] | "fmt"\n", __FUNCTION__, __LINE__, ##args)

typedef struct __BM_HARNESS_DATA__
{
  char *bm; 
  unsigned int gc_cycles;
  unsigned int gc_time_ms;
} BM_Harness; 

int bmlog(BM_Harness *);
#endif
