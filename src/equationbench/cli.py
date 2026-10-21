"""EquationBench command line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from . import (
    BENCHMARK_NAME,
    DATASET_VERSION,
    FAMILIES,
    LEVELS,
    __version__,
)
from .dataset import (
    DEFAULT_PROFILES,
    DatasetProfile,
    load_dataset,
    secrets_dir,
    verify_dataset,
    write_dataset,
)
from .ladder import (
    DEFAULT_SEASON_SEED,
    MAX_PUBLIC_LEVEL,
    OFFICIAL_CAP_LEVEL,
    build_ladder_task,
    ladder_manifest,
)
from .providers import load_models, models_by_key
from .runner import RunConfig, run_benchmark, select_tasks
from .scoring import score_predictions
from .types import Prediction

app = typer.Typer(
    name="eqb",
    help="EquationBench: exact linear-system reasoning on an open-ended ladder.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _dataset_path(profile: str) -> Path:
    return Path("datasets") / f"equationbench-{DATASET_VERSION}-{profile}"


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


@app.command("build-dataset")
def build_dataset_command(
    profile: str = typer.Option("dev", "--profile", "-p", help="dev, test, sealed, or a custom name."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output directory."),
    per_cell: Optional[int] = typer.Option(None, "--per-cell", help="Tasks per level cell."),
    family: Optional[List[str]] = typer.Option(None, "--family", "-f", help="Restrict the dataset to one or more tracks."),
    master_seed: Optional[str] = typer.Option(None, "--master-seed", help="Override the master seed."),
    sealed: bool = typer.Option(False, "--sealed", help="Encrypt the dataset."),
    key_file: Optional[Path] = typer.Option(None, "--key-file", help="Fernet key file for sealed data."),
    seed_file: Optional[Path] = typer.Option(None, "--seed-file", help="Where to save the sealed master seed."),
    overwrite: bool = typer.Option(False, "--force", help="Overwrite an existing output directory."),
) -> None:
    """Generate a deterministic dataset from the public or private seed."""
    if profile in DEFAULT_PROFILES:
        base = DEFAULT_PROFILES[profile]
        resolved = DatasetProfile(
            name=base.name,
            per_cell=per_cell if per_cell is not None else base.per_cell,
            master_seed=master_seed if master_seed is not None else base.master_seed,
            sealed=sealed or base.sealed,
            description=base.description,
            families=tuple(family) if family else base.families,
            levels=base.levels,
            prompt_version=base.prompt_version,
        )
    else:
        resolved = DatasetProfile(
            name=profile,
            per_cell=per_cell or 1,
            master_seed=master_seed or "default",
            sealed=sealed,
            description=f"Custom EquationBench dataset {profile}.",
            families=tuple(family) if family else FAMILIES,
            levels=LEVELS,
        )
    path = out or _dataset_path(profile)
    if path.exists() and any(path.iterdir()) and not overwrite:
        console.print(f"[red]{path} already exists.[/red] Use --force to overwrite.")
        raise typer.Exit(2)
    if resolved.sealed and seed_file is None:
        seed_file = secrets_dir() / f"{profile}_seed.txt"
    bundle = write_dataset(
        resolved,
        path,
        key_file=key_file or secrets_dir() / "sealed.key",
        seed_file=seed_file,
    )
    problems = verify_dataset(bundle)
    table = Table(title=f"{BENCHMARK_NAME} dataset: {profile}")
    table.add_column("Field")
    table.add_column("Value", overflow="fold")
    table.add_row("Path", str(path))
    table.add_row("Tasks", str(len(bundle.tasks)))
    table.add_row("Cells", f"{len(resolved.families)} families x {len(resolved.levels)} levels")
    table.add_row("Per cell", str(resolved.per_cell))
    table.add_row("Dataset hash", bundle.manifest["dataset_sha256"])
    table.add_row("Master seed", "hidden (sealed)" if resolved.sealed else str(resolved.master_seed))
    table.add_row("Integrity", "ok" if not problems else f"{len(problems)} problem(s)")
    console.print(table)
    if problems:
        for problem in problems[:20]:
            console.print(f"[red]- {problem}[/red]")
        raise typer.Exit(1)
    if resolved.sealed:
        console.print(
            f"[yellow]Sealed key and seed are in {secrets_dir()} (outside the repo). "
            "Do not publish them before the reveal date.[/yellow]"
        )


@app.command("verify-dataset")
def verify_dataset_command(
    path: Path = typer.Option(..., "--path", "-p", help="Dataset directory."),
    key: Optional[str] = typer.Option(None, "--key", help="Sealed dataset key."),
    key_file: Optional[Path] = typer.Option(None, "--key-file", help="Sealed key file."),
    no_regenerate: bool = typer.Option(False, "--no-regenerate", help="Only check internal hashes."),
) -> None:
    """Verify task ids, answer hashes, and optionally regenerate every task."""
    bundle = load_dataset(path, key=key, key_file=key_file)
    problems = verify_dataset(bundle, regenerate=not no_regenerate)
    if problems:
        console.print(f"[red]{len(problems)} problem(s) found:[/red]")
        for problem in problems[:50]:
            console.print(f"[red]- {problem}[/red]")
        raise typer.Exit(1)
    console.print(
        f"[green]OK[/green] {len(bundle.tasks)} tasks; "
        f"hash {bundle.manifest['dataset_sha256'][:24]}..."
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


@app.command("show-task")
def show_task_command(
    dataset: Path = typer.Option(Path("datasets/equationbench-v1-dev"), "--dataset", "-d"),
    family: str = typer.Option("linear", "--family", "-f"),
    level: int = typer.Option(1, "--level", "-l"),
    index: int = typer.Option(0, "--index", "-i"),
    key: Optional[str] = typer.Option(None, "--key"),
    show_solution: bool = typer.Option(False, "--solution"),
) -> None:
    """Print one task (dev/test sets include answers)."""
    bundle = load_dataset(dataset, key=key)
    matches = [t for t in bundle.tasks if t.family == family and t.level == level]
    if index < 0 or index >= len(matches):
        console.print(f"[red]index out of range (0..{len(matches) - 1})[/red]")
        raise typer.Exit(2)
    task = matches[index]
    console.print(Panel(task.prompt, title=f"{task.family} L{task.level} · {task.task_id}", expand=False))
    console.rule("ground truth")
    console.print(f"[bold]Answer:[/bold] {task.answer}")
    console.print(f"[bold]Type:[/bold] {task.answer_type}")
    console.print_json(json.dumps(task.metadata))
    if show_solution:
        console.print(f"[bold]Solution note:[/bold] {task.solution}")


@app.command("decrypt-dataset")
def decrypt_dataset_command(
    path: Path = typer.Option(..., "--path", "-p"),
    out: Path = typer.Option(..., "--out", "-o"),
    key: Optional[str] = typer.Option(None, "--key"),
    key_file: Optional[Path] = typer.Option(None, "--key-file"),
) -> None:
    """Decrypt a sealed dataset to a local working directory."""
    bundle = load_dataset(path, key=key, key_file=key_file)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "tasks.jsonl").open("w", encoding="utf-8") as handle:
        for task in bundle.tasks:
            handle.write(json.dumps(task.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    with (out / "prompts.jsonl").open("w", encoding="utf-8") as handle:
        for task in bundle.tasks:
            handle.write(json.dumps(task.public_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    (out / "manifest.json").write_text(
        json.dumps(bundle.manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    console.print(f"[green]Decrypted {len(bundle.tasks)} tasks to {out}[/green]")
    console.print("[yellow]Do not commit this directory. It contains answers.[/yellow]")


def _run_one(
    model,
    dataset,
    *,
    out_dir: Optional[Path],
    concurrency: int,
    timeout: float,
    retries: int,
    thinking: Optional[str],
    limit: Optional[int],
    families: Optional[List[str]],
    levels: Optional[List[int]],
    force: bool,
    max_cost: Optional[float],
    notes: str,
    quiet: bool = False,
):
    selected = select_tasks(dataset.tasks, families=families, levels=levels, limit=limit)
    progress = Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=not quiet,
    )
    progress_task = progress.add_task(model.name, total=len(selected))

    def on_progress(done: int, total: int, prediction: Prediction) -> None:
        marker = "✓" if prediction.correct else "·"
        progress.update(
            progress_task,
            completed=done,
            description=f"{model.name}  [dim]{marker} {prediction.parse_status}[/dim]",
        )

    config = RunConfig(
        model=model,
        dataset=dataset,
        out_dir=out_dir,
        concurrency=concurrency,
        timeout=timeout if timeout and timeout > 0 else None,
        retries=retries,
        thinking=thinking,
        families=families,
        levels=levels,
        limit=limit,
        force=force,
        max_cost=max_cost,
        notes=notes,
        on_progress=on_progress,
    )
    with progress:
        result = run_benchmark(config)

    summary = result.summary
    table = Table(title=f"{model.name} · {result.status}")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Score (difficulty-weighted)", f"{summary.score:.1f}")
    table.add_row("95% CI", f"{summary.score_ci[0]:.1f} – {summary.score_ci[1]:.1f}")
    table.add_row("Accuracy", f"{summary.accuracy * 100:.1f}%")
    table.add_row("Correct", f"{summary.correct} / {summary.n}")
    table.add_row("Cost", "unknown" if not summary.cost_known else f"${summary.total_cost_usd:.4f}")
    table.add_row("Latency (median)", f"{summary.median_latency_ms or 0} ms")
    table.add_row("Reasoning (actual)", ", ".join(result.metadata.get("actual_thinking_levels", {})) or "n/a")
    table.add_row("Run directory", str(result.run_dir))
    console.print(table)
    if result.status != "complete":
        console.print(f"[yellow]Run status: {result.status} ({result.aborted_reason})[/yellow]")
    return result


@app.command("run")
def run_command(
    model: Optional[List[str]] = typer.Option(None, "--model", "-m", help="Model key(s); repeat or comma-separate."),
    all_models: bool = typer.Option(False, "--all", help="Run every enabled model."),
    division: Optional[str] = typer.Option(None, "--division", help="Only models in this division."),
    config: Path = typer.Option(Path("config/models.toml"), "--config", "-c"),
    dataset: Path = typer.Option(Path("datasets/equationbench-v1-test"), "--dataset", "-d"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Run directory (single model only)."),
    concurrency: int = typer.Option(4, "--concurrency", "-j", min=1, max=32),
    timeout: float = typer.Option(0.0, "--timeout", help="Per-task wall-clock limit in seconds; 0 means wait until the model answers."),
    retries: int = typer.Option(2, "--retries", min=0, max=8),
    thinking: Optional[str] = typer.Option(None, "--thinking", help="Override the model's thinking level."),
    limit: Optional[int] = typer.Option(None, "--limit", help="Balanced task limit per model."),
    family: Optional[List[str]] = typer.Option(None, "--family", "-f", help="Restrict to a family."),
    level: Optional[List[int]] = typer.Option(None, "--level", "-l", help="Restrict to a level."),
    force: bool = typer.Option(False, "--force", help="Re-run tasks even if cached."),
    max_cost: Optional[float] = typer.Option(None, "--max-cost", help="Abort a model after this USD cost."),
    notes: str = typer.Option("", "--notes", help="Free-form run note."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the plan without calling models."),
    include_disabled: bool = typer.Option(False, "--include-disabled"),
) -> None:
    """Run one or more models on a dataset."""
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
    bundle = load_dataset(dataset)
    selected = select_tasks(bundle.tasks, families=family, levels=level, limit=limit)
    if not selected:
        console.print("[red]No tasks matched the filters.[/red]")
        raise typer.Exit(2)
    console.print(
        f"[bold]{BENCHMARK_NAME} run[/bold] · dataset {bundle.manifest.get('name')} · "
        f"{len(selected)} tasks · {len(models)} model(s)"
    )
    for item in models:
        console.print(
            f"  • {item.name} [dim]({item.provider}/{item.model}, thinking={thinking or item.thinking})[/dim]"
        )
    if dry_run:
        console.print("[yellow]Dry run: no provider calls made.[/yellow]")
        return
    results = []
    for item in models:
        result = _run_one(
            item,
            bundle,
            out_dir=out if len(models) == 1 else None,
            concurrency=concurrency,
            timeout=timeout,
            retries=retries,
            thinking=thinking,
            limit=limit,
            families=family,
            levels=level,
            force=force,
            max_cost=max_cost,
            notes=notes,
        )
        results.append(result)
    console.print("\n[bold]Run summary[/bold]")
    table = Table()
    table.add_column("Model")
    table.add_column("Score", justify="right")
    table.add_column("95% CI", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Status")
    for item, result in zip(models, results):
        table.add_row(
            item.name,
            f"{result.summary.score:.1f}",
            f"{result.summary.score_ci[0]:.1f}–{result.summary.score_ci[1]:.1f}",
            "n/a" if not result.summary.cost_known else f"${result.summary.total_cost_usd:.3f}",
            result.status,
        )
    console.print(table)


@app.command("score")
def score_command(
    run: Path = typer.Option(..., "--run", "-r", help="Run directory."),
    dataset: Optional[Path] = typer.Option(None, "--dataset", "-d", help="Override dataset path."),
    bootstrap: int = typer.Option(2000, "--bootstrap", help="Bootstrap replicates."),
) -> None:
    """Re-score an existing run from its stored predictions."""
    run_json = json.loads((run / "run.json").read_text(encoding="utf-8"))
    dataset_path = dataset or Path(run_json["dataset"]["path"])
    bundle = load_dataset(dataset_path)
    selected_ids = set(run_json["dataset"]["selected_tasks"])
    tasks = [task for task in bundle.tasks if task.task_id in selected_ids]
    predictions = []
    for line in (run / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            predictions.append(Prediction.from_dict(json.loads(line)))
    pred_by_id = {p.task_id: p for p in predictions}
    selected_predictions = [pred_by_id[t.task_id] for t in tasks if t.task_id in pred_by_id]
    summary = score_predictions(selected_predictions, tasks, bootstrap_replicates=bootstrap)
    console.print_json(json.dumps(summary.to_dict(), indent=2))
    (run / "summary.json").write_text(
        json.dumps(
            {**run_json, "score": summary.to_dict(), "summary": summary.to_dict()},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    console.print(f"[green]Updated {run / 'summary.json'}[/green]")



if __name__ == "__main__":  # pragma: no cover
    app()
