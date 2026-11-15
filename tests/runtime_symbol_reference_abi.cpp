#include <cuda_runtime_api.h>
using SymbolError=cudaError_t;
using SymbolKind=cudaMemcpyKind;
#define SYMBOL_CALL CUDARTAPI
constexpr int symbol_invalid=cudaErrorInvalidSymbol,symbol_direction=cudaErrorInvalidMemcpyDirection;
constexpr int symbol_htod=cudaMemcpyHostToDevice,symbol_dtoh=cudaMemcpyDeviceToHost,symbol_dtod=cudaMemcpyDeviceToDevice,symbol_default=cudaMemcpyDefault;
#include "runtime_symbol_probe.hpp"
