#include <windows.h>
static LONG calls;
__declspec(dllexport) int __stdcall cuInit(unsigned flags) { (void)flags; InterlockedIncrement(&calls);return 0; }
__declspec(dllexport) int __stdcall test_init_calls(void) { return calls; }
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved) { (void)instance;(void)reason;(void)reserved;return TRUE; }
