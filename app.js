/* Marketing Budget Variance Desk - browser logic.
   All text from uploaded files is inserted with textContent (never innerHTML),
   so a malicious line-item name cannot run code in the page. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

  var state = { analysis: null, rankBy: "amount", source: null, busy: false, notice: "" };

  // ---------- helpers
  function money(n, signed) {
    var sign = n < 0 ? "-" : (signed && n > 0 ? "+" : "");
    return sign + "₹" + inr.format(Math.abs(Math.round(n)));
  }
  function pct(n, signed) {
    var sign = signed && n > 0 ? "+" : "";
    return sign + n.toFixed(1) + "%";
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function dir(line) { return line.status === "Over budget" ? "over" : (line.status === "Under budget" ? "under" : "on"); }
  function chip(line) { return el("span", "chip " + dir(line), line.status); }

  function setBusy(isBusy, message) {
    state.busy = isBusy;
    ["btn-analyse", "btn-sample", "btn-ai"].forEach(function (id) {
      if ($(id)) $(id).disabled = isBusy || (id === "btn-analyse" && !$("file-input").files.length);
    });
    $("status").textContent = message || "";
  }
  function showError(message, rejected) {
    var box = $("errors");
    clear(box);
    box.appendChild(el("strong", null, "Could not analyse: "));
    box.appendChild(document.createTextNode(message));
    box.hidden = false;
    renderSkipped(rejected, true);
  }
  function renderSkipped(rejected, onError) {
    var box = $("skipped");
    clear(box);
    if (!rejected || !rejected.length) { box.hidden = true; return; }
    var head = onError ? "Rows with problems (" : "Skipped rows (";
    box.appendChild(el("strong", null, head + rejected.length + ")"));
    if (!onError) box.appendChild(document.createTextNode(" - these rows were left out; the rest were analysed."));
    var ul = el("ul");
    rejected.slice(0, 25).forEach(function (r) {
      ul.appendChild(el("li", null, "Row " + r.row + " - " + r.line_item + ": " + r.reasons.join("; ")));
    });
    if (rejected.length > 25) ul.appendChild(el("li", null, "...and " + (rejected.length - 25) + " more."));
    box.appendChild(ul);
    box.hidden = false;
  }

  // ---------- step 1: analyse
  function analyse(source) {
    if (state.busy) return;                       // blocks double submit
    var tol = parseFloat($("tolerance").value);
    if (isNaN(tol) || tol < 0 || tol > 100) {
      showError("Tolerance must be a number between 0 and 100.");
      return;
    }
    var form = new FormData();
    form.append("tolerance", String(tol));
    if (source.type === "sample") form.append("use_sample", "true");
    else form.append("file", source.file);

    $("errors").hidden = true;
    setBusy(true, "Analysing...");
    fetch("/api/analyze", { method: "POST", body: form })
      .then(function (r) { return r.json().catch(function () { return { ok: false, error: "Unexpected server response." }; }); })
      .then(function (data) {
        if (!data.ok) {
          $("results").hidden = true;
          state.analysis = null;
          showError(data.error, data.rejected);
          return;
        }
        state.analysis = data;
        state.source = source;
        $("errors").hidden = true;
        renderSkipped(data.rejected, false);
        extraWarnings(data.warnings);
        $("results").hidden = false;
        clear($("ai-output"));
        $("ai-status").textContent = state.notice || "";
        state.notice = "";
        renderAll();
      })
      .catch(function () { showError("Could not reach the server. Check your connection and try again."); })
      .then(function () { setBusy(false, ""); });
  }
  function extraWarnings(warnings) {
    if (!warnings || !warnings.length) return;
    var box = $("skipped");
    if (box.hidden) { clear(box); box.hidden = false; }
    var ul = el("ul");
    warnings.forEach(function (w) { ul.appendChild(el("li", null, w)); });
    box.appendChild(ul);
  }

  // ---------- step 2: render review
  function renderAll() { renderKpis(); renderOutliers(); renderCategories(); renderChart(); renderTable(); }

  function renderKpis() {
    var s = state.analysis.summary, box = $("kpis");
    clear(box);
    function kpi(label, value, sub, cls) {
      var d = el("div", "kpi " + (cls || ""));
      d.appendChild(el("div", "k", label));
      d.appendChild(el("div", "v", value));
      d.appendChild(el("div", "s", sub));
      box.appendChild(d);
    }
    kpi("Budget", money(s.total_budget), s.n_lines + " line items · " + s.period);
    kpi("Actual", money(s.total_actual), "Total spend");
    kpi("Variance", money(s.total_variance, true), pct(s.total_pct, true) + (s.total_variance > 0 ? " over budget" : s.total_variance < 0 ? " under budget" : " on budget"), s.total_variance > 0 ? "over" : (s.total_variance < 0 ? "under" : ""));
    kpi("Outside tolerance", s.n_outside + " of " + s.n_lines, "More than ±" + s.tolerance_pct + "% of budget");
  }

  function topIds() {
    return state.rankBy === "pct" ? state.analysis.top_by_pct : state.analysis.top_by_amount;
  }
  function renderOutliers() {
    var list = $("outliers"), a = state.analysis;
    clear(list);
    var ids = topIds();
    if (!ids.length) { list.appendChild(el("li", null, "No line item differs from its budget.")); return; }
    ids.forEach(function (id, i) {
      var l = a.lines[id], li = el("li", dir(l));
      var top = el("div", "o-top");
      var left = el("div");
      left.appendChild(el("div", "o-name", (i + 1) + ". " + l.line_item));
      left.appendChild(el("div", "o-cat", l.category));
      top.appendChild(left);
      top.appendChild(chip(l));
      li.appendChild(top);
      li.appendChild(el("div", "o-nums", "Budget " + money(l.budget) + " → Actual " + money(l.actual) +
        " · Variance " + money(l.variance, true) + " (" + pct(l.pct, true) + ")"));
      list.appendChild(li);
    });
  }

  function renderCategories() {
    var t = $("cat-table"); clear(t);
    var head = el("tr");
    ["Category", "Budget", "Actual", "Variance", "%"].forEach(function (h, i) {
      var th = el("th", i ? "num" : "", h); head.appendChild(th);
    });
    t.appendChild(head);
    state.analysis.categories.forEach(function (c) {
      var tr = el("tr");
      tr.appendChild(el("td", null, c.category));
      tr.appendChild(el("td", "num", money(c.budget)));
      tr.appendChild(el("td", "num", money(c.actual)));
      tr.appendChild(el("td", "num", money(c.variance, true)));
      tr.appendChild(el("td", "num", pct(c.pct, true)));
      t.appendChild(tr);
    });
  }

  function renderChart() {
    var box = $("chart"); clear(box);
    var lines = state.analysis.lines.filter(function (l) { return l.status !== "On budget"; })
      .sort(function (x, y) { return Math.abs(y.variance) - Math.abs(x.variance); }).slice(0, 15);
    if (!lines.length) { box.textContent = "No variances to chart."; return; }
    var max = Math.abs(lines[0].variance), ids = topIds();
    lines.forEach(function (l) {
      var row = el("div", "c-row" + (ids.indexOf(l.idx) >= 0 ? " top" : ""));
      row.appendChild(el("div", "c-name", l.line_item));
      var track = el("div", "c-track"), bar = el("div", "c-bar " + dir(l));
      bar.style.width = (Math.abs(l.variance) / max * 50) + "%";
      track.appendChild(bar);
      row.appendChild(track);
      row.appendChild(el("div", "c-val", money(l.variance, true)));
      box.appendChild(row);
    });
    var cap = el("div", "hint", "Red = over budget (right of the centre line), teal = under budget (left). Showing up to the 15 largest gaps; bold = current top 3.");
    box.appendChild(cap);
  }

  function visibleLines() {
    var lines = state.analysis.lines.slice(), f = $("filter-by").value, s = $("sort-by").value;
    if (f === "over") lines = lines.filter(function (l) { return l.status === "Over budget"; });
    if (f === "under") lines = lines.filter(function (l) { return l.status === "Under budget"; });
    if (f === "outside") lines = lines.filter(function (l) { return l.outside_tolerance; });
    if (s === "amount") lines.sort(function (x, y) { return Math.abs(y.variance) - Math.abs(x.variance); });
    if (s === "pct") lines.sort(function (x, y) { return Math.abs(y.pct) - Math.abs(x.pct); });
    return lines;
  }
  function renderTable() {
    var t = $("line-table"); clear(t);
    var head = el("tr");
    ["Line item", "Category", "Budget", "Actual", "Variance", "%", "Status", "Tolerance"].forEach(function (h, i) {
      head.appendChild(el("th", i >= 2 && i <= 5 ? "num" : "", h));
    });
    t.appendChild(head);
    var ids = topIds();
    visibleLines().forEach(function (l) {
      var tr = el("tr", ids.indexOf(l.idx) >= 0 ? "top" : "");
      tr.appendChild(el("td", null, l.line_item));
      tr.appendChild(el("td", null, l.category));
      tr.appendChild(el("td", "num", money(l.budget)));
      tr.appendChild(el("td", "num", money(l.actual)));
      tr.appendChild(el("td", "num", money(l.variance, true)));
      tr.appendChild(el("td", "num", pct(l.pct, true)));
      var st = el("td"); st.appendChild(chip(l)); tr.appendChild(st);
      tr.appendChild(el("td", null, l.outside_tolerance ? "Outside" : "Within"));
      t.appendChild(tr);
    });
  }

  function exportCsv() {
    function safe(v) {                       // stops spreadsheet formula injection
      var s = String(v);
      if (/^[=+\-@\t\r]/.test(s) && isNaN(Number(s))) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    }
    var rows = [["Line_Item", "Category", "Budget_INR", "Actual_INR", "Variance_INR", "Variance_pct", "Status", "Tolerance"]];
    visibleLines().forEach(function (l) {
      rows.push([l.line_item, l.category, l.budget, l.actual, l.variance, l.pct, l.status, l.outside_tolerance ? "Outside" : "Within"]);
    });
    var csv = "\ufeff" + rows.map(function (r) { return r.map(safe).join(","); }).join("\n");
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "variance_review.csv";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  }

  // ---------- step 3: commentary
  function listBlock(parent, title, items) {
    if (!items || !items.length) return;
    parent.appendChild(el("h4", null, title));
    var ul = el("ul");
    items.forEach(function (x) { ul.appendChild(el("li", null, x)); });
    parent.appendChild(ul);
  }
  function renderCommentary(d) {
    var out = $("ai-output"); clear(out);
    var card = el("div", "ai-card"), c = d.commentary;
    card.appendChild(el("span", "src " + (d.source === "gemini" ? "ai" : "rules"),
      d.source === "gemini" ? "Written by Gemini (" + d.model + ")" + (d.cached ? " · cached" : "")
                            : "Standard rules-based summary (AI not used)"));
    if (d.notice) card.appendChild(el("div", "alert warn", d.notice));
    (d.warnings || []).forEach(function (w) { card.appendChild(el("div", "alert warn", w)); });
    card.appendChild(el("h3", null, c.headline));
    card.appendChild(el("p", null, c.overall_summary));
    if (c.outlier_notes.length) {
      card.appendChild(el("h4", null, "Outlier line items"));
      c.outlier_notes.forEach(function (n) {
        var box = el("div", "note-box");
        box.appendChild(el("strong", null, n.line_item));
        box.appendChild(el("p", null, n.what_happened));
        listBlock(box, "Questions to check", n.questions_to_check);
        card.appendChild(box);
      });
    }
    listBlock(card, "Category observations", c.category_observations);
    listBlock(card, "Suggested review actions", c.recommended_actions);
    listBlock(card, "Data caveats", c.data_caveats);
    card.appendChild(el("p", "disclaimer", d.disclaimer));
    out.appendChild(card);
  }
  function generate() {
    if (state.busy || !state.analysis) return;
    var refresh = false;                    // set when the server forgot this analysis
    setBusy(true, "");
    $("ai-status").textContent = "Writing commentary... this can take up to 30 seconds.";
    fetch("/api/commentary", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: state.analysis.analysis_id, rank_by: state.rankBy,
                             simulate_outage: $("sim-outage").checked })
    })
      .then(function (r) { return r.json().catch(function () { return { ok: false, error: "Unexpected server response." }; }); })
      .then(function (d) {
        if (!d.ok) {
          $("ai-status").textContent = d.error || "Could not generate commentary.";
          if (d.error && d.error.indexOf("expired") >= 0 && state.source) refresh = true;
          return;
        }
        $("ai-status").textContent = "";
        renderCommentary(d);
      })
      .catch(function () { $("ai-status").textContent = "Could not reach the server. Please try again."; })
      .then(function () {
        setBusy(false, "");
        if (refresh) {                       // recalculate automatically, then ask the user to retry
          state.notice = "Your analysis had expired (for example after a server restart), so it was recalculated. Please click Generate commentary again.";
          analyse(state.source);
        }
      });
  }

  // ---------- events
  function setRank(mode) {
    state.rankBy = mode;
    $("rank-amount").classList.toggle("active", mode === "amount");
    $("rank-pct").classList.toggle("active", mode === "pct");
    $("rank-amount").setAttribute("aria-pressed", String(mode === "amount"));
    $("rank-pct").setAttribute("aria-pressed", String(mode === "pct"));
    if (state.analysis) { renderOutliers(); renderChart(); renderTable(); }
  }
  $("file-input").addEventListener("change", function () {
    $("btn-analyse").disabled = !$("file-input").files.length || state.busy;
  });
  $("btn-analyse").addEventListener("click", function () {
    var f = $("file-input").files[0];
    if (f) analyse({ type: "file", file: f });
  });
  $("btn-sample").addEventListener("click", function () { $("file-input").value = ""; $("btn-analyse").disabled = true; analyse({ type: "sample" }); });
  $("tolerance").addEventListener("change", function () { if (state.source) analyse(state.source); });
  $("rank-amount").addEventListener("click", function () { setRank("amount"); });
  $("rank-pct").addEventListener("click", function () { setRank("pct"); });
  $("sort-by").addEventListener("change", function () { if (state.analysis) renderTable(); });
  $("filter-by").addEventListener("change", function () { if (state.analysis) renderTable(); });
  $("btn-export").addEventListener("click", function () { if (state.analysis) exportCsv(); });
  $("btn-ai").addEventListener("click", generate);
})();
