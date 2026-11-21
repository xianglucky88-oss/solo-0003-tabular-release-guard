import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    key: str
    count: int
    mode: str


@dataclass(frozen=True)
class Equation:
    key: str
    total: str
    terms: tuple[str, ...]


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
        raise ValueError('invalid table, cell or relation identifier')
    return value


MAX_CANDIDATE_MINIMUM = 257
CANDIDATE_POLICY_FIELDS = ('min_candidates', 'minimum_candidates', 'required_candidates')


def parse_policy(payload, cells):
    """Read the optional per-cell minimum candidate requirement.

    A request without the field keeps the legacy semantics: every masked cell
    only has to admit one feasible value other than the observed one.  When a
    field is present it must name masked cells and require a positive number of
    mutually distinct integer candidates, the observed value included.  The
    canonical field is ``min_candidates``; the documented aliases are accepted
    for callers that spell the requirement differently.
    """
    present = [name for name in CANDIDATE_POLICY_FIELDS if name in payload]
    if not present:
        return {}
    raw = payload[present[0]]
    if any(payload[name] != raw for name in present[1:]):
        raise ValueError('conflicting candidate policy fields')
    if not isinstance(raw, dict):
        raise ValueError('min_candidates must be an object keyed by masked cell')
    policy = {}
    for key, value in raw.items():
        key = identifier(key)
        if key not in cells or cells[key].mode != 'masked':
            raise ValueError('min_candidates may only name masked cells')
        if type(value) is not int or not 1 <= value <= MAX_CANDIDATE_MINIMUM:
            raise ValueError('min_candidates values must be integers between 1 and 257')
        policy[key] = value
    return policy


def parse(payload):
    table = identifier(payload['table'])
    rows, equations = payload['cells'], payload['relations']
    limit = payload['max_count']
    if type(limit) is not int or not 1 <= limit <= 256 or not 1 <= len(rows) <= 60 or len(equations) > 60:
        raise ValueError('table bounds: 1..60 cells, at most 60 relations, max_count 1..256')
    cells = {}
    for row in rows:
        key, count, mode = identifier(row['id']), row['count'], row['mode']
        if key in cells or type(count) is not int or not 0 <= count <= limit:
            raise ValueError('duplicate cell or count outside declared bounds')
        if mode not in ('public', 'masked', 'zero') or (mode == 'zero' and count != 0):
            raise ValueError('invalid disclosure mode or structural zero')
        cells[key] = Cell(key, count, mode)
    relations = {}
    for row in equations:
        key, total = identifier(row['id']), identifier(row['total'])
        terms = tuple(sorted(map(identifier, row['terms'])))
        if key in relations or total not in cells or total in terms or not terms or len(set(terms)) != len(terms):
            raise ValueError('invalid relation structure')
        if any(term not in cells for term in terms) or cells[total].count != sum(cells[t].count for t in terms):
            raise ValueError(f'relation {key} does not balance or references a missing cell')
        relations[key] = Equation(key, total, terms)
    return table, limit, cells, tuple(relations[key] for key in sorted(relations)), parse_policy(payload, cells)
