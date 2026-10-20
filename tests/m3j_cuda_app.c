/* Ordinary independent CUDA consumer for the synthetic integer oracle fixture. */
#include <cuda.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#define CHECK(call) do { CUresult code=(call); if(code!=CUDA_SUCCESS) { fprintf(stderr,"CUDA check failed code=%d\n",(int)code); return 3; } } while(0)
int main(int argc,char **argv) {
    enum { N=32, GUARD=64 };
    CUdevice device;CUcontext context;CUmodule module;CUfunction kernel;CUdeviceptr output_device;
    float output[N+GUARD];unsigned int seed=0,i;void *args[2]={&output_device,&seed};
    FILE *file;long length;unsigned char *image;
    if(argc!=2)return 2;
    file=fopen(argv[1],"rb");if(!file)return 2;
    if(fseek(file,0,SEEK_END)||(length=ftell(file))<=0||length>16*1024*1024||fseek(file,0,SEEK_SET))return 2;
    image=(unsigned char*)malloc((size_t)length+1);if(!image)return 2;
    if(fread(image,1,(size_t)length,file)!=(size_t)length)return 2;
    fclose(file);image[length]=0;
    CHECK(cuInit(0));CHECK(cuDeviceGet(&device,0));CHECK(cuCtxCreate(&context,0,device));
    CHECK(cuModuleLoadData(&module,image));free(image);
    CHECK(cuModuleGetFunction(&kernel,module,"integer_checks"));
    for(i=0;i<N+GUARD;i++)output[i]=(i<N)?NAN:-12345.25f;
    CHECK(cuMemAlloc(&output_device,sizeof(output)));CHECK(cuMemcpyHtoD(output_device,output,sizeof(output)));
    CHECK(cuLaunchKernel(kernel,1,1,1,1,1,1,0,NULL,args,NULL));
    CHECK(cuMemcpyDtoH(output,output_device,sizeof(output)));
    for(i=0;i<N;i++)if(output[i]!=1.0f)return 4;
    for(i=N;i<N+GUARD;i++)if(output[i]!=-12345.25f)return 5;
    CHECK(cuMemFree(output_device));CHECK(cuModuleUnload(module));CHECK(cuCtxDestroy(context));
    puts("{\"status\":\"pass\",\"results\":32,\"guards\":64}");return 0;
}
