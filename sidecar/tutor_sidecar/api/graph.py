from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from tutor_sidecar.api.deps import require_db
from tutor_sidecar.db import repo
from tutor_sidecar.db.connection import connect
from tutor_sidecar.models import (
    ExportRequest,
    ExportResponse,
    GraphEdge,
    GraphNode,
    GraphResponse,
)
from tutor_sidecar.services.export import export_json, export_markdown, resolve_target_dir

router = APIRouter()


@router.get("/graph")
def graph(request: Request) -> GraphResponse:
    db_path = require_db(request)
    conn = connect(db_path)
    try:
        nodes = repo.graph_nodes(conn)
        edges = repo.graph_edges(conn)
    finally:
        conn.close()
    return GraphResponse(
        nodes=[
            GraphNode(
                id=row["id"],
                name=row["name"],
                status=row["status"],
                has_content=bool(row["has_content"]),
                degree=row["degree"],
            )
            for row in nodes
        ],
        edges=[
            GraphEdge(
                from_id=row["from_concept_id"],
                to_id=row["to_concept_id"],
                kind=row["kind"],
            )
            for row in edges
        ],
    )


@router.post("/export")
def export(payload: ExportRequest, request: Request) -> ExportResponse:
    db_path = require_db(request)
    try:
        target_dir = resolve_target_dir(payload.path)
        if payload.format == "markdown":
            files_written = export_markdown(db_path, target_dir)
            result_path = target_dir
        else:
            result_path = export_json(db_path, target_dir)
            files_written = 1
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"kind": "export", "message": f"Eksport nie powiódł się: {exc}"},
        ) from exc
    return ExportResponse(
        format=payload.format, path=str(result_path), files_written=files_written
    )
