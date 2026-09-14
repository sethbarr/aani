"use strict";

(() => {
  const bundle = JSON.parse(document.getElementById("plan-data").textContent);
  const plan = bundle.plan;
  const byId = id => document.getElementById(id);
  const label = value => String(value ?? "Unassigned").replaceAll("_", " ");
  const urls = [];

  function element(tag, text) {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  }

  function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], {type}));
    urls.push(url);
    const link = element("a", name);
    link.href = url;
    link.download = name;
    const item = document.createElement("li");
    item.append(link);
    byId("downloads").append(item);
  }

  function csv(rows) {
    const columns = Object.keys(rows[0] ?? {});
    const cell = value => {
      let text = String(value ?? "");
      if (typeof value === "string" && /^[=+@-]/.test(text)) text = "'" + text;
      return '"' + text.replaceAll('"', '""') + '"';
    };
    return [columns, ...rows.map(row => columns.map(key => row[key]))]
      .map(row => row.map(cell).join(",")).join("\r\n") + "\r\n";
  }

  function table(id, caption, columns, rows) {
    const target = byId(id);
    target.replaceChildren(element("caption", caption));
    const head = target.createTHead().insertRow();
    for (const [key, title] of columns) {
      const cell = element("th", title);
      cell.scope = "col";
      head.append(cell);
    }
    const body = target.createTBody();
    for (const row of rows) {
      const tr = body.insertRow();
      for (const [key] of columns) tr.append(element("td", label(row[key])));
    }
  }

  byId("status").textContent = `${plan.plan_id}: ${label(plan.status)}. ` +
    `Results: ${label(plan.results_status)}.`;
  download("experiment_plan.json", JSON.stringify(plan, null, 2), "application/json");
  download("study_matrix.csv", csv(plan.matrix), "text/csv;charset=utf-8");
  download("illustrative_plate_map.csv", csv(plan.layout), "text/csv;charset=utf-8");
  for (const [name, content] of Object.entries(bundle.files)) {
    download(name, content, "text/plain;charset=utf-8");
  }
  table("matrix", "Proposed material and fungus combinations", [
    ["material", "Material"], ["fungus", "Fungus"], ["status", "Status"],
    ["value", "Measured value"], ["unit", "Unit"],
  ], plan.matrix);

  const plates = [...new Set(plan.layout.map(row => row.plate_id))];
  for (const id of plates) {
    const option = element("option", id);
    option.value = id;
    byId("plate").append(option);
  }
  function showPlate() {
    table("layout", "Dose slots are placeholders; concentrations remain unassigned.", [
      ["well", "Well"], ["role", "Role"], ["candidate_id", "Material ID"],
      ["dose_slot", "Dose slot"], ["technical_replicate", "Technical replicate"],
      ["independent_run", "Independent run"],
    ], plan.layout.filter(row => row.plate_id === byId("plate").value));
  }
  byId("plate").addEventListener("change", showPlate);
  showPlate();
  for (const text of plan.limitations) byId("limitations").append(element("li", text));
  byId("plan").textContent = JSON.stringify(plan, null, 2);
  window.addEventListener("pagehide", event => {
    if (!event.persisted) urls.forEach(url => URL.revokeObjectURL(url));
  });
})();
