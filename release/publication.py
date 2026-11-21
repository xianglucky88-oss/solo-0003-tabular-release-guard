from .model import MAX_CANDIDATE_MINIMUM
from .review import LEGACY_MINIMUM


def protection_policy(cells, policy):
    """Describe the protection standard that an artifact was admitted under.

    The record names the minimum number of distinct feasible integer candidates
    required for every masked cell.  It deliberately contains no observed
    count, candidate enumeration result or solver trace: it only states the
    standard, so the same standard yields the same bytes regardless of the raw
    masked values behind a request.
    """
    minimums = {cell.key: policy.get(cell.key, LEGACY_MINIMUM)
                for cell in sorted(cells.values(), key=lambda cell: cell.key)
                if cell.mode == 'masked'}
    return {
        'standard': 'distinct_integer_candidates_per_masked_cell',
        'candidate_minimums': minimums,
        'legacy_equivalent_at': LEGACY_MINIMUM,
        'candidate_minimum_ceiling': MAX_CANDIDATE_MINIMUM,
    }


def manifest(table, limit, cells, equations, policy=None):
    return {
        'table': table, 'max_count': limit,
        'cells': [{'id': cell.key, 'mode': cell.mode,
                   **({'count': cell.count} if cell.mode != 'masked' else {})}
                  for cell in sorted(cells.values(), key=lambda cell: cell.key)],
        'relations': [{'id': row.key, 'total': row.total, 'terms': list(row.terms)} for row in equations],
        'protection': protection_policy(cells, policy or {}),
    }
