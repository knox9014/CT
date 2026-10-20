/* Independent synthetic CUDA consumer, built with pinned official headers. */
#include <cuda.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#define CHECK(call) do { CUresult code=(call); if(code!=CUDA_SUCCESS) { fprintf(stderr,"CUDA check failed code=%d\n",(int)code); return 3; } } while(0)

static int execute(CUfunction kernel,unsigned int nx,unsigned int ny,unsigned int nz) {
    unsigned int bx=4,by=3,bz=(nz==1)?1:2;
    unsigned int gx=(nx+bx-1)/bx,gy=(ny+by-1)/by,gz=(nz+bz-1)/bz;
    unsigned int n=nx*ny*nz,total=gx*bx*gy*by*gz*bz+64,i;
    CUdeviceptr da,db,dc;
    float *a=(float*)malloc(n*sizeof(float)),*b=(float*)malloc(n*sizeof(float)),*out=(float*)malloc(total*sizeof(float));
    void *args[6]={&da,&db,&dc,&nx,&ny,&nz};
    if(!a || !b || !out)return 2;
    for(i=0;i<n;i++){a[i]=(float)i*.25f;b[i]=-(float)i*.125f;}
    for(i=0;i<total;i++)out[i]=(i<n)?NAN:-12345.25f;
    CHECK(cuMemAlloc(&da,n*sizeof(float)));CHECK(cuMemAlloc(&db,n*sizeof(float)));CHECK(cuMemAlloc(&dc,total*sizeof(float)));
    CHECK(cuMemcpyHtoD(da,a,n*sizeof(float)));CHECK(cuMemcpyHtoD(db,b,n*sizeof(float)));CHECK(cuMemcpyHtoD(dc,out,total*sizeof(float)));
    CHECK(cuLaunchKernel(kernel,gx,gy,gz,bx,by,bz,0,NULL,args,NULL));
    CHECK(cuMemcpyDtoH(out,dc,total*sizeof(float)));
    for(i=0;i<n;i++)if(out[i]!=a[i]+b[i])return 5;
    for(i=n;i<total;i++)if(out[i]!=-12345.25f)return 6;
    CHECK(cuMemFree(da));CHECK(cuMemFree(db));CHECK(cuMemFree(dc));
    free(a);free(b);free(out);return 0;
}

int main(int argc,char **argv) {
    CUdevice device;CUcontext context;CUmodule module;CUfunction kernel;
    FILE *file;long length;unsigned char *image;int attr,value,result;
    if(argc!=2)return 2;
    file=fopen(argv[1],"rb");if(!file)return 2;
    if(fseek(file,0,SEEK_END)||(length=ftell(file))<=0||length>16*1024*1024||fseek(file,0,SEEK_SET))return 2;
    image=(unsigned char*)malloc((size_t)length+1);if(!image)return 2;
    if(fread(image,1,(size_t)length,file)!=(size_t)length)return 2;
    fclose(file);image[length]=0;
    CHECK(cuInit(0));CHECK(cuDeviceGet(&device,0));CHECK(cuCtxCreate(&context,0,device));
    for(attr=5;attr<=7;attr++){CHECK(cuDeviceGetAttribute(&value,(CUdevice_attribute)attr,device));if(value<5)return 4;}
    CHECK(cuModuleLoadData(&module,image));free(image);
    CHECK(cuModuleGetFunction(&kernel,module,"matrix_add"));
    result=execute(kernel,17,13,1);if(result)return result;
    result=execute(kernel,13,11,5);if(result)return result;
    CHECK(cuModuleUnload(module));
    if(cuLaunchKernel(kernel,1,1,1,1,1,1,0,NULL,NULL,NULL)!=CUDA_ERROR_INVALID_HANDLE)return 7;
    CHECK(cuCtxDestroy(context));
    puts("{\"status\":\"pass\",\"results\":936,\"guards\":632}");return 0;
}
