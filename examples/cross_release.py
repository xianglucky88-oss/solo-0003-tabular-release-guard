"""Cross-release review demonstration.

Two stories are exercised through the real WSGI entry point:

1. region-hierarchy change: each release passes its single-table review on its
   own, but the verifiable cross-version mapping lets an observer pin a masked
   value once both releases are combined. A tiny node budget shows the
   "budget exhausted" outcome as a distinct verdict.

2. same name, different scope: a cell called "ridge" exists in both releases
   yet denotes a different geography. A mapping that leaves the cells separate
   is supported and the candidate publishes; a mapping that forces them equal
   fails the public balance check and is rejected as an unsupported mapping.
"""
import json

from .client import run

# --- Story 1: published v1, candidate v2 (new region hierarchy + time split) ---

V1 = {
    'table': 'district-counts-v1', 'max_count': 12,
    'cells': [
        {'id': 'district', 'count': 9, 'mode': 'public'},
        {'id': 'ridge', 'count': 2, 'mode': 'masked'},
        {'id': 'meadow', 'count': 7, 'mode': 'masked'},
        {'id': 'inapplicable', 'count': 0, 'mode': 'zero'},
    ],
    'relations': [
        {'id': 'district-sum', 'total': 'district',
         'terms': ['inapplicable', 'meadow', 'ridge']},
    ],
}

V2 = {
    'table': 'district-counts-v2', 'max_count': 12,
    'cells': [
        {'id': 'district', 'count': 9, 'mode': 'public'},
        {'id': 'ridge', 'count': 2, 'mode': 'public'},      # same slice, now public
        {'id': 'meadow', 'count': 4, 'mode': 'masked'},
        {'id': 'valley', 'count': 3, 'mode': 'masked'},    # meadow split in two
        {'id': 'inapplicable', 'count': 0, 'mode': 'zero'},
    ],
    'relations': [
        {'id': 'district-sum', 'total': 'district',
         'terms': ['inapplicable', 'meadow', 'ridge', 'valley']},
    ],
}

# Caller-provided, checkable linkage plus the cells owned by one side only.
# Same-named cells are always qualified with their release side: nothing is
# merged merely because two releases happen to use the same label.
MAPPING_A = {
    'relations': [
        # The shared slice: v2 publishes the count that v1 had masked.
        {'id': 'shared-ridge',
         'total': 'reference.ridge', 'terms': ['candidate.ridge']},
        # Hierarchy change: the v1 meadow is partitioned into two v2 cells.
        {'id': 'meadow-partition',
         'total': 'reference.meadow',
         'terms': ['candidate.meadow', 'candidate.valley']},
        {'id': 'same-district',
         'total': 'reference.district', 'terms': ['candidate.district']},
        {'id': 'same-inapplicable',
         'total': 'reference.inapplicable',
         'terms': ['candidate.inapplicable']},
    ],
    'only_reference': [],
    'only_candidate': [],
}

# --- Story 2: same-named "ridge" covers a different scope in each release ---

W1 = {
    'table': 'watershed-counts-v1', 'max_count': 20,
    'cells': [
        {'id': 'watershed', 'count': 15, 'mode': 'public'},
        {'id': 'ridge', 'count': 5, 'mode': 'public'},
        {'id': 'marsh', 'count': 6, 'mode': 'masked'},
        {'id': 'fen', 'count': 4, 'mode': 'masked'},
        {'id': 'inapplicable', 'count': 0, 'mode': 'zero'},
    ],
    'relations': [
        {'id': 'watershed-sum', 'total': 'watershed',
         'terms': ['fen', 'inapplicable', 'marsh', 'ridge']},
    ],
}

W2 = {
    'table': 'watershed-counts-v2', 'max_count': 20,
    'cells': [
        {'id': 'watershed', 'count': 18, 'mode': 'public'},
        {'id': 'ridge', 'count': 8, 'mode': 'public'},       # different boundary!
        {'id': 'terrace', 'count': 6, 'mode': 'masked'},
        {'id': 'brook', 'count': 4, 'mode': 'masked'},
        {'id': 'inapplicable', 'count': 0, 'mode': 'zero'},
    ],
    'relations': [
        {'id': 'watershed-sum', 'total': 'watershed',
         'terms': ['brook', 'inapplicable', 'ridge', 'terrace']},
    ],
}

