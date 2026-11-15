#include <type_traits>
#include <cstdio>
using SymbolAddress=SymbolError(SYMBOL_CALL *)(void **,const void *);
using SymbolSize=SymbolError(SYMBOL_CALL *)(size_t *,const void *);
using SymbolTo=SymbolError(SYMBOL_CALL *)(const void *,const void *,size_t,size_t,SymbolKind);
using SymbolFrom=SymbolError(SYMBOL_CALL *)(void *,const void *,size_t,size_t,SymbolKind);
static_assert(std::is_same_v<decltype(&cudaGetSymbolAddress),SymbolAddress>);
static_assert(std::is_same_v<decltype(&cudaGetSymbolSize),SymbolSize>);
static_assert(std::is_same_v<decltype(&cudaMemcpyToSymbol),SymbolTo>);
static_assert(std::is_same_v<decltype(&cudaMemcpyFromSymbol),SymbolFrom>);
static_assert(sizeof(SymbolError)==4&&sizeof(SymbolKind)==4);
int main(){std::printf("SYMBOL_ABI 4 %zu %zu %zu\n%d %d %d %d %d %d\n",sizeof(void *),sizeof(size_t),sizeof(SymbolKind),symbol_invalid,symbol_direction,symbol_htod,symbol_dtoh,symbol_dtod,symbol_default);}
