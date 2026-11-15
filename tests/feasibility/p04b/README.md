# P04b original-header ABI feasibility

symbol_abi.cpp compiles only against the authenticated local CUDA12 runtime headers.
It verifies four C signatures, copy-kind values, invalid-symbol13 and invalid-copy21.
It does not load CT, run a GPU, or establish Runtime26 support. Expected Windows x64
output: SYMBOL_ABI 4 8 8 4. Vendor headers, object/executable and raw logs stay ignored.
