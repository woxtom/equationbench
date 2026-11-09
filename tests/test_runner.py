from __future__ import annotations

import json

from equationbench.frontier_run import build_ladder_bundle
from equationbench.runner import RunConfig, run_benchmark


def test_runner_writes_complete_receipt(tiny_dataset, fake_provider_factory, tmp_path):
    from equationbench.types import ModelSpec

    spec = ModelSpec(key="fake-model", name="Fake Model", lab="Test", provider="fake", model="fake")
    provider = fake_provider_factory(spec, accuracy=1.0)
    out = tmp_path / "run"
    result = run_benchmark(
        RunConfig(
            model=spec,
            dataset=tiny_dataset,
            out_dir=out,
            concurrency=4,
            retries=0,
            provider=provider,
        )
    )
    assert result.status == "complete"
    assert result.summary.correct == 5
    assert result.summary.accuracy == 1.0
    assert len(result.predictions) == 5
    assert (out / "run.json").exists()
    assert (out / "summary.json").exists()
    meta = json.loads((out / "run.json").read_text())
    assert meta["dataset"]["dataset_sha256"] == tiny_dataset.manifest["dataset_sha256"]
    assert meta["status"] == "complete"
    predictions = (out / "predictions.jsonl").read_text().splitlines()
    assert len(predictions) == 5


def test_runner_resumes_without_recalling_provider(tiny_dataset, fake_provider_factory, tmp_path):
    from equationbench.types import ModelSpec

    spec = ModelSpec(key="fake-model", name="Fake Model", lab="Test", provider="fake", model="fake")
    out = tmp_path / "run"
    first = fake_provider_factory(spec, accuracy=1.0)
    run_benchmark(
        RunConfig(
            model=spec,
            dataset=tiny_dataset,
            out_dir=out,
            concurrency=4,
            retries=0,
            provider=first,
        )
    )
    assert first.calls == 5
    second = fake_provider_factory(spec, accuracy=1.0)
    result = run_benchmark(
        RunConfig(
            model=spec,
            dataset=tiny_dataset,
            out_dir=out,
            concurrency=4,
            retries=0,
            provider=second,
        )
    )
    assert second.calls == 0
    assert result.summary.correct == 5


def test_zero_timeout_means_unlimited(tiny_dataset, fake_provider_factory, tmp_path):
    from equationbench.types import ModelSpec

    spec = ModelSpec(key="fake-model", name="Fake Model", lab="Test", provider="fake", model="fake")
    provider = fake_provider_factory(spec, accuracy=1.0)
    result = run_benchmark(
        RunConfig(
            model=spec,
            dataset=tiny_dataset,
            out_dir=tmp_path / "no-timeout",
            concurrency=1,
            retries=0,
            timeout=0,
            provider=provider,
        )
    )
    meta = json.loads((result.run_dir / "run.json").read_text())
    assert meta["config"]["timeout"] is None


def test_resume_retries_provider_errors(tiny_dataset, fake_provider_factory, tmp_path):
    import json

    from equationbench.types import ModelSpec, Prediction

    spec = ModelSpec(key="fake-model", name="Fake Model", lab="Test", provider="fake", model="fake")
    out = tmp_path / "retry"
    out.mkdir()
    one_task = build_ladder_bundle([1], tasks_per_level=1)
    task = one_task.tasks[0]
    failed = Prediction(
        task_id=task.task_id,
        model_key=spec.key,
        raw_response="",
        parsed_answer=None,
        correct=False,
        parse_status="provider_error",
        error="429 usage limit",
    )
    (out / "predictions.jsonl").write_text(json.dumps(failed.to_dict()) + "\n")
    provider = fake_provider_factory(spec, accuracy=1.0)
    result = run_benchmark(
        RunConfig(
            model=spec,
            dataset=one_task,
            out_dir=out,
            concurrency=1,
            retries=0,
            provider=provider,
        )
    )
    assert provider.calls == 1
    assert result.summary.correct == 1
    assert len((out / "predictions.jsonl").read_text().splitlines()) == 1
