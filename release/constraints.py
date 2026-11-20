def compile_view(cells, equations):
    ranges = {key: (cell.count, cell.count) for key, cell in cells.items() if cell.mode != 'masked'}
    return ranges, [{eq.total: 1, **{term: -1 for term in eq.terms}} for eq in equations]


def narrow(domains, equations):
    next_domains = domains.copy()
    changed = True
    while changed:
        changed = False
        for equation in equations:
            for key, sign in equation.items():
                lo_sum, hi_sum = 0, 0
                for peer, coefficient in equation.items():
                    if peer == key:
                        continue
                    lo, hi = next_domains[peer]
                    lo_sum += lo if coefficient == 1 else -hi
                    hi_sum += hi if coefficient == 1 else -lo
                lo, hi = next_domains[key]
                proposal = (-hi_sum, -lo_sum) if sign == 1 else (lo_sum, hi_sum)
                bounds = (max(lo, proposal[0]), min(hi, proposal[1]))
                if bounds[0] > bounds[1]:
                    return None
                if bounds != (lo, hi):
                    next_domains[key] = bounds
                    changed = True
    return next_domains
