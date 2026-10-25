#include "../include/ct_cudart.h"
using SymbolError=int;
using SymbolKind=int;
#define SYMBOL_CALL CT_RUNTIME_API
constexpr int symbol_invalid=13,symbol_direction=21,symbol_htod=1,symbol_dtoh=2,symbol_dtod=3,symbol_default=4;
#include "runtime_symbol_probe.hpp"
