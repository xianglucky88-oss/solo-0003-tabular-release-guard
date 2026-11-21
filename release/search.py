from .constraints import narrow


class Exhausted(Exception):
    pass


class Solver:
    def __init__(self, equations, budget):
        self.equations = equations
        self.remaining = budget

    def feasible(self, domains):
        stack = [domains]
        while stack:
            if not self.remaining:
                raise Exhausted
            self.remaining -= 1
            reduced = narrow(stack.pop(), self.equations)
            if reduced is None:
                continue
            lo, hi, key = min(
                ((lo, hi, key) for key, (lo, hi) in reduced.items() if lo != hi),
                key=lambda item: (item[1] - item[0], item[2]), default=(0, 0, None),
            )
            if key is None:
                return True
            mid = (lo + hi) // 2
            stack.append({**reduced, key: (mid + 1, hi)})
            stack.append({**reduced, key: (lo, mid)})
        return False

    def has_alternative(self, domains, key, observed):
        """Legacy test: can the cell take at least one value other than observed?"""
        lo, hi = domains[key]
        for bounds in ((lo, observed - 1), (observed + 1, hi)):
            if bounds[0] <= bounds[1] and self.feasible({**domains, key: bounds}):
                return True
        return False

    def count_distinct(self, domains, key, observed, required):
        """Count distinct feasible integers for one cell, stopping at required.

        Values are tested individually, so integer holes are respected instead
        of being approximated by ``max - min + 1``.  The observed assignment is
        known to satisfy every relation (the parsed table balances), hence it is
        counted as one candidate without spending budget.

        Returns ``(found, exact)``.  ``found`` is a witnessed lower bound when
        ``exact`` is false (the count reached ``required`` and enumeration
        stopped); otherwise it is the exact number of feasible values.
        """
        lo, hi = domains[key]
        if required <= 1:
            return 1, False
        count = 1
        for value in range(lo, hi + 1):
            if value == observed:
                continue
            if self.feasible({**domains, key: (value, value)}):
                count += 1
                if count >= required:
                    return count, False
        return count, True
