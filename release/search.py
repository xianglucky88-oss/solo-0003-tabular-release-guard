from .constraints import narrow


class Solver:
    """Feasibility search under one shared node budget.

    Every propagation or branch is charged exactly one node, and no call ever
    visits more nodes than the budget currently leaves, so ``budget -
    remaining`` is always the exact number of nodes spent.

    A search is a resumable stack of candidate domains.  ``step`` works the
    stack for at most ``limit`` nodes and leaves it in place, so a later call
    continues where the earlier one stopped and no work is repeated when the
    caller hands out the budget in slices.

    Branching picks the narrowest undecided variable, ties broken by the fixed
    structural ``rank`` the caller supplies, never by dict or input order.  A
    residual tie can only join cells whose rank is equal, which the caller
    treats as interchangeable, so renaming or reordering cannot change what is
    confirmed under the same budget.
    """

    def __init__(self, budget):
        self.remaining = budget

    def step(self, stack, equations, limit, rank):
        """Continue a search over ``stack`` for at most ``limit`` nodes.

        Returns True (a witness was reached), False (the stack emptied, so no
        assignment exists) or None (the allowance ran out with work left).
        Visited nodes only are charged to the shared budget.
        """
        allowance = min(limit, self.remaining)
        used = 0
        while stack and used < allowance:
            used += 1
            reduced = narrow(stack.pop(), equations)
            if reduced is None:
                continue
            lo, hi, key = min(
                ((lo, hi, key) for key, (lo, hi) in reduced.items() if lo != hi),
                key=lambda item: (item[1] - item[0], rank[item[2]], item[0], item[1]),
                default=(0, 0, None),
            )
            if key is None:
                self.remaining -= used
                return True
            mid = (lo + hi) // 2
            stack.append({**reduced, key: (mid + 1, hi)})
            stack.append({**reduced, key: (lo, mid)})
        self.remaining -= used
        if not stack:
            return False
        return None
