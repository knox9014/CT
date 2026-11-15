// Official-header-only compile proof; no CT or vendor binaries are linked.
#include <ze_api.h>
#include <cstddef>
#include <type_traits>
using Query = ze_result_t (ZE_APICALL *)(ze_device_handle_t, uint32_t *, ze_device_memory_properties_t *);
static_assert(std::is_same_v<decltype(&zeDeviceGetMemoryProperties), Query>);
static_assert(ZE_STRUCTURE_TYPE_DEVICE_MEMORY_PROPERTIES == 7);
static_assert(sizeof(ze_device_memory_properties_t) == 296);
static_assert(alignof(ze_device_memory_properties_t) == 8);
static_assert(offsetof(ze_device_memory_properties_t, totalSize) == 32);
static_assert(offsetof(ze_device_memory_properties_t, name) == 40);
