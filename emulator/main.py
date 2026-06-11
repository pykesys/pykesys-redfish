"""Redfish BMC Emulator — FastAPI application entry point.

Serves NUM_NODES virtual BMC nodes, each at /bmc/{node_id}/redfish/v1/,
plus a central control API at /sim/ for injecting events and scenarios.

Environment variables:
  NUM_NODES   Number of virtual nodes to create (default: 10)
  ADMIN_USER  Admin username for all nodes (default: admin)
  ADMIN_PASS  Admin password for all nodes (default: redfish)
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import registry
from routes.redfish import router as redfish_router
from routes.sim import router as sim_router

app = FastAPI(
    title="Redfish BMC Emulator",
    description="Multi-node Redfish emulator for SDK and integration testing",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def startup():
    registry.init_registry()
    num = len(registry.node_ids())
    print(f"[emulator] {num} nodes ready (admin user: {os.environ.get('ADMIN_USER', 'admin')})")
    print(f"[emulator] Nodes accessible at /bmc/1 through /bmc/{num}/redfish/v1/")
    print(f"[emulator] Control API at /sim/  |  Docs at /docs")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "nodes": registry.node_ids()}


# Mount the Redfish router for each possible node_id prefix.
# FastAPI resolves {node_id} as an integer path parameter.
app.include_router(redfish_router, prefix="/bmc/{node_id}")

# Sim control API (no node prefix — operates fleet-wide)
app.include_router(sim_router)
