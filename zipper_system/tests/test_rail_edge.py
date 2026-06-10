# -*- coding: utf-8 -*-
"""Edge-chain ordering robustness (ARCHITECTURE.md sec.2, sec.9).

These exercise the PURE graph algorithm only -- no Maya required.
"""

import pytest

from zipper_system.core.rail_edge import order_edge_chain, EdgeOrderError


def test_open_chain_ordered():
    # unordered edges of the path 10-11-12-13
    edges = [(12, 13), (10, 11), (11, 12)]
    ordered, is_closed = order_edge_chain(edges)
    assert is_closed is False
    assert ordered in ([10, 11, 12, 13], [13, 12, 11, 10])
    # adjacency is preserved
    assert abs(ordered.index(11) - ordered.index(12)) == 1


def test_closed_loop_ordered():
    # square loop 0-1-2-3-0
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    ordered, is_closed = order_edge_chain(edges)
    assert is_closed is True
    assert len(ordered) == 4
    assert sorted(ordered) == [0, 1, 2, 3]
    # consecutive in the ring (wrap-around) are adjacent in the input
    ring = ordered + [ordered[0]]
    input_set = set(frozenset(e) for e in edges)
    for i in range(4):
        assert frozenset((ring[i], ring[i + 1])) in input_set


def test_duplicate_edges_tolerated():
    edges = [(0, 1), (1, 2), (1, 0)]  # (1,0) duplicates (0,1)
    ordered, is_closed = order_edge_chain(edges)
    assert is_closed is False
    assert sorted(ordered) == [0, 1, 2]


def test_branch_raises():
    # vertex 1 has degree 3 -> branch
    edges = [(0, 1), (1, 2), (1, 3)]
    with pytest.raises(EdgeOrderError):
        order_edge_chain(edges)


def test_disconnected_raises():
    # two separate segments: 0-1 and 5-6  -> 4 endpoints
    edges = [(0, 1), (5, 6)]
    with pytest.raises(EdgeOrderError):
        order_edge_chain(edges)


def test_two_disjoint_chains_raises():
    edges = [(0, 1), (1, 2), (10, 11), (11, 12)]
    with pytest.raises(EdgeOrderError):
        order_edge_chain(edges)


def test_degenerate_edge_raises():
    with pytest.raises(EdgeOrderError):
        order_edge_chain([(3, 3)])


def test_empty_raises():
    with pytest.raises(EdgeOrderError):
        order_edge_chain([])


def test_bad_pair_raises():
    with pytest.raises(EdgeOrderError):
        order_edge_chain([(1, 2, 3)])
