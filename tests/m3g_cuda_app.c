/* Independent ordinary CUDA consumer built with pinned NVIDIA headers. */
#include <cuda.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#define CHECK(call) do { CUresult code=(call); if(code!=CUDA_SUCCESS) { fprintf(stderr,"CUDA check failed code=%d\n",(int)code); return 3; } } while(0)
int main(int argc,char **argv) {
    enum { N=257, GUARD=64 };
    CUdevice device; CUcontext context; CUmodule module; CUfunction functions[4],missing;
    CUdeviceptr left_device,right_device,output_device;
    float left[N],right[N],output[N+GUARD],value=3.25f;
    unsigned int n=N,i,k; void *arguments[4]; FILE *file; long length; unsigned char *image;
    const char *names[4]={"kernel_add","kernel_sub","kernel_fill","kernel_add"};
    if(argc!=2) return 2;
    file=fopen(argv[1],"rb"); if(!file) return 2;
    if(fseek(file,0,SEEK_END) || (length=ftell(file))<=0 || length>16*1024*1024 || fseek(file,0,SEEK_SET)) return 2;
    image=(unsigned char*)malloc((size_t)length+1); if(!image) return 2;
    if(fread(image,1,(size_t)length,file)!=(size_t)length) return 2;
    fclose(file); image[length]=0;
    CHECK(cuInit(0)); CHECK(cuDeviceGet(&device,0)); CHECK(cuCtxCreate(&context,0,device));
    CHECK(cuModuleLoadData(&module,image)); free(image);
    for(k=0;k<4;k++) CHECK(cuModuleGetFunction(&functions[k],module,names[k]));
    missing=(CUfunction)(size_t)1;
    if(cuModuleGetFunction(&missing,module,"missing")!=CUDA_ERROR_NOT_FOUND || missing!=NULL) return 4;
    for(i=0;i<N;i++) { left[i]=(float)i*.25f;right[i]=-(float)i*.125f; }
    CHECK(cuMemAlloc(&left_device,sizeof(left)));CHECK(cuMemAlloc(&right_device,sizeof(right)));CHECK(cuMemAlloc(&output_device,sizeof(output)));
    CHECK(cuMemcpyHtoD(left_device,left,sizeof(left)));CHECK(cuMemcpyHtoD(right_device,right,sizeof(right)));
    for(k=0;k<4;k++) {
        for(i=0;i<N+GUARD;i++) output[i]=(i<N)?NAN:-12345.25f;
        CHECK(cuMemcpyHtoD(output_device,output,sizeof(output)));
        if(k==2) { arguments[0]=&output_device;arguments[1]=&value;arguments[2]=&n; }
        else { arguments[0]=&left_device;arguments[1]=&right_device;arguments[2]=&output_device;arguments[3]=&n; }
        CHECK(cuLaunchKernel(functions[k],(N+63)/64,1,1,64,1,1,0,NULL,arguments,NULL));
        CHECK(cuMemcpyDtoH(output,output_device,sizeof(output)));
        for(i=0;i<N;i++) {
            float expected=(k==2)?value:((k==1)?left[i]-right[i]:left[i]+right[i]);
            if(output[i]!=expected) return 5;
        }
        for(i=N;i<N+GUARD;i++) if(output[i]!=-12345.25f) return 6;
    }
    CHECK(cuMemFree(left_device));CHECK(cuMemFree(right_device));CHECK(cuMemFree(output_device));
    CHECK(cuModuleUnload(module));
    if(cuLaunchKernel(functions[0],1,1,1,64,1,1,0,NULL,NULL,NULL)!=CUDA_ERROR_INVALID_HANDLE) return 7;
    CHECK(cuCtxDestroy(context));
    puts("{\"status\":\"pass\",\"entries\":3,\"results\":1028,\"guards\":256}");
    return 0;
}
