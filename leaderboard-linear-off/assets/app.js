/* EquationBench leaderboard — vanilla JS, no external dependencies. */
(() => {
  const DATA = window.EQB_DATA;
  if (!DATA || !DATA.models) return;
  const BENCH = DATA.benchmark;
  const FAMILIES = BENCH.families || [];
  const state = {
    division: "standard",
    lab: "all",
    query: "",
    sort: "rank",
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const fmt = (value, digits = 1) =>
    Number.isFinite(value) ? Number(value).toFixed(digits) : "n/a";

  const scoreColor = (score) => (score >= 75 ? "var(--lime)" : score >= 50 ? "var(--gold)" : "var(--rose)");

  const divisions = [...new Set(DATA.models.map((model) => model.division))];
  if (!divisions.includes(state.division)) state.division = divisions[0] || "standard";

  function populateFilters() {
    const divisionSelect = $("#division-filter");
    if (divisionSelect) {
      divisionSelect.innerHTML = [
        ...(divisions.length > 1 ? ['<option value="all">All divisions</option>'] : []),
        ...divisions.map((division) => `<option value="${escapeHtml(division)}">${escapeHtml(division)}</option>`),
      ].join("");
      divisionSelect.value = state.division;
      if (divisions.length <= 1) {
        const control = divisionSelect.closest(".control");
        if (control) control.style.display = "none";
      }
      divisionSelect.addEventListener("change", () => {
        state.division = divisionSelect.value;
        render();
      });
    }
    const labs = [...new Set(DATA.models.map((model) => model.lab))].sort();
    const labSelect = $("#lab-filter");
    if (labSelect) {
      labSelect.innerHTML = ['<option value="all">All labs</option>', ...labs.map((lab) => `<option value="${escapeHtml(lab)}">${escapeHtml(lab)}</option>`)].join("");
      labSelect.addEventListener("change", () => {
        state.lab = labSelect.value;
        render();
      });
    }
    const search = $("#search-input");
    if (search) {
      search.addEventListener("input", () => {
        state.query = search.value.trim().toLowerCase();
        render();
      });
    }
    const sortSelect = $("#sort-select");
    if (sortSelect) {
      sortSelect.addEventListener("change", () => {
        state.sort = sortSelect.value;
        render();
      });
    }
  }

  function filteredModels() {
    let models = DATA.models.filter((model) => {
      if (state.division !== "all" && model.division !== state.division) return false;
      if (state.lab !== "all" && model.lab !== state.lab) return false;
      if (state.query) {
        const haystack = [model.name, model.lab, model.provider, model.model_id].join(" ").toLowerCase();
        if (!haystack.includes(state.query)) return false;
      }
      return true;
    });
    const sorters = {
      rank: (a, b) => {
        const ar = state.division === "all" ? a.rank : a.rank_division;
        const br = state.division === "all" ? b.rank : b.rank_division;
        return ar - br;
      },
      score: (a, b) => b.score - a.score,
      cost: (a, b) => {
        if (a.cost_per_100 == null && b.cost_per_100 == null) return 0;
        if (a.cost_per_100 == null) return 1;
        if (b.cost_per_100 == null) return -1;
        return a.cost_per_100 - b.cost_per_100;
      },
      latency: (a, b) => {
        if (a.median_latency_ms == null && b.median_latency_ms == null) return 0;
        if (a.median_latency_ms == null) return 1;
        if (b.median_latency_ms == null) return -1;
        return a.median_latency_ms - b.median_latency_ms;
      },
      name: (a, b) => a.name.localeCompare(b.name),
    };
    models = [...models].sort(sorters[state.sort] || sorters.rank);
    return models;
  }

  function trackBars(model) {
    if (BENCH.track_filter) {
      return [1, 2, 3, 4, 5].map((level) => {
        const row = model.by_level?.[String(level)] || { accuracy: 0, n: 0 };
        const score = row.accuracy * 100;
        const height = Math.max(4, Math.min(26, 4 + score * 0.22));
        return `<span class="track-bar" style="height:${height}px;background:${scoreColor(score)}" title="L${level}: ${fmt(score)}% on ${row.n} tasks"></span>`;
      }).join("");
    }
    return FAMILIES.map((family) => {
      const score = model.by_family?.[family.key]?.score ?? 0;
      const height = Math.max(4, Math.min(26, 4 + score * 0.22));
      return `<span class="track-bar" style="height:${height}px;background:${scoreColor(score)}" title="${escapeHtml(family.label)}: ${fmt(score)} EQB Score"></span>`;
    }).join("");
  }

  function costCell(model) {
    if (!model.cost_known || model.cost_per_100 == null) {
      return `<span class="muted">n/a</span>`;
    }
    if (model.cost_per_100 === 0) return `free<small>provider-reported</small>`;
    return `$${fmt(model.cost_per_100, 2)}<small>per 100 tasks</small>`;
  }

  function latencyCell(model) {
    if (model.median_latency_ms == null) return `<span class="muted">n/a</span>`;
    return `${fmt(model.median_latency_ms / 1000, 1)}s<small>p95 ${fmt((model.p95_latency_ms || 0) / 1000, 1)}s</small>`;
  }

  function renderTable(models) {
    const body = $("#leaderboard-body");
    if (!body) return;
    if (!models.length) {
      body.innerHTML = `<tr><td colspan="8" class="table-empty">No models match these filters.</td></tr>`;
      return;
    }
    body.innerHTML = models
      .map((model) => {
        const rank = state.division === "all" ? model.rank : model.rank_division;
        const rankClass = rank === 1 ? "top" : rank === 2 ? "top2" : rank === 3 ? "top3" : "";
        const verifiedLabel = BENCH.track_filter ? "source 70/70" : "full set";
        const verifiedTitle = BENCH.track_filter ? "The source run covered the full 70-task set" : "Full fixed-set coverage";
        const badges = [
          model.verified ? `<span class="badge verified" title="${verifiedTitle}">${verifiedLabel}</span>` : "",
          model.preview ? '<span class="badge preview">preview</span>' : "",
          model.division !== "standard" ? `<span class="badge open">${escapeHtml(model.division)}</span>` : "",
          model.timeouts ? `<span class="badge timeout" title="${model.timeouts} tasks exceeded the per-task timeout">${model.timeouts} timeout${model.timeouts === 1 ? "" : "s"}</span>` : "",
          model.refusals ? `<span class="badge timeout" title="${model.refusals} tasks were refused by the model">${model.refusals} refusal${model.refusals === 1 ? "" : "s"}</span>` : "",
        ].join("");
        return `<tr>
          <td><span class="rank-badge ${rankClass}">${rank}</span></td>
          <td>
            <div class="model-cell">
              <span class="model-dot" style="color:${escapeHtml(model.color)};background:${escapeHtml(model.color)}"></span>
              <div>
                <a class="model-name" href="${escapeHtml(model.url)}">${escapeHtml(model.name)}</a>
                <div class="model-meta">${escapeHtml(model.lab)}<span>·</span><span>${escapeHtml(model.provider)}</span>${badges}</div>
              </div>
            </div>
          </td>
          <td>
            <div class="score-cell">
              <div class="score-line"><span class="score-num">${fmt(model.score)}</span><span class="ci">${fmt(model.score_ci[0])}–${fmt(model.score_ci[1])}</span></div>
              <div class="bar"><span style="width:${Math.max(1, Math.min(100, model.score))}%"></span></div>
            </div>
          </td>
          <td class="acc-cell"><strong>${fmt(model.accuracy * 100)}%</strong><span>${model.correct} / ${model.n}</span></td>
          <td><div class="track-bars" aria-label="Per-track EQB Scores">${trackBars(model)}</div></td>
          <td class="cost-cell">${costCell(model)}</td>
          <td class="latency-cell">${latencyCell(model)}</td>
          <td><a class="row-link" href="${escapeHtml(model.url)}" aria-label="Open ${escapeHtml(model.name)} details">↗</a></td>
        </tr>`;
      })
      .join("");
    const count = $("#model-count");
    if (count) count.textContent = `${models.length} model${models.length === 1 ? "" : "s"}`;
  }

  function renderChart() {
    const host = $("#cost-chart");
    if (!host) return;
    const models = filteredModels().filter(
      (model) => model.cost_per_100 != null && model.cost_per_100 > 0 && Number.isFinite(model.score)
    );
    if (!models.length) {
      host.innerHTML = `<div class="chart-empty">No cost data is available for this selection.</div>`;
      return;
    }
    const width = 760;
    const height = 360;
    const margin = { top: 22, right: 24, bottom: 48, left: 50 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    const xs = models.map((model) => Math.log10(model.cost_per_100));
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const xMin = minX === maxX ? minX - 0.5 : minX;
    const xMax = minX === maxX ? maxX + 0.5 : maxX;
    const xScale = (value) => margin.left + ((Math.log10(value) - xMin) / (xMax - xMin)) * plotW;
    const yScale = (score) => margin.top + plotH - (Math.max(0, Math.min(100, score)) / 100) * plotH;
    const yTicks = [0, 25, 50, 75, 100];
    const xTicks = [Math.pow(10, xMin), Math.pow(10, (xMin + xMax) / 2), Math.pow(10, xMax)];
    const grid = yTicks.map((tick) => `<line class="gridline" x1="${margin.left}" x2="${width - margin.right}" y1="${yScale(tick)}" y2="${yScale(tick)}"/>`).join("");
    const yLabels = yTicks.map((tick) => `<text x="${margin.left - 10}" y="${yScale(tick) + 3}" text-anchor="end">${tick}</text>`).join("");
    const xLabels = xTicks.map((tick) => {
      const x = xScale(tick);
      const label = tick < 0.01 ? tick.toExponential(1) : tick < 1 ? tick.toFixed(2) : tick.toFixed(tick >= 10 ? 0 : 1);
      return `<text x="${x}" y="${height - 22}" text-anchor="middle">$${label}</text>`;
    }).join("");
    const points = models.map((model, index) => {
      const x = xScale(model.cost_per_100);
      const y = yScale(model.score);
      const above = index % 2 === 0;
      const labelY = above ? y - 11 : y + 19;
      return `<g class="dot">
        <circle cx="${x}" cy="${y}" r="7" fill="${escapeHtml(model.color)}" stroke="#060a12" stroke-width="2"/>
        <circle cx="${x}" cy="${y}" r="12" fill="${escapeHtml(model.color)}" opacity="0.10"/>
        <title>${escapeHtml(model.name)} — ${fmt(model.score)} EQB Score — $${fmt(model.cost_per_100, 2)} / 100 tasks</title>
        <text class="dot-label" x="${x}" y="${labelY}" text-anchor="middle">${escapeHtml(model.name)}</text>
      </g>`;
    }).join("");
    host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Score versus cost per 100 tasks">
      ${grid}
      <line class="axis" x1="${margin.left}" x2="${width - margin.right}" y1="${height - margin.bottom}" y2="${height - margin.bottom}"/>
      <line class="axis" x1="${margin.left}" x2="${margin.left}" y1="${margin.top}" y2="${height - margin.bottom}"/>
      ${yLabels}${xLabels}
      <text x="${margin.left}" y="${height - 5}">cost per 100 tasks · USD · log scale</text>
      ${points}
    </svg>`;
  }

  function renderTracks() {
    const host = $("#track-grid");
    if (!host) return;
    const visible = filteredModels();
    host.innerHTML = FAMILIES.map((family, index) => {
      const best = visible
        .filter((model) => model.by_family?.[family.key])
        .sort((a, b) => (b.by_family[family.key].accuracy - a.by_family[family.key].accuracy))[0];
      const mean = family.mean_accuracy * 100;
      return `<article class="track-card">
        <div class="track-card-top">
          <div><div class="track-index">TRACK ${String(index + 1).padStart(2, "0")}</div><h3>${escapeHtml(family.label)}</h3></div>
          <span class="pill">${family.n} tasks</span>
        </div>
        <p>${escapeHtml(family.description)}</p>
        <div class="track-meter"><span style="width:${Math.max(1, mean)}%"></span></div>
        <div class="track-stat-row"><span>mean across models</span><strong>${fmt(mean)} / 100</strong></div>
        <div class="track-best">Best: <strong>${best ? escapeHtml(best.name) : "—"}</strong>${best ? ` · ${fmt(best.by_family[family.key].accuracy * 100)}%` : ""}</div>
      </article>`;
    }).join("");
  }

  function render() {
    const models = filteredModels();
    renderTable(models);
    renderChart();
    renderTracks();
  }

  function setupMotion() {
    const sections = $$(".section, .model-hero, .metric-strip, .docs-article");
    sections.forEach((node) => node.classList.add("reveal"));
    if (!("IntersectionObserver" in window)) {
      sections.forEach((node) => node.classList.add("visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.06 }
    );
    sections.forEach((node) => observer.observe(node));
  }

  function setupCopy() {
    $$(".copy-button").forEach((button) => {
      button.addEventListener("click", async () => {
        const selector = button.dataset.copy;
        const source = selector ? $(selector) : null;
        if (!source) return;
        try {
          await navigator.clipboard.writeText(source.textContent.trim());
          button.textContent = "Copied";
          setTimeout(() => (button.textContent = "Copy"), 1600);
        } catch {
          button.textContent = "Select & copy";
        }
      });
    });
  }

  function setupNav() {
    const toggle = $("#nav-toggle");
    const nav = $(".site-nav");
    if (toggle && nav) {
      toggle.addEventListener("click", () => {
        nav.classList.toggle("open");
        toggle.setAttribute("aria-expanded", nav.classList.contains("open") ? "true" : "false");
      });
      $$(".site-nav a").forEach((link) => link.addEventListener("click", () => nav.classList.remove("open")));
    }
  }

  populateFilters();
  setupMotion();
  setupCopy();
  setupNav();
  render();
})();
