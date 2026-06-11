from __future__ import annotations

import os
from node import NodeState

_registry: dict[int, NodeState] = {}


def init_registry() -> None:
    """Populate the registry from NUM_NODES, ADMIN_USER, ADMIN_PASS env vars."""
    global _registry
    num = int(os.environ.get("NUM_NODES", "10"))
    user = os.environ.get("ADMIN_USER", "admin")
    pw = os.environ.get("ADMIN_PASS", "redfish")
    _registry = {i: NodeState(i, admin_user=user, admin_pass=pw) for i in range(1, num + 1)}


def get(node_id: int) -> NodeState | None:
    return _registry.get(node_id)


def all_nodes() -> dict[int, NodeState]:
    return dict(_registry)


def node_ids() -> list[int]:
    return sorted(_registry.keys())
