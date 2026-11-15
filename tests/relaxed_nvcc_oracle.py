"""Independent exact readback/guard oracle for the genuine compiler consumer."""


def expected(seed, *, noop=False):
    if type(seed) is not int or not 1 <= seed <= 1000000:
        raise ValueError('invalid seed')
    inputs = [0, 1, 0x7fffffff, 0x80000000, 0x80000001, 0xffffffff,
              (seed * 2654435761) & 0xffffffff, seed ^ 0xa5a5a5a5]
    wides = [0, 1, 0xdeadbeef80000001, 0xffffffffffffffff]
    rows = []
    for i, value in enumerate(inputs):
        wide = wides[(i + seed) % 4] ^ ((seed << 32) if i >= 6 else 0)
        rows.append({'wide': [0x12345678cafebabe] * 2 +
                     [0xffffffffffffffff if noop else value] + [0x12345678cafebabe] * 2,
                     'narrow': [0xcafebabe] * 2 +
                     [value if noop else wide & 0xffffffff] + [0xcafebabe] * 2})
    return {'device': 'Intel(R) Arc(TM) B390 GPU', 'seed': seed,
            'rows': rows, 'main_entered': 1}


def validate(value, seed, *, noop=False):
    wanted = expected(seed, noop=noop)

    def exact(actual, reference):
        if isinstance(reference, dict):
            return type(actual) is dict and set(actual) == set(reference) and all(
                exact(actual[k], v) for k, v in reference.items())
        if isinstance(reference, list):
            return type(actual) is list and len(actual) == len(reference) and all(
                exact(a, b) for a, b in zip(actual, reference))
        return type(actual) is type(reference) and actual == reference

    return [] if exact(value, wanted) else ['compiler consumer numerical/guard/schema mismatch']
