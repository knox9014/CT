"""Independent full-device-buffer oracle for mixed pointer alignment."""
N, G = 17, 64
TOTAL = N + 2 * G + 2


def expected(seed, *, noop=False):
    if type(seed) is not int or not 1 <= seed <= 1000000:
        raise ValueError('invalid seed')
    values = [0, 1, 0x7fffffff, 0x80000000, 0x80000001, 0xffffffff]
    values += [(seed * 17 + i * 2654435761) & 0xffffffff for i in range(6, N)]
    inputs = [0xcafebabe] * TOTAL
    inputs[G + 1:G + 1 + N] = values
    wide = [0xdeadbeefcafebabe] * TOTAL
    wide[G:G + N] = [v ^ 0xffffffffffffffff for v in values]
    negative = wide.copy()
    narrow = [0xcafebabe] * TOTAL
    narrow[G + 1:G + 1 + N] = [v ^ 0xffffffff for v in values]
    if not noop:
        wide[G:G + N] = values
        narrow[G + 1:G + 1 + N] = values
    return dict(device='Intel(R) Arc(TM) B390 GPU', seed=seed,
                invalid=0 if noop else 1, negative=negative, wide=wide,
                narrow=narrow, input=inputs)


def validate(value, seed, *, noop=False):
    def exact(a, b):
        if type(b) is dict:
            return type(a) is dict and a.keys() == b.keys() and all(exact(a[k], v) for k,v in b.items())
        if type(b) is list:
            return type(a) is list and len(a) == len(b) and all(exact(x,y) for x,y in zip(a,b))
        return type(a) is type(b) and a == b
    return [] if exact(value, expected(seed, noop=noop)) else ['mixed-pointer numerical/guard/schema mismatch']
