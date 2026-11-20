def manifest(table, limit, cells, equations):
    return {
        'table': table, 'max_count': limit,
        'cells': [{'id': cell.key, 'mode': cell.mode,
                   **({'count': cell.count} if cell.mode != 'masked' else {})}
                  for cell in sorted(cells.values(), key=lambda cell: cell.key)],
        'relations': [{'id': row.key, 'total': row.total, 'terms': list(row.terms)} for row in equations],
    }
