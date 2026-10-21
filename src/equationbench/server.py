"""FastAPI server for leaderboard data and submission review."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import BENCHMARK_NAME, __version__
from .dataset import load_dataset
from .db import create_submission, get_submission, list_submissions, update_status
from .scoring import score_predictions
from .types import Prediction
from .verify import grade_response


def _token_ok(token: str | None) -> bool:
    expected = os.environ.get("EQB_ADMIN_TOKEN")
    if not expected:
        return True
    return token == expected


def _require_token(token: str | None) -> None:
    if not _token_ok(token):
        raise HTTPException(status_code=401, detail="invalid or missing EQB_ADMIN_TOKEN")


def _validate_submission(
    body: dict[str, Any], dataset_path: Path
) -> tuple[list[Prediction], list[dict[str, Any]], dict[str, Any], list[Any]]:
    bundle = load_dataset(dataset_path)
    tasks = bundle.tasks
    tasks_by_id = {task.task_id: task for task in tasks}
    dataset_hash = str(bundle.manifest.get("dataset_sha256", ""))
    if body.get("dataset_sha256") != dataset_hash:
        raise HTTPException(status_code=400, detail="dataset_sha256 does not match the server dataset")
    selected = body.get("selected_tasks")
    if not isinstance(selected, list) or set(selected) != set(tasks_by_id):
        raise HTTPException(status_code=400, detail="submission must cover the full fixed task set")
    raw_predictions = body.get("predictions")
    if not isinstance(raw_predictions, list):
        raise HTTPException(status_code=400, detail="predictions must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for row in raw_predictions:
        if not isinstance(row, dict) or "task_id" not in row:
            raise HTTPException(status_code=400, detail="each prediction needs a task_id")
        by_id[str(row["task_id"])] = row
    if set(by_id) != set(tasks_by_id):
        raise HTTPException(status_code=400, detail="predictions must cover every task exactly once")
    predictions: list[Prediction] = []
    for task in tasks:
        row = by_id[task.task_id]
        raw = str(row.get("raw_response", ""))
        graded = grade_response(raw, task.answer, task.answer_type)
        predictions.append(
            Prediction(
                task_id=task.task_id,
                model_key=str(body.get("model", {}).get("key", "submitted")),
                raw_response=raw,
                parsed_answer=graded.parsed_answer,
                correct=graded.correct,
                parse_status=graded.status,
                error=graded.error,
                latency_ms=int(row.get("latency_ms", 0) or 0),
                usage=row.get("usage", {}) if isinstance(row.get("usage", {}), dict) else {},
                cost_usd=row.get("cost_usd"),
                attempts=int(row.get("attempts", 1) or 1),
                model_info=row.get("model_info", {}) if isinstance(row.get("model_info", {}), dict) else {},
                stop_reason=row.get("stop_reason"),
            )
        )
    summary = score_predictions(predictions, tasks)
    model = body.get("model")
    if not isinstance(model, dict) or not model.get("key") or not model.get("name"):
        raise HTTPException(status_code=400, detail="model must include key and name")
    notes = str(body.get("notes", ""))
    return predictions, [p.to_dict() for p in predictions], summary.to_dict(), [model, notes, dataset_hash]


def create_app(db_path: Path | str = Path("eqb.sqlite"), dataset_path: Path | str = Path("datasets/equationbench-v1-test"), leaderboard_dir: Path | str = Path("leaderboard")) -> FastAPI:
    app = FastAPI(title=f"{BENCHMARK_NAME} API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    db_path = Path(db_path)
    dataset_path = Path(dataset_path)
    leaderboard_dir = Path(leaderboard_dir)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "benchmark": BENCHMARK_NAME, "version": __version__}

    @app.get("/api/leaderboard")
    def leaderboard() -> JSONResponse:
        path = leaderboard_dir / "data" / "leaderboard.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="leaderboard has not been built")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/models/{key}")
    def model_detail(key: str) -> JSONResponse:
        path = leaderboard_dir / "data" / "leaderboard.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="leaderboard has not been built")
        data = json.loads(path.read_text(encoding="utf-8"))
        for model in data.get("models", []):
            if model.get("key") == key:
                detail_path = leaderboard_dir / "data" / "models" / f"{model.get('slug')}.json"
                if detail_path.exists():
                    return JSONResponse(json.loads(detail_path.read_text(encoding="utf-8")))
                return JSONResponse(model)
        raise HTTPException(status_code=404, detail="model not found")

    @app.post("/api/submissions")
    def submit(body: dict[str, Any], x_eqb_token: str | None = Header(default=None)) -> JSONResponse:
        _require_token(x_eqb_token)
        predictions, raw_predictions, summary, extras = _validate_submission(body, dataset_path)
        model, notes, dataset_hash = extras
        submission_id = create_submission(
            db_path,
            model=model,
            dataset_sha256=dataset_hash,
            summary=summary,
            predictions=raw_predictions,
            notes=notes,
        )
        return JSONResponse(
            {
                "id": submission_id,
                "status": "pending",
                "summary": summary,
                "message": "Submission stored for review. It is not on the leaderboard until approved.",
            },
            status_code=201,
        )

    @app.get("/api/submissions")
    def submissions(
        status: str | None = None,
        x_eqb_token: str | None = Header(default=None),
    ) -> JSONResponse:
        _require_token(x_eqb_token)
        return JSONResponse({"submissions": list_submissions(db_path, status)})

    @app.get("/api/submissions/{submission_id}")
    def submission(submission_id: int, x_eqb_token: str | None = Header(default=None)) -> JSONResponse:
        _require_token(x_eqb_token)
        data = get_submission(db_path, submission_id)
        if data is None:
            raise HTTPException(status_code=404, detail="submission not found")
        return JSONResponse(data)

    @app.post("/api/submissions/{submission_id}/approve")
    def approve(submission_id: int, x_eqb_token: str | None = Header(default=None)) -> JSONResponse:
        _require_token(x_eqb_token)
        if not update_status(db_path, submission_id, "approved"):
            raise HTTPException(status_code=404, detail="submission not found")
        return JSONResponse(
            {
                "id": submission_id,
                "status": "approved",
                "message": "Approved. Add the run artifacts and rebuild the leaderboard to publish.",
            }
        )

    if leaderboard_dir.exists():
        app.mount("/", StaticFiles(directory=leaderboard_dir, html=True), name="leaderboard")
    else:
        @app.get("/")
        def index() -> dict[str, Any]:
            return {
                "benchmark": BENCHMARK_NAME,
                "version": __version__,
                "message": "Build the leaderboard with `eqb leaderboard build` to serve the static site.",
            }

    return app
