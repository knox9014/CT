"""Encode only CT's readable M0 fixture; this is NOT a general SPIR-V assembler.

Opcode/enumerant values were checked against Khronos SPIRV-Headers tag
vulkan-sdk-1.4.328.1 (spirv.core.grammar.json). No downloads at execution time.
For a general assembler/validator use the upstream SPIRV-Tools project.
"""
from pathlib import Path
import hashlib
import re
import struct

OPS = {
    "OpMemoryModel": 14, "OpEntryPoint": 15, "OpCapability": 17,
    "OpTypeVoid": 19, "OpTypeBool": 20, "OpTypeInt": 21,
    "OpTypeFloat": 22, "OpTypeVector": 23, "OpTypePointer": 32,
    "OpTypeFunction": 33, "OpFunction": 54, "OpFunctionParameter": 55,
    "OpFunctionEnd": 56, "OpVariable": 59, "OpLoad": 61,
    "OpStore": 62, "OpInBoundsPtrAccessChain": 70, "OpDecorate": 71,
    "OpCompositeExtract": 81, "OpUConvert": 113, "OpFAdd": 129,
    "OpULessThan": 176, "OpSelectionMerge": 247, "OpLabel": 248,
    "OpBranch": 249, "OpBranchConditional": 250, "OpReturn": 253,
}
ENUM = {
    "Addresses": 4, "Kernel": 6, "Int64": 11, "Physical64": 2,
    "OpenCL": 2, "Input": 1, "CrossWorkgroup": 5,
    "BuiltIn": 11, "GlobalInvocationId": 28, "None": 0,
}
TYPED = {
    "OpFunction", "OpFunctionParameter", "OpVariable", "OpLoad",
    "OpInBoundsPtrAccessChain", "OpCompositeExtract", "OpUConvert",
    "OpFAdd", "OpULessThan",
}


def encode_fixture(source: str) -> bytes:
    lines = [line.split(";", 1)[0].strip() for line in source.splitlines()]
    lines = [line for line in lines if line]
    definitions = [line.split("=", 1)[0].strip() for line in lines if "=" in line]
    if len(set(definitions)) != len(definitions):
        raise ValueError("duplicate fixture ID")
    ids = {name: i + 1 for i, name in enumerate(definitions)}
    words = [0x07230203, 0x00010000, 0, len(ids) + 1, 0]
    for line in lines:
        result = None
        if "=" in line:
            result, line = (part.strip() for part in line.split("=", 1))
        tokens = re.findall(r'"[^"\\]*"|\S+', line)
        opcode, *args = tokens
        operands = []
        for token in args:
            if token.startswith('"'):
                data = token[1:-1].encode("utf-8") + b"\0"
                data += b"\0" * (-len(data) % 4)
                operands.extend(struct.unpack("<" + "I" * (len(data) // 4), data))
            elif token.startswith("%"):
                operands.append(ids[token])
            elif token in ENUM:
                operands.append(ENUM[token])
            else:
                operands.append(int(token, 0))
        if result:
            operands.insert(1 if opcode in TYPED else 0, ids[result])
        words.extend([((len(operands) + 1) << 16) | OPS[opcode], *operands])
    return struct.pack("<" + "I" * len(words), *words)


if __name__ == "__main__":
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/vector_add.spvasm"
    data = encode_fixture(fixture.read_text(encoding="utf-8"))
    output = fixture.with_suffix(".spv")
    output.write_bytes(data)
    print(f"vector_add.spv: {len(data)} bytes; sha256={hashlib.sha256(data).hexdigest()}")
