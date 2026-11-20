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
