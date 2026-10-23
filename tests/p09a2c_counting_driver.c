/* Count all forwarded Driver entries; nominal CT Driver remains untouched. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static volatile LONG64 calls;
static FARPROC counted_address(HMODULE module,LPCSTR name){InterlockedIncrement64(&calls);return GetProcAddress(module,name);}
#define GetProcAddress counted_address
#include "p09a_noop_driver.c"
#undef GetProcAddress
__declspec(dllexport) unsigned long long __stdcall ct_driver_calls(void){return (unsigned long long)InterlockedCompareExchange64(&calls,0,0);}
