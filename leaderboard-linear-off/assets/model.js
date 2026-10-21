/* EquationBench model detail page. */
(() => {
  const MODEL = window.EQB_MODEL;
  const BENCH = window.EQB_BENCHMARK;
  if (!MODEL) return;
  const $ = (selector, root = document) => root.querySelector(selector);
  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  const fmt = (value, digits = 1) =>
    Number.isFinite(value) ? Number(value).toFixed(digits) : "n/a";

  function familyTable() {
    const host = $("#family-table");
    if (!host) return;
    const families = BENCH.families || [];
    host.innerHTML = families
      .map((family) => {
        const row = MODEL.by_family?.[family.key];
        if (!row) return "";
        const accuracy = row.accuracy * 100;
        return `<div class="family-row">
          <span class="family-name">${escapeHtml(family.label)}</span>
          <div class="family-meter"><span style="width:${Math.max(1, accuracy)}%"></span></div>
          <span class="family-score">${fmt(accuracy)}%</span>
        </div>`;
      })
      .join("");
  }

  function levelBars() {
    const host = $("#level-bars");
    if (!host) return;
    host.innerHTML = [1, 2, 3, 4, 5]
      .map((level) => {
        const row = MODEL.by_level?.[String(level)] || { accuracy: 0, n: 0 };
        const accuracy = row.accuracy * 100;
        return `<div class="level-col" title="Level ${level}: ${fmt(accuracy)}% on ${row.n} tasks">
          <span class="level-value">${fmt(accuracy)}%</span>
          <div class="level-track"><div class="level-fill" style="height:${Math.max(2, accuracy)}%"></div></div>
          <span class="level-label">L${level}</span>
        </div>`;
      })
      .join("");
  }

  function sampleStatus(status) {
    return ["correct", "wrong", "unparseable"].includes(status) ? status : "unparseable";
  }

  function samples() {
    const host = $("#samples");
    if (!host) return;
    if (!MODEL.samples || !MODEL.samples.length) {
      host.innerHTML = `<div class="chart-empty">No samples stored for this run.</div>`;
      return;
    }
    host.innerHTML = MODEL.samples
      .map((sample) => {
        const status = sample.correct ? "correct" : sampleStatus(sample.status);
        const label = sample.correct ? "correct" : sample.status === "unparseable" ? "unparsed" : "incorrect";
        return `<details class="sample">
          <summary>
            <span class="sample-title"><span class="sample-status ${status}">${label}</span>${escapeHtml(sample.family_label)} <span class="sample-level">L${sample.level}</span></span>
            <span class="sample-level">${escapeHtml(sample.task_id)}</span>
          </summary>
          <div class="sample-body">
            <h4>Prompt</h4>
            <pre>${escapeHtml(sample.prompt)}</pre>
            <div class="sample-answer"><span>Ground truth</span><code>${escapeHtml(sample.expected)}</code><span>Model</span><code>${escapeHtml(sample.parsed ?? "—")}</code></div>
            <h4>Raw response (tail)</h4>
            <pre>${escapeHtml(sample.raw || "(empty)")}</pre>
          </div>
        </details>`;
      })
      .join("");
  }

  function motion() {
    const nodes = Array.from(document.querySelectorAll(".panel, .model-hero, .metric-strip"));
    nodes.forEach((node) => node.classList.add("reveal"));
    if (!("IntersectionObserver" in window)) {
      nodes.forEach((node) => node.classList.add("visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      }),
      { threshold: 0.06 }
    );
    nodes.forEach((node) => observer.observe(node));
  }

  familyTable();
  levelBars();
  samples();
  motion();
})();
