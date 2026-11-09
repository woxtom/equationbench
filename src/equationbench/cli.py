"""EquationBench command line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import BENCHMARK_NAME, DATASET_VERSION, __version__
from .frontier_run import bundle_from_receipt, frontier_from_predictions, run_frontier
from .ladder import (
    DEFAULT_SEASON_SEED,
    MAX_PUBLIC_LEVEL,
    OFFICIAL_CAP_LEVEL,
    build_ladder_task,
    ladder_manifest,
    size_for_level,
)
from .leaderboard import (
    CSV_OUT,
    JSON_OUT,
    MD_OUT,
    build_payload,
    render_outputs,
    stale_outputs,
    write_outputs,
)
from .providers import load_models, models_by_key
from .runner import load_predictions
from .scoring import score_predictions
from .types import Level, normalize_level

app = typer.Typer(
    name="eqb",
    help="EquationBench: exact linear-system reasoning on an open-ended ladder.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _parse_seed(value: str | None) -> int | str | None:
    if value is None:
        return None
    value = value.strip()
    if value.startswith("0x"):
        return int(value, 16)
    try:
        return int(value)
    except ValueError:
        return value


def _parse_levels(value: str) -> list[Level]:
    """Parse ``1-8``, ``4,5,8-10``, or half levels such as ``9.5,10.5``."""
    levels: set[Level] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"invalid level range: {part}")
            levels.update(range(start, end + 1))
        else:
            levels.add(normalize_level(float(part)))
    if not levels:
        raise ValueError("no levels supplied")
    if min(levels) < 1:
        raise ValueError("levels must be at least 1")
    return sorted(levels)


def _resolve_models(
    config_path: Path,
    keys: List[str] | None,
    *,
    all_models: bool,
    division: str | None = None,
    include_disabled: bool = False,
):
    models = load_models(config_path)
    by_key = models_by_key(models)
    requested: list[str] = []
    for item in keys or []:
        requested.extend(piece.strip() for piece in item.split(",") if piece.strip())
    if all_models:
        selected = [m for m in models if m.enabled]
    elif requested:
        for key in requested:
            if key not in by_key:
                console.print(f"[red]Unknown model key:[/red] {key}")
                raise typer.Exit(2)
        selected = [by_key[key] for key in requested]
    else:
        console.print("[red]Choose at least one --model or pass --all.[/red]")
        raise typer.Exit(2)
    if division:
        selected = [m for m in selected if m.division == division]
    if not include_disabled:
        disabled = [m.key for m in selected if not m.enabled]
        if disabled:
            console.print(
                f"[yellow]Skipping disabled models:[/yellow] {', '.join(disabled)}"
            )
        selected = [m for m in selected if m.enabled]
    if not selected:
        console.print("[red]No enabled models selected.[/red]")
        raise typer.Exit(2)
    return selected


@app.command()
def version() -> None:
    """Print the benchmark version."""
    console.print(f"{BENCHMARK_NAME} {__version__} (dataset {DATASET_VERSION})")


@app.command("ladder")
def ladder_command(
    max_level: int = typer.Option(
        MAX_PUBLIC_LEVEL,
        "--max-level",
        "-m",
        help="Highest ladder level to print.",
    ),
    measure: bool = typer.Option(
        False,
        "--measure",
        help="Generate one task per level and print actual prompt sizes.",
    ),
    season_seed: Optional[str] = typer.Option(
        None,
        "--season-seed",
        help="Override the public task-bank seed.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Print the open-ended linear-system ladder.

    The score is the continuous level at which a model reaches 50% exact
    accuracy.  Levels are geometric in system size, so adding a level is a
    constant step in log difficulty rather than a relabel.
    """
    if max_level < 1:
        console.print("[red]--max-level must be at least 1.[/red]")
        raise typer.Exit(2)
    seed = _parse_seed(season_seed) if season_seed is not None else DEFAULT_SEASON_SEED
    manifest = ladder_manifest(max_level, season_seed=seed)

    if measure:
        if max_level > MAX_PUBLIC_LEVEL:
            console.print(
                f"[red]--measure is limited to L{MAX_PUBLIC_LEVEL} to avoid "
                "generating enormous prompts.[/red]"
            )
            raise typer.Exit(2)
        for row in manifest["levels"]:
            task = build_ladder_task(row["level"], 0, season_seed=seed)
            row["measured_prompt_chars"] = len(task.prompt)
            row["measured_prompt_tokens"] = round(len(task.prompt) / 4)

    if as_json:
        console.print_json(json.dumps(manifest, ensure_ascii=False))
        return

    table = Table(title=f"{BENCHMARK_NAME} linear ladder", expand=False)
    table.add_column("L", justify="right", style="cyan")
    table.add_column("n", justify="right")
    table.add_column("prompt tokens", justify="right")
    table.add_column("core tasks", justify="right")
    table.add_column("precision", justify="right")
    table.add_column("zone")
    for row in manifest["levels"]:
        tokens = (
            row["measured_prompt_tokens"]
            if measure
            else row["approx_prompt_tokens"]
        )
        table.add_row(
            str(row["level"]),
            str(row["size"]),
            f"{tokens:,}",
            str(row["tasks_per_level"]),
            str(row["precision_tasks"]),
            row["zone"],
        )
    console.print(table)
    console.print(
        "[dim]size = round(3 * 2 ** ((L - 1) / 3)); "
        f"coefficients in [-{manifest['coefficient_bound']}, {manifest['coefficient_bound']}]; "
        f"solutions in [-{manifest['solution_bound']}, {manifest['solution_bound']}][/dim]"
    )
    console.print(
        f"[dim]official cap: L{OFFICIAL_CAP_LEVEL}; "
        "levels above it are long-context extensions. "
        f"Prompt tokens are {'measured' if measure else 'estimated'}.[/dim]"
    )


