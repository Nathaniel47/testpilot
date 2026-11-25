// Static TestPilot demo. Shows results saved by the real pipeline; runs no Python.
// All content goes in through textContent, so nothing in the data is treated as HTML.
(function () {
  "use strict";
  var base = new URL(".", document.currentScript.src);
  var root = document.getElementById("app");

  var css =
    ":root{--bg:#fff;--fg:#17202a;--mute:#5b6673;--card:#f3f5f8;--line:#d5dbe3;--accent:#0072b2}" +
    "@media (prefers-color-scheme:dark){:root{--bg:#11151a;--fg:#e8ecf1;--mute:#a3adba;" +
    "--card:#1b2129;--line:#333c48;--accent:#56b4e9}}" +
    "body{margin:0;background:var(--bg);color:var(--fg);" +
    "font:16px/1.5 system-ui,sans-serif}" +
    "#app{max-width:860px;margin:0 auto;padding:20px 16px 48px}" +
    "h1{font-size:1.5rem;line-height:1.25}h2{font-size:1.1rem;margin-top:28px}" +
    "nav{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}" +
    "button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--line);" +
    "background:var(--card);color:var(--fg);cursor:pointer}" +
    "button[aria-pressed=true]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}" +
    "pre{background:var(--card);padding:12px;border-radius:8px;overflow-x:auto;" +
    "font-size:.85rem}" +
    ".stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}" +
    ".stat{background:var(--card);border-radius:8px;padding:10px 12px}" +
    ".stat b{display:block;font-size:1.7rem}.stat span,.note{color:var(--mute);" +
    "font-size:.9rem}" +
    ".gap{border-left:4px solid var(--accent);padding:8px 12px;background:var(--card)}" +
    "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);" +
    "padding:6px 8px;text-align:left}a{color:var(--accent)}";

  function el(tag, text, cls) {
    var node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  function pct(v) {
    return v === null || v === undefined ? "n/a" : Math.round(v * 100) + "%";
  }

  function stat(value, label) {
    var box = el("div", undefined, "stat");
    box.append(el("b", value), el("span", label));
    return box;
  }

  function show(out, ex) {
    out.replaceChildren();
    out.append(el("h2", "Function under test"), el("pre", ex.code));
    var stats = el("div", undefined, "stats");
    stats.append(
      stat(pct(ex.line_cov), "line coverage"),
      stat(pct(ex.mutation_score), "mutation score"),
      stat(String(ex.n_mutants), "injected bugs tried")
    );
    out.append(el("h2", "Result"), stats);
    if (ex.line_cov - ex.mutation_score > 0.05) {
      out.append(
        el(
          "p",
          "The tests run " + pct(ex.line_cov) + " of the lines but catch only " +
            pct(ex.mutation_score) + " of the injected bugs.",
          "gap"
        )
      );
    }
    if (ex.survivors && ex.survivors.length) {
      var table = el("table");
      var head = el("tr");
      head.append(el("th", "Line"), el("th", "Bug the tests missed"), el("th", "Kind"));
      table.append(head);
      ex.survivors.forEach(function (s) {
        var row = el("tr");
        row.append(el("td", String(s.line)), el("td", s.detail), el("td", s.operator));
        table.append(row);
      });
      out.append(
        el("h2", "Surviving bugs"),
        table,
        el("p", "Some of these may not change behaviour at all (equivalent mutants), so the " +
          "score is a lower bound.", "note")
      );
    }
    out.append(el("h2", "Generated tests"), el("pre", ex.test_code));
  }

  function render(data) {
    root.replaceChildren();
    root.append(
      el("h1", "TestPilot: do the tests catch bugs, or just run the code?"),
      el("p", "TestPilot writes tests for a Python function, then injects small bugs " +
        "(mutants) and counts how many the tests catch. Coverage says a line ran; mutation " +
        "score says a wrong line would be noticed. Pick an example.")
    );
    var nav = el("nav");
    var out = el("div");
    data.examples.forEach(function (ex, i) {
      var button = el("button", ex.name);
      button.type = "button";
      button.setAttribute("aria-pressed", String(i === 0));
      button.addEventListener("click", function () {
        nav.querySelectorAll("button").forEach(function (b) {
          b.setAttribute("aria-pressed", String(b === button));
        });
        show(out, ex);
      });
      nav.append(button);
    });
    var note = el("p", "These are saved results from real runs of the pipeline with the " +
      "offline template generator, a weak baseline. This page runs no code. In the study, an " +
      "LLM with repair reached a mean mutation score of 0.90 on 61 dev-split functions, " +
      "against 0.29 for this baseline. To try your own function, run the app locally: ",
      "note");
    var link = el("a", "source and instructions");
    link.href = "https://github.com/Nathaniel47/testpilot";
    link.target = "_blank";
    link.rel = "noopener";
    note.append(link);
    root.append(nav, out, note);
    show(out, data.examples[0]);
  }

  var style = el("style", css);
  document.head.append(style);
  fetch(new URL("results.json", base))
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(render)
    .catch(function (err) {
      root.textContent = "Could not load the saved results (" + err.message + ").";
    });
})();
