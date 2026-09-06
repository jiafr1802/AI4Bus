const state = { dashboard: null, activeCandidate: null, readOnly: false };

const scoreFields = [
  ["demand_score", "需求分"], ["trend_score", "趋势分"], ["competition_score", "竞争吸引力"],
  ["logistics_score", "物流分"], ["content_fit_score", "内容适配"], ["evidence_confidence", "证据置信度"]
];
const economicsFields = [
  ["compliance_risk", "合规风险（1-5）"], ["ip_risk", "IP 风险（1-5）"], ["supplier_cost_cny", "采购成本 CNY"],
  ["freight_cny", "运费 CNY"], ["retail_price_sgd", "售价 SGD"], ["ad_cost_rate", "广告费率"]
];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function icon(name) {
  const node = element("i");
  node.setAttribute("data-lucide", name);
  return node;
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function renderDashboard(data) {
  state.dashboard = data;
  const top = data.candidates[0];
  document.querySelector("#top-candidate").textContent = top.name_zh;
  document.querySelector("#top-decision").textContent = top.decision;
  document.querySelector("#top-score").textContent = Number(top.score).toFixed(2);
  document.querySelector("#median-price").textContent = `S$${Number(data.lazada_summary.median_price_sgd).toFixed(2)}`;
  document.querySelector("#sample-size").textContent = `${data.lazada_summary.sample_size} 条 Best Match 样本`;
  document.querySelector("#median-sold").textContent = formatNumber(data.lazada_summary.median_sold_count);
  document.querySelector("#max-sold").textContent = formatNumber(data.lazada_summary.max_sold_count);
  document.querySelector("#updated-at").textContent = `页面同步 ${new Date(data.generated_at).toLocaleString("zh-CN")}`;
  renderCandidates(data.candidates);
  renderAccess(data.marketplace_access);
  refreshIcons();
}

function renderCandidates(candidates) {
  const body = document.querySelector("#candidate-rows");
  body.replaceChildren();
  candidates.forEach((candidate, index) => {
    const row = document.createElement("tr");
    const values = [
      ["rank", String(index + 1)], ["candidate-name", candidate.name_zh], ["", candidate.decision],
      ["score", Number(candidate.score).toFixed(2)], ["", `S$${Number(candidate.unit_profit_sgd).toFixed(2)}`],
      ["", `${(Number(candidate.contribution_margin) * 100).toFixed(1)}%`], ["", `${Number(candidate.evidence_confidence).toFixed(0)}%`]
    ];
    values.forEach(([className, value], valueIndex) => {
      const cell = element("td", className);
      if (valueIndex === 2) cell.append(element("span", `pill ${value}`, value));
      else cell.textContent = value;
      row.append(cell);
    });
    const action = element("td");
    if (!state.readOnly) {
      const button = element("button", "edit-button");
      button.type = "button";
      button.title = `编辑 ${candidate.name_zh}`;
      button.setAttribute("aria-label", button.title);
      button.append(icon("square-pen"));
      button.addEventListener("click", () => openEditor(candidate));
      action.append(button);
    }
    row.append(action);
    body.append(row);
  });
}

function renderAccess(sources) {
  const list = document.querySelector("#access-list");
  list.replaceChildren();
  sources.forEach(source => {
    const item = element("div", "access-item");
    item.append(element("strong", "", source.marketplace));
    item.append(element("span", `access-status ${source.status}`, source.status === "accessible" ? "可访问" : "受限"));
    item.append(element("small", "", source.notes));
    list.append(item);
  });
}

function buildFields(container, fields) {
  container.replaceChildren();
  fields.forEach(([name, labelText]) => {
    const label = element("label");
    label.append(element("span", "", labelText));
    const input = element("input");
    input.name = name;
    input.type = "number";
    input.step = name.endsWith("_risk") ? "1" : "0.01";
    if (name.endsWith("_score") || name === "evidence_confidence") { input.min = "0"; input.max = "100"; }
    if (name.endsWith("_risk")) { input.min = "1"; input.max = "5"; }
    label.append(input);
    container.append(label);
  });
}

function openEditor(candidate) {
  state.activeCandidate = candidate;
  document.querySelector("#dialog-title").textContent = candidate.name_zh;
  document.querySelector("#dialog-id").textContent = candidate.product_id;
  [...scoreFields, ...economicsFields].forEach(([name]) => {
    document.querySelector(`[name="${name}"]`).value = candidate[name];
  });
  document.querySelector('[name="evidence_note"]').value = candidate.evidence_note;
  document.querySelector("#form-error").textContent = "";
  document.querySelector("#candidate-dialog").showModal();
}

function closeEditor() {
  document.querySelector("#candidate-dialog").close();
}

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2200);
}

async function request(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "请求失败");
  return payload;
}

async function loadDashboard() {
  const staticMode = document.querySelector('meta[name="app-mode"]')?.content === "static";
  if (staticMode) {
    state.readOnly = true;
    document.querySelector("#recalculate").hidden = true;
    document.querySelector("#runtime-label").textContent = "GitHub Pages 只读版";
    document.querySelector("#runtime-detail").textContent = "数据随仓库发布更新";
    try {
      renderDashboard(await request("./dashboard-data.json"));
    } catch (error) {
      renderLoadError(error);
    }
    return;
  }
  try {
    renderDashboard(await request("/api/dashboard"));
  } catch (error) {
    renderLoadError(error);
  }
}

function renderLoadError(error) {
  const cell = element("td", "loading", error.message);
  cell.colSpan = 8;
  const row = element("tr");
  row.append(cell);
  document.querySelector("#candidate-rows").replaceChildren(row);
}

async function saveCandidate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = form.querySelector('[type="submit"]');
  const names = [...scoreFields, ...economicsFields].map(([name]) => name);
  const changes = Object.fromEntries(names.map(name => [name, form.elements[name].value]));
  changes.evidence_note = form.elements.evidence_note.value;
  submit.disabled = true;
  try {
    await request(`/api/candidates/${encodeURIComponent(state.activeCandidate.product_id)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes)
    });
    closeEditor();
    await loadDashboard();
    showToast("候选已保存，排名已重算");
  } catch (error) {
    document.querySelector("#form-error").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

buildFields(document.querySelector("#score-fields"), scoreFields);
buildFields(document.querySelector("#economics-fields"), economicsFields);
document.querySelector("#candidate-form").addEventListener("submit", saveCandidate);
document.querySelector("#close-dialog").addEventListener("click", closeEditor);
document.querySelector("#cancel-dialog").addEventListener("click", closeEditor);
document.querySelector("#recalculate").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  try { renderDashboard(await request("/api/recalculate", { method: "POST" })); showToast("评分已重新计算"); }
  catch (error) { showToast(error.message); }
  finally { button.disabled = false; }
});
document.querySelector("#candidate-dialog").addEventListener("click", event => {
  if (event.target === event.currentTarget) closeEditor();
});
loadDashboard();
refreshIcons();