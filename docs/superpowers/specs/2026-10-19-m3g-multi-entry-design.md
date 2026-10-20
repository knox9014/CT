# M3g / P02: multiple kernel entries in one module

Baseline: M3f8b73a53. User authorized continuing P02 implementation/testing.
Extend the existing PTX/module path, preserving known PTX profiles and CUDA26 exports.

- Parse one module header and bounded unused globals, then1..32 distinct visible entries.
  Keep existing source256KiB/token65536 caps per module and register256/block128/
  instruction4096/parameter32 caps per entry. Entry names cannot collide with globals.
  Parameters/registers/labels are scoped per entry; malformed or unsupported later entries
  reject the whole module. Used globals/device calls remain P04, not silently ignored.
- New parse_module returns Module{profile,kernels}; legacy parse still requires one entry.
- New translate_module returns CompiledModule{profile,entries,spirv}; each CompiledEntry
  contains entry name and params. Legacy translate retains one-entry behavior.
- Emit one SPIR-V binary with shared type/constant/builtin definitions and distinct functions.
  IDs are global; register/label state resets per function. Reuse identical function types;
  entry interfaces contain that entry's used builtins. No splitting into separate native modules.
- Fatbin alternative identity is a sorted entry-name -> ordered ParamKind map. Entry order
  and parameter names may differ, but the entry set and per-entry ABI must match.
  All candidates validate before selection/native load. Existing rank and failure rules remain.
- Backend owns one native module and its ordered kernel handles. Create all before exposing
  a CUDA module; partial failure destroys created kernels before module, retaining uncertain
  resources/poisoned context under existing policy. No native fallback.
- CUDA function tokens own (module token,entry index). Launch validates that entry's params;
  repeated lookup may create separate tokens for the same entry. Unload/context destruction
  invalidates all such handles. Unknown entry500, invalid/stale/foreign handles400.
- Current ABI remains Pointer(global f32,host arg8B,alignment4 for pointed data), U32/F32(4B).
  Structure/vector/other address-space ABI expansion requires a later layout descriptor.
- Raw text, genuine compressed/plain fatbin, static/dynamic app-local consumers use the same path.
  No Runtime/AMD/shared/global-storage support or stronger CUDA conformance is implied.

Validation: parser scope/limits/rejections, SPIR-V entry/function IDs and signatures,
alternative name-map comparison, cleanup fault injection, GPU add/sub/scalar kernels of
different ABI in one loaded module, duplicate lookups/cross-module/cross-context/unload/
context-destroy lifetime, raw/plain/compressed inputs, unchanged external C consumer/CLI,
M1~M3f native regressions, tests/lint/ABI/privacy and one fresh whole-branch review.
SPIR-V official validator absence is recorded as skip, separately from native compile/run.
