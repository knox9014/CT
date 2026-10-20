/* Independent typed integer CUDA consumer, pinned official cuda.h. */
#include <cuda.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define CHECK(call) do { CUresult code=(call); if(code!=CUDA_SUCCESS) { fprintf(stderr,"CUDA check failed code=%d\n",(int)code); return 3; } } while(0)
int main(int argc,char **argv) {
    enum { N=257,TOTAL=N+129 };
    CUdevice device;CUcontext context;CUmodule module;CUfunction x32,x64,fill;
    CUdeviceptr a32,b32,a64,b64,ia,ib;
    uint32_t input32[TOTAL],output32[TOTAL],mask32=UINT32_MAX,n=N;
    uint64_t input64[TOTAL],output64[TOTAL],mask64=UINT64_C(0x80000000fedcba98),value=UINT64_MAX;
    const uint32_t guard32=UINT32_C(0xcafebabe);
    const uint64_t guard64=UINT64_C(0xdeadbeefcafebabe);
    unsigned int i;void *args[4];FILE *file;long length;unsigned char *image;
    if(argc!=2)return 2;
    file=fopen(argv[1],"rb");if(!file)return 2;
    if(fseek(file,0,SEEK_END)||(length=ftell(file))<=0||length>16*1024*1024||fseek(file,0,SEEK_SET))return 2;
    image=(unsigned char*)malloc((size_t)length+1);if(!image)return 2;
    if(fread(image,1,(size_t)length,file)!=(size_t)length)return 2;
    fclose(file);image[length]=0;
    CHECK(cuInit(0));CHECK(cuDeviceGet(&device,0));CHECK(cuCtxCreate(&context,0,device));
    CHECK(cuModuleLoadData(&module,image));free(image);
    CHECK(cuModuleGetFunction(&x32,module,"xor32"));CHECK(cuModuleGetFunction(&x64,module,"xor64"));CHECK(cuModuleGetFunction(&fill,module,"fill64"));
    for(i=0;i<TOTAL;i++){input32[i]=guard32;output32[i]=guard32;input64[i]=guard64;output64[i]=guard64;}
    for(i=0;i<N;i++) {
        input32[65+i]=i*UINT32_C(0x9e3779b9)^UINT32_C(0x80000000);
        input64[65+i]=(uint64_t)i*UINT64_C(0x9e3779b97f4a7c15)^UINT64_C(0x8000000000000000);
        output32[65+i]=~(input32[65+i]^mask32);output64[65+i]=~(input64[65+i]^mask64);
    }
    CHECK(cuMemAlloc(&a32,sizeof(input32)));CHECK(cuMemAlloc(&b32,sizeof(output32)));CHECK(cuMemAlloc(&a64,sizeof(input64)));CHECK(cuMemAlloc(&b64,sizeof(output64)));
    CHECK(cuMemcpyHtoD(a32,input32,sizeof(input32)));CHECK(cuMemcpyHtoD(b32,output32,sizeof(output32)));CHECK(cuMemcpyHtoD(a64,input64,sizeof(input64)));CHECK(cuMemcpyHtoD(b64,output64,sizeof(output64)));
    ia=a32+64*4;ib=b32+64*4;args[0]=&ia;args[1]=&ib;args[2]=&mask32;args[3]=&n;
    CHECK(cuLaunchKernel(x32,(N+63)/64,1,1,64,1,1,0,NULL,args,NULL));
    CHECK(cuMemcpyDtoH(output32,b32,sizeof(output32)));
    for(i=0;i<TOTAL;i++)if(output32[i]!=((i>=65&&i<65+N)?input32[i]^mask32:guard32))return 4;
    ia=a64+64*8;ib=b64+64*8;args[2]=&mask64;
    CHECK(cuLaunchKernel(x64,(N+63)/64,1,1,64,1,1,0,NULL,args,NULL));
    CHECK(cuMemcpyDtoH(output64,b64,sizeof(output64)));
    for(i=0;i<TOTAL;i++)if(output64[i]!=((i>=65&&i<65+N)?input64[i]^mask64:guard64))return 5;
    for(i=65;i<65+N;i++)output64[i]=~value;
    CHECK(cuMemcpyHtoD(b64,output64,sizeof(output64)));args[0]=&ib;args[1]=&value;args[2]=&n;
    CHECK(cuLaunchKernel(fill,(N+63)/64,1,1,64,1,1,0,NULL,args,NULL));
    CHECK(cuMemcpyDtoH(output64,b64,sizeof(output64)));
    for(i=0;i<TOTAL;i++)if(output64[i]!=((i>=65&&i<65+N)?value:guard64))return 6;
    CHECK(cuMemFree(a32));CHECK(cuMemFree(b32));CHECK(cuMemFree(a64));CHECK(cuMemFree(b64));CHECK(cuModuleUnload(module));CHECK(cuCtxDestroy(context));
    puts("{\"status\":\"pass\",\"results\":771,\"guards\":387}");return 0;
}
