from __future__ import annotations

import json

from equationbench.runner import RunConfig, run_benchmark, select_tasks


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
    assert result.summary.score == 100.0
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


def test_select_tasks_is_balanced_for_small_limits(tiny_dataset):
    selected = select_tasks(tiny_dataset.tasks, limit=2)
    assert len(selected) == 2
    assert {task.family for task in selected} == {"linear"}
    assert [task.level for task in selected] == [1, 2]
    selected = select_tasks(tiny_dataset.tasks, limit=5)
    assert len(selected) == 5
    assert {task.level for task in selected} == {1, 2, 3, 4, 5}


def test_partial_run_limits_tasks(tiny_dataset, fake_provider_factory, tmp_path):
    from equationbench.types import ModelSpec

    spec = ModelSpec(key="fake-model", name="Fake Model", lab="Test", provider="fake", model="fake")
    provider = fake_provider_factory(spec, accuracy=1.0)
    result = run_benchmark(
        RunConfig(
            model=spec,
            dataset=tiny_dataset,
            out_dir=tmp_path / "partial",
            concurrency=4,
            retries=0,
            limit=2,
            provider=provider,
        )
    )
    assert result.summary.n == 2
    assert result.summary.correct == 2
    assert result.status == "complete"


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
            limit=1,
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
    task = select_tasks(tiny_dataset.tasks, limit=1)[0]
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
            dataset=tiny_dataset,
            out_dir=out,
            concurrency=1,
            retries=0,
            limit=1,
            provider=provider,
        )
    )
    assert provider.calls == 1
    assert result.summary.correct == 1
    assert len((out / "predictions.jsonl").read_text().splitlines()) == 1
