/* CT-owned test protocol; CUDA declarations come only from official headers. */
#pragma once
#include <windows.h>
#include <cudaTypedefs.h>
#include <stdio.h>
struct SharedResources { CUdeviceptr a,b,c; CUmodule module; CUfunction function; };
typedef int (__cdecl *ProducerOpen)(const char *,struct SharedResources *,CUcontext *);
typedef int (__cdecl *ConsumerOpen)(CUcontext *);
typedef int (__cdecl *ConsumerRun)(const struct SharedResources *);
typedef int (__cdecl *PluginClose)(void);
typedef HMODULE (__cdecl *PluginDriver)(void);
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"check failed at line %d\n",__LINE__); return 3; } } while(0)
#define OK(x) REQUIRE((x)==0)
