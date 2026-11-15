// Independent official-header consumer: metadata only, never launches a kernel.
#include <windows.h>
#include <ze_api.h>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

#define REQUIRE(x) do { if (!(x)) throw 1; } while (0)
#define CHECK(x) REQUIRE((x) == ZE_RESULT_SUCCESS)
#define RESOLVE(name) auto name = reinterpret_cast<decltype(&::name)>(GetProcAddress(loader, #name)); REQUIRE(name)

int main(int argc, char** argv) {
    try {
        REQUIRE(argc == 3);
        std::ifstream input(argv[1], std::ios::binary);
        REQUIRE(input.good());
        std::vector<unsigned char> code((std::istreambuf_iterator<char>(input)), {});
        REQUIRE(!code.empty());
        auto loader = LoadLibraryExW(L"ze_loader.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
        REQUIRE(loader);
        RESOLVE(zeInit); RESOLVE(zeDriverGet); RESOLVE(zeDeviceGet);
        RESOLVE(zeDeviceGetProperties); RESOLVE(zeContextCreate); RESOLVE(zeContextDestroy);
        RESOLVE(zeModuleCreate); RESOLVE(zeModuleDestroy); RESOLVE(zeModuleBuildLogDestroy);
        RESOLVE(zeKernelCreate); RESOLVE(zeKernelDestroy); RESOLVE(zeKernelGetProperties);
        CHECK(zeInit(ZE_INIT_FLAG_GPU_ONLY));
        uint32_t count = 0;
        CHECK(zeDriverGet(&count, nullptr)); REQUIRE(count > 0 && count <= 64);
        std::vector<ze_driver_handle_t> drivers(count);
        CHECK(zeDriverGet(&count, drivers.data())); REQUIRE(count <= drivers.size());
        ze_driver_handle_t driver = nullptr;
        ze_device_handle_t device = nullptr;
        char name[ZE_MAX_DEVICE_NAME]{};
        unsigned matches = 0;
        for (uint32_t i = 0; i < count; ++i) {
            uint32_t n = 0;
            CHECK(zeDeviceGet(drivers[i], &n, nullptr)); REQUIRE(n <= 64);
            if (!n) continue;
            std::vector<ze_device_handle_t> devices(n);
            CHECK(zeDeviceGet(drivers[i], &n, devices.data())); REQUIRE(n <= devices.size());
            for (uint32_t j = 0; j < n; ++j) {
                ze_device_properties_t props{}; props.stype = ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
                CHECK(zeDeviceGetProperties(devices[j], &props));
                REQUIRE(std::memchr(props.name, 0, sizeof(props.name)));
                if (props.vendorId == 0x8086 && std::strstr(props.name, "B390")) {
                    ++matches; driver = drivers[i]; device = devices[j];
                    std::memcpy(name, props.name, sizeof(name));
                }
            }
        }
        REQUIRE(matches == 1);
        ze_context_desc_t context_desc{}; context_desc.stype = ZE_STRUCTURE_TYPE_CONTEXT_DESC;
        ze_context_handle_t context = nullptr;
        CHECK(zeContextCreate(driver, &context_desc, &context)); REQUIRE(context);
        ze_module_desc_t module_desc{}; module_desc.stype = ZE_STRUCTURE_TYPE_MODULE_DESC;
        module_desc.format = ZE_MODULE_FORMAT_IL_SPIRV;
        module_desc.inputSize = code.size(); module_desc.pInputModule = code.data();
        module_desc.pBuildFlags = "";
        ze_module_handle_t module = nullptr; ze_module_build_log_handle_t log = nullptr;
        CHECK(zeModuleCreate(context, device, &module_desc, &module, &log)); REQUIRE(module);
        if (log) CHECK(zeModuleBuildLogDestroy(log));
        ze_kernel_desc_t kernel_desc{}; kernel_desc.stype = ZE_STRUCTURE_TYPE_KERNEL_DESC;
        kernel_desc.pKernelName = argv[2];
        ze_kernel_handle_t kernel = nullptr;
        CHECK(zeKernelCreate(module, &kernel_desc, &kernel)); REQUIRE(kernel);
        // Distinct nonzero output sentinels also detect success without field writes.
        ze_kernel_properties_t props;
        std::memset(&props, 0xa5, sizeof(props));
        props.stype = ZE_STRUCTURE_TYPE_KERNEL_PROPERTIES; props.pNext = nullptr;
        CHECK(zeKernelGetProperties(kernel, &props));
        CHECK(zeKernelDestroy(kernel)); CHECK(zeModuleDestroy(module)); CHECK(zeContextDestroy(context));
        REQUIRE(FreeLibrary(loader));
        std::printf("{\"device_name_hex\":\"");
        for (const unsigned char* p = reinterpret_cast<const unsigned char*>(name); *p; ++p)
            std::printf("%02x", unsigned(*p));
        std::printf("\",\"num_kernel_args\":%u,\"required_group_size\":[%u,%u,%u],"
                    "\"required_num_subgroups\":%u,\"required_subgroup_size\":%u,"
                    "\"max_subgroup_size\":%u,\"max_num_subgroups\":%u,"
                    "\"local_mem_bytes\":%u,\"private_mem_bytes\":%u,\"spill_mem_bytes\":%u}\n",
                    props.numKernelArgs, props.requiredGroupSizeX, props.requiredGroupSizeY, props.requiredGroupSizeZ,
                    props.requiredNumSubGroups, props.requiredSubgroupSize, props.maxSubgroupSize, props.maxNumSubgroups,
                    props.localMemSize, props.privateMemSize, props.spillMemSize);
        return 0;
    } catch (...) {
        // Failed native setup/cleanup terminates the isolated process; no blind retries.
        std::fputs("native kernel-resource probe failed\n", stderr);
        return 1;
    }
}
