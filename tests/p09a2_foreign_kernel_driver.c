#include <windows.h>
#define API __declspec(dllexport) int __stdcall
API cuModuleLoadData(void) {return 999;}
API cuModuleGetFunction(void) {return 999;}
API cuLaunchKernel(void) {return 999;}
API cuModuleUnload(void) {return 999;}
API cuDeviceGetAttribute(void) {return 999;}