@app.command("list-models")
def list_models_command(
    config: Path = typer.Option(Path("config/models.toml"), "--config", "-c"),
    enabled_only: bool = typer.Option(False, "--enabled-only"),
) -> None:
    """List the model registry."""
    models = load_models(config)
    table = Table(title="EquationBench models", expand=False)
    table.add_column("Key", style="cyan")
    table.add_column("Name")
    table.add_column("Lab")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Thinking")
    table.add_column("Division")
    table.add_column("Enabled")
    table.add_column("Notes", overflow="fold")
    for model in models:
        if enabled_only and not model.enabled:
            continue
        table.add_row(
            model.key,
            model.name,
            model.lab,
            model.provider,
            model.model,
            model.thinking,
            model.division,
            "yes" if model.enabled else "[dim]no[/dim]",
            model.notes,
        )
    Console(width=180).print(table)


@app.command("run-frontier")
def run_frontier_command(
    model: Optional[List[str]] = typer.Option(None, "--model", "-m", help="Model key(s)."),
    all_models: bool = typer.Option(False, "--all", help="Run every enabled model."),
    division: Optional[str] = typer.Option(None, "--division", help="Only models in this division."),
    config: Path = typer.Option(Path("config/models.toml"), "--config", "-c"),
    levels: str = typer.Option("1-8", "--levels", help="Levels to run, e.g. 1-8, 4,5,8-10, or 9,9.5,10."),
    tasks_per_level: int = typer.Option(5, "--tasks-per-level", min=1, max=10),
    precision_levels: str = typer.Option(
        "",
        "--precision-levels",
        help="Levels that get extra precision tasks, e.g. 10-11.",
    ),
    precision_tasks: int = typer.Option(
        0,
        "--precision-tasks",
        min=0,
        max=5,
        help="Extra tasks per precision level (indices 6-10).",
    ),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Run directory (single model only)."),
    concurrency: int = typer.Option(2, "--concurrency", "-j", min=1, max=16),
    timeout: float = typer.Option(900.0, "--timeout", help="Per-task seconds; 0 means no limit."),
    retries: int = typer.Option(2, "--retries", min=0, max=8),
    thinking: Optional[str] = typer.Option(None, "--thinking", help="Override the model's thinking level."),
    max_cost: Optional[float] = typer.Option(None, "--max-cost", help="Abort a model after this USD cost."),
    bootstrap: int = typer.Option(1000, "--bootstrap", min=0, help="Frontier bootstrap replicates."),
    season_seed: Optional[str] = typer.Option(None, "--season-seed", help="Override the task-bank seed."),
    force: bool = typer.Option(False, "--force", help="Re-run tasks even if cached."),
    notes: str = typer.Option("", "--notes", help="Free-form run note."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the plan without calling models."),
    include_disabled: bool = typer.Option(False, "--include-disabled"),
) -> None:
    """Run a fixed ladder set and score the 50% frontier."""
    try:
        selected_levels = _parse_levels(levels)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    if selected_levels[-1] > MAX_PUBLIC_LEVEL:
        console.print(f"[red]levels must be at most L{MAX_PUBLIC_LEVEL}.[/red]")
        raise typer.Exit(2)
    try:
        for level in selected_levels:
            size_for_level(level)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    try:
        selected_precision_levels = (
            _parse_levels(precision_levels) if precision_levels.strip() else []
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    if selected_precision_levels and precision_tasks < 1:
        console.print("[red]--precision-tasks must be positive with --precision-levels.[/red]")
        raise typer.Exit(2)
    missing_precision = sorted(set(selected_precision_levels) - set(selected_levels))
    if missing_precision:
        console.print(
            f"[red]Precision levels are not in --levels: {missing_precision}[/red]"
        )
        raise typer.Exit(2)
    if tasks_per_level + precision_tasks > 10:
        console.print("[red]Core plus precision tasks must not exceed 10.[/red]")
        raise typer.Exit(2)

    models = _resolve_models(
        config,
        model,
        all_models=all_models,
        division=division,
        include_disabled=include_disabled,
    )
    if out is not None and len(models) > 1:
        console.print("[red]--out can only be used with one model.[/red]")
        raise typer.Exit(2)

    seed = _parse_seed(season_seed) if season_seed is not None else DEFAULT_SEASON_SEED
    total_tasks = sum(
        tasks_per_level + (precision_tasks if level in selected_precision_levels else 0)
        for level in selected_levels
    )
    console.print(
        f"[bold]{BENCHMARK_NAME} frontier run[/bold] · "
        f"L{selected_levels[0]}–L{selected_levels[-1]} · "
        f"{len(selected_levels)} levels × {tasks_per_level} core tasks"
        f" = {total_tasks} tasks"
    )
    if selected_precision_levels:
        console.print(
            f"  precision: +{precision_tasks} tasks at "
            f"L{', L'.join(str(level) for level in selected_precision_levels)}"
        )
    console.print(f"  levels: {', '.join(f'L{level}={size_for_level(level)}×{size_for_level(level)}' for level in selected_levels)}")
    for item in models:
        console.print(
            f"  • {item.name} [dim]({item.provider}/{item.model}, thinking={thinking or item.thinking})[/dim]"
        )
    if dry_run:
        console.print("[yellow]Dry run: no provider calls made.[/yellow]")
        return

    rows = []
    for item in models:
        # The bundle is rebuilt inside run_frontier; print progress by task.
        def progress(done: int, total: int, prediction) -> None:
            console.print(
                f"  [{done}/{total}] {prediction.parse_status} "
                f"{prediction.latency_ms / 1000:.0f}s"
            )

        result, score, bundle = run_frontier(
            item,
            selected_levels,
            out_dir=out if len(models) == 1 else None,
            tasks_per_level=tasks_per_level,
            precision_levels=selected_precision_levels,
            precision_tasks=precision_tasks,
            concurrency=concurrency,
            timeout=timeout,
            retries=retries,
            thinking=thinking,
            max_cost=max_cost,
            force=force,
            notes=notes,
            season_seed=seed,
            bootstrap_replicates=bootstrap,
            on_progress=progress,
        )
        valid = sum(1 for prediction in result.predictions if not prediction.is_infra)
        rows.append((item, result, score, valid / len(bundle.tasks) if bundle.tasks else 0.0))
        console.print(f"[green]Wrote {result.run_dir / 'frontier.json'}[/green]")

    table = Table(title="Frontier summary")
    table.add_column("Model")
    table.add_column("EQB-L", justify="right")
    table.add_column("Frontier size", justify="right")
    table.add_column("95% CI", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Valid")
    table.add_column("Status")
    for item, result, score, completion in rows:
        if score.censored == "upper":
            label = f"≥{score.bound:.1f}" if score.bound is not None else "≥max"
        elif score.censored == "lower":
            label = f"<{score.bound:.1f}" if score.bound is not None else "<min"
        elif score.score is not None:
            label = f"{score.score:.2f}"
        else:
            label = "—"
        size_label = f"{score.size:.1f}" if score.size is not None else "—"
        ci_label = (
            f"{score.ci[0]:.1f}–{score.ci[1]:.1f}" if score.ci is not None else "—"
        )
        cost = (
            "n/a"
            if not result.summary.cost_known
            else f"${result.summary.total_cost_usd:.3f}"
        )
        table.add_row(
            item.name,
            label,
            size_label,
            ci_label,
            cost,
            f"{completion:.0%}",
            result.status,
        )
    console.print(table)


@app.command("score")
def score_command(
    run: Path = typer.Option(..., "--run", "-r", help="Run directory."),
    bootstrap: int = typer.Option(2000, "--bootstrap", help="Bootstrap replicates."),
) -> None:
    """Re-score an existing run from its stored predictions."""
    run_json = json.loads((run / "run.json").read_text(encoding="utf-8"))
    bundle = bundle_from_receipt(run_json)
    if bundle is None:
        console.print(f"[red]{run} is not a ladder run receipt.[/red]")
        raise typer.Exit(2)
    selected_ids = set(run_json["dataset"]["selected_tasks"])
    tasks = [task for task in bundle.tasks if task.task_id in selected_ids]
    pred_by_id = {p.task_id: p for p in load_predictions(run / "predictions.jsonl")}
    selected_predictions = [pred_by_id[t.task_id] for t in tasks if t.task_id in pred_by_id]
    summary = score_predictions(selected_predictions, tasks)
    console.print_json(json.dumps(summary.to_dict(), indent=2))
    updated = {
        **run_json,
        "score": summary.to_dict(),
        "summary": summary.to_dict(),
        "frontier": frontier_from_predictions(
            selected_predictions, tasks, bootstrap_replicates=bootstrap
        ).to_dict(),
    }
    (run / "summary.json").write_text(
        json.dumps(updated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    console.print(f"[green]Updated {run / 'summary.json'}[/green]")


@app.command("build-leaderboard")
def build_leaderboard_command(
    root: Path = typer.Option(Path("."), "--root", help="Repository root."),
    bootstrap: int = typer.Option(2000, "--bootstrap", help="Bootstrap replicates per row."),
    include_probes: bool = typer.Option(False, "--include-probes", help="Include unranked probes."),
    generated_at: Optional[str] = typer.Option(
        None, "--generated-at", help="Override the build timestamp (default: newest run)."
    ),
    json_out: Path = typer.Option(JSON_OUT, "--json-out"),
    csv_out: Path = typer.Option(CSV_OUT, "--csv-out"),
    md_out: Path = typer.Option(MD_OUT, "--md-out"),
    check: bool = typer.Option(
        False, "--check", help="Fail if the published files differ from a fresh build."
    ),
) -> None:
    """Re-score every receipt and publish the leaderboard files."""
    root = root.resolve()
    payload = build_payload(
        root,
        bootstrap=bootstrap,
        include_probes=include_probes,
        generated_at=generated_at,
    )
    outputs = render_outputs(root, payload, json_out=json_out, csv_out=csv_out, md_out=md_out)
    if check:
        stale = stale_outputs(outputs)
        if stale:
            for path in stale:
                console.print(f"[red]Out of date:[/red] {path}")
            console.print("Run [bold]eqb build-leaderboard[/bold] and commit the result.")
            raise typer.Exit(1)
        console.print("[green]Leaderboard files are up to date.[/green]")
        return
    write_outputs(outputs)
    for path in outputs:
        console.print(f"Wrote {path}")
    console.print(f"ranked: {payload['ranked_count']}, unranked: {payload['unranked_count']}")


if __name__ == "__main__":  # pragma: no cover
    app()