# The honest mapping keeps the two "ridge" cells apart: names never imply
# equality, only explicit relations create linkage. The totals themselves
# differ between the re-scoped releases, so only the structural zero links.
MAPPING_B = {
    'relations': [
        {'id': 'same-inapplicable',
         'total': 'reference.inapplicable',
         'terms': ['candidate.inapplicable']},
    ],
    'only_reference': ['marsh', 'fen', 'ridge', 'watershed'],
    'only_candidate': ['brook', 'ridge', 'terrace', 'watershed'],
}

# The over-eager mapping forces the two same-named cells to be one scope.
MAPPING_B_FORCED = {
    'relations': [
        {'id': 'same-inapplicable',
         'total': 'reference.inapplicable',
         'terms': ['candidate.inapplicable']},
        {'id': 'forced-ridge',
         'total': 'reference.ridge', 'terms': ['candidate.ridge']},
    ],
    'only_reference': ['marsh', 'fen', 'watershed'],
    'only_candidate': ['brook', 'terrace', 'watershed'],
}


def probe(request):
    findings = {}

    # Story 1: each release is safe on its own.
    v1_review = request('POST', '/release/reviews', V1)
    assert v1_review['decision'] == 'allow'
    v2_review = request('POST', '/release/reviews', V2)
    assert v2_review['decision'] == 'allow'
    assert set(v2_review['cells'].values()) == {'alternative_exists'}

    # Freeze the already-public v1 manifest (no masked counts leave the trust
    # boundary) and audit v2 against it.
    v1_pub = request('POST', '/release/publications', V1)
    assert all('count' not in cell for cell in v1_pub['cells'] if cell['mode'] == 'masked')
    cross_request = {'candidate': V2, 'reference': v1_pub['id'], 'mapping': MAPPING_A}
    merged = request('POST', '/release/cross-reviews', cross_request)
    assert merged['decision'] == 'hold'
    # The v1 masked slice becomes uniquely inferable once v2 is combined.
    assert merged['cells'] == {
        'reference.meadow': 'uniquely_determined',
        'reference.ridge': 'uniquely_determined',
        'candidate.meadow': 'alternative_exists',
        'candidate.valley': 'alternative_exists',
    }
    findings['merge_exposure'] = merged['cells']

    # The held cross-review blocks publication even though v2 alone passes.
    request('POST', '/release/publications',
            {**V2, 'reference': v1_pub['id'], 'mapping': MAPPING_A}, expected=400)

    # Budget exhaustion is its own outcome, distinct from proven risk.
    starved = request('POST', '/release/cross-reviews',
                      {**cross_request, 'node_budget': 1})
    assert starved['decision'] == 'hold'
    assert set(starved['cells'].values()) == {'indeterminate'}
    findings['budget_exhausted'] = {'nodes_used': starved['nodes_used'],
                                    'cells': starved['cells']}

    # Story 2: same name, different scope.
    assert request('POST', '/release/reviews', W1)['decision'] == 'allow'
    assert request('POST', '/release/reviews', W2)['decision'] == 'allow'
    w1_pub = request('POST', '/release/publications', W1)

    # Honest, verifiable mapping: the shared-name cells stay separate.
    honest = request('POST', '/release/cross-reviews',
                     {'candidate': W2, 'reference': w1_pub['id'], 'mapping': MAPPING_B})
    assert honest['decision'] == 'allow'
    findings['same_name_kept_separate'] = honest['decision']
    published = request('POST', '/release/publications',
                        {**W2, 'reference': w1_pub['id'], 'mapping': MAPPING_B})
    assert 'count' not in next(cell for cell in published['cells'] if cell['id'] == 'terrace')

    # Forced equality contradicts the public values (ridge 5 vs ridge 8): the
    # tool refuses to merge rather than silently treating names as scopes.
    forced = request('POST', '/release/cross-reviews',
                     {'candidate': W2, 'reference': w1_pub['id'],
                      'mapping': MAPPING_B_FORCED}, expected=400)
    assert forced['reason'] == 'unsupported_mapping'
    findings['same_name_forced_merge'] = forced['reason']
    request('POST', '/release/publications',
            {**W2, 'reference': w1_pub['id'], 'mapping': MAPPING_B_FORCED}, expected=400)

    # A mapping that invents a cell is rejected for the same reason.
    broken = dict(MAPPING_A)
    broken['only_candidate'] = ['ghost-cell']
    bad = request('POST', '/release/cross-reviews',
                  {'candidate': V2, 'reference': v1_pub['id'], 'mapping': broken},
                  expected=400)
    assert bad['reason'] == 'unsupported_mapping'
    findings['unknown_cell_rejected'] = bad['reason']

    # An unqualified name that exists on both sides is ambiguous: the caller
    # must state which release's cell they mean instead of relying on labels.
    ambiguous = {
        'relations': [
            {'id': 'ambiguous-ridge', 'total': 'ridge', 'terms': ['candidate.ridge']},
            {'id': 'same-district',
             'total': 'reference.district', 'terms': ['candidate.district']},
            {'id': 'same-inapplicable',
             'total': 'reference.inapplicable',
             'terms': ['candidate.inapplicable']},
        ],
        'only_reference': ['meadow'],
        'only_candidate': ['meadow', 'valley'],
    }
    ambiguous_reply = request('POST', '/release/cross-reviews',
                              {'candidate': V2, 'reference': v1_pub['id'],
                               'mapping': ambiguous}, expected=400)
    assert ambiguous_reply['reason'] == 'unsupported_mapping'
    findings['ambiguous_name_rejected'] = ambiguous_reply['reason']

    # Asserted linkage that only becomes contradictory after the merge is
    # caught by feasibility narrowing, still as an unsupported mapping rather
    # than a (meaningless) risk verdict: the candidate's own equation forces
    # meadow+valley=7 while the mapping claims the public total 9.
    contradictory = {
        'relations': [
            {'id': 'shared-ridge',
             'total': 'reference.ridge', 'terms': ['candidate.ridge']},
            {'id': 'impossible-total',
             'total': 'reference.district',
             'terms': ['candidate.meadow', 'candidate.valley']},
        ],
        'only_reference': ['inapplicable', 'meadow'],
        'only_candidate': ['district', 'inapplicable'],
    }
    contradiction_reply = request('POST', '/release/cross-reviews',
                                  {'candidate': V2, 'reference': v1_pub['id'],
                                   'mapping': contradictory}, expected=400)
    assert contradiction_reply['reason'] == 'unsupported_mapping'
    findings['contradictory_linkage_rejected'] = contradiction_reply['reason']

    # Publishing against a reference without a mapping is refused as well.
    request('POST', '/release/publications',
            {**V2, 'reference': v1_pub['id']}, expected=400)

    # An unknown stored reference is a missing artifact, not a mapping fault.
    request('POST', '/release/cross-reviews',
            {'candidate': V2, 'reference': 'no-such-id', 'mapping': MAPPING_A},
            expected=404)

    # Trust boundary at the data model: even if someone tampers with a stored
    # manifest and adds a private count to a masked cell, it cannot re-enter
    # the review through the public-manifest parser.
    from release.model import parse_manifest
    tampered = request('GET', '/release/publications/' + v1_pub['id'])
    next(cell for cell in tampered['cells'] if cell['id'] == 'ridge')['count'] = 2
    try:
        parse_manifest(tampered)
    except ValueError:
        findings['private_count_reentry_blocked'] = True
    else:  # pragma: no cover - defensive, the assertion must hold
        raise AssertionError('manifest parser accepted a masked private count')
    return findings


if __name__ == '__main__':
    run(probe)
