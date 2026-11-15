/* Diagnostic ONLY. Not a CT capability profile. All other exports forward via DEF. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <cuda_runtime_api.h>
static unsigned major_queries,minor_queries;
cudaError_t CUDARTAPI cudaDeviceGetAttribute(int *out,enum cudaDeviceAttr attr,int device) {
 HMODULE runtime=LoadLibraryW(L"ct_runtime.dll");
 typedef cudaError_t (CUDARTAPI *query_fn)(int *,enum cudaDeviceAttr,int);
 typedef cudaError_t (CUDARTAPI *count_fn)(int *);
 query_fn query;count_fn count;int devices=0;cudaError_t code;FILE *f;int ok;
 if(!runtime)return cudaErrorInsufficientDriver;
 query=(query_fn)GetProcAddress(runtime,"cudaDeviceGetAttribute");
 count=(count_fn)GetProcAddress(runtime,"cudaGetDeviceCount");
 if(!query||!count){FreeLibrary(runtime);return cudaErrorInsufficientDriver;}
 if(!out || device<0 || (attr!=cudaDevAttrComputeCapabilityMajor && attr!=cudaDevAttrComputeCapabilityMinor)) {
  code=query(out,attr,device);FreeLibrary(runtime);return code;
 }
 code=count(&devices);FreeLibrary(runtime);if(code)return code;
 if(device!=0 || devices<1)return cudaErrorInvalidDevice;
 if(attr==cudaDevAttrComputeCapabilityMajor){*out=5;major_queries++;}
 else {*out=2;minor_queries++;}
 f=fopen("metadata.json","wb");if(!f)return cudaErrorUnknown;
 ok=fprintf(f,"{\"major_queries\":%u,\"minor_queries\":%u,\"major\":5,\"minor\":2}",major_queries,minor_queries)>0;
 if(fclose(f)!=0 || !ok)return cudaErrorUnknown;
 return cudaSuccess;
}
