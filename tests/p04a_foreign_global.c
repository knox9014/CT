#include <stddef.h>
__declspec(dllexport) int __stdcall cuModuleGetGlobal_v2(unsigned long long *p,size_t *n,void *m,const char *name) {
 (void)m;(void)name;if(p)*p=0;if(n)*n=0;return 801;
}
