from __future__ import annotations

import base64

from fastapi import Depends, Header, HTTPException
from typing import Annotated, Optional

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import registry
from node import NodeState


def get_node(node_id: int) -> NodeState:
    node = registry.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


def require_auth(
    node: Annotated[NodeState, Depends(get_node)],
    x_auth_token: Annotated[Optional[str], Header()] = None,
    authorization: Annotated[Optional[str], Header()] = None,
) -> NodeState:
    if x_auth_token and node.validate_token(x_auth_token):
        return node
    if authorization:
        if authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization[6:]).decode()
                username, _, password = decoded.partition(":")
                if node.validate_basic(username, password):
                    return node
            except Exception:
                pass
    raise HTTPException(status_code=401, detail="Unauthorized")
