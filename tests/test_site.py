"""Exercise the static page's real renderer with the generated v3 payload."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional for site smoke tests")
def test_page_renders_area_scores_bounds_and_both_charts():
    html = (ROOT / "docs/index.html").read_text()
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    payload = json.loads((ROOT / "data/leaderboard.json").read_text())
    harness = """
const assert = require("node:assert/strict");
const vm = require("node:vm");
let input = "";
process.stdin.on("data", chunk => input += chunk);
process.stdin.on("end", async () => {
  const {script, payload} = JSON.parse(input);
  const nodes = new Map();
  const document = {getElementById: id => {
    if (!nodes.has(id)) nodes.set(id, {innerHTML: "", outerHTML: "", textContent: "", remove() {}});
    return nodes.get(id);
  }};
  const context = {document, fetch: async () => ({ok: true, json: async () => payload})};
  vm.runInNewContext(script, context);
  // Flush the fetch -> json -> render promise chain.
  await new Promise(resolve => setImmediate(resolve));
  const board = nodes.get("board").outerHTML;
  assert.ok(board.includes("EQB (95% CI)"));
  assert.ok(board.includes("bounds"));
  assert.ok(board.includes("9.58"));
  assert.ok(!board.includes("EQB-C") && !board.includes("EQB-L"));
  assert.equal((board.match(/<tbody>/g) || []).length, 1);
  assert.equal((board.match(/<tr>/g) || []).length, payload.rows.length + 1);
  for (const id of ["chart-cost", "chart-tokens"]) {
    const chart = nodes.get(id).innerHTML;
    assert.ok(chart.includes("<svg"));
    assert.ok(chart.includes(">EQB</text>"));
    assert.ok(!chart.includes("NaN") && !chart.includes("undefined"));
    const expected = payload.rows.filter(r => r.rankable &&
      (id === "chart-cost" ? r.cost_usd > 0 : r.total_tokens > 0)).length;
    assert.equal((chart.match(/<circle/g) || []).length, expected);
  }
  assert.ok(nodes.get("meta").textContent.includes("scoring v3.0"));
  assert.ok(nodes.get("meta").textContent.includes("horizon L11"));
});
"""
    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps({"script": script, "payload": payload}),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
