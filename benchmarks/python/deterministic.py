"""Versioned integer-only randomness for workload artifacts (not cryptography)."""

PRNG_VERSION = "splitmix64-v1"
UINT64_MAX = (1 << 64) - 1
MAX_DRAWS = 128


class SplitMix64:
    """The seed is the initial 64-bit state; each draw first increments it."""

    def __init__(self, seed):
        if type(seed) is not int or not 0 <= seed <= UINT64_MAX:
            raise ValueError("seed must be a uint64 integer")
        self.state = seed

    def next_u64(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & UINT64_MAX
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & UINT64_MAX
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & UINT64_MAX
        return value ^ (value >> 31)

    def below(self, bound):
        """Uniform [0,bound), rejecting the short residue prefix; bounded retry."""
        if type(bound) is not int or not 1 <= bound <= 1 << 64:
            raise ValueError("sampling bound must be in [1, 2^64]")
        threshold = (1 << 64) % bound
        for _ in range(MAX_DRAWS):
            value = self.next_u64()
            if value >= threshold:
                return value % bound
        raise ValueError("bounded integer sampling exhausted 128 draws")


def sample_ranks(random, population, count):
    """Floyd sampling: count draws, no duplicate-edge rejection, sorted result."""
    if (type(population) is not int or not 0 <= population <= UINT64_MAX or
            type(count) is not int or not 0 <= count <= population):
        raise ValueError("invalid sampling population/count")
    chosen = set()
    for last in range(population - count, population):
        candidate = random.below(last + 1)
        chosen.add(last if candidate in chosen else candidate)
    return sorted(chosen)


class EligiblePool:
    """Sorted initial IDs; O(1) uniform draw and swap-with-last removal."""

    def __init__(self, indices):
        self.items = list(indices)
        self.positions = {value: index for index, value in enumerate(self.items)}
        if len(self.positions) != len(self.items):
            raise ValueError("duplicate eligible index")

    def choose(self, random):
        if not self.items:
            raise ValueError("no eligible positive-weight edge (decrease budget exhausted)")
        return self.items[random.below(len(self.items))]

    def discard(self, value):
        position = self.positions.pop(value, None)
        if position is None:
            return
        last = self.items.pop()
        if position < len(self.items):
            self.items[position] = last
            self.positions[last] = position
