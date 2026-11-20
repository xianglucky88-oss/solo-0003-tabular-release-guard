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
    return table, limit, cells, tuple(relations[key] for key in sorted(relations))
