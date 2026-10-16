const state = { dashboard: null, activeCandidate: null, readOnly: false, researchId: null, evidencePage: 1, endpoint: null, quote: null, job: null, monid: null };
const kindLabels = { listing: "新加坡商品", review: "新加坡评论", social: "社媒内容", supplier: "供应商报价" };
const recordLabels = { listing: "商品", review: "评论", social: "社媒内容", supplier: "供应商报价" };
const decisionLabels = { TEST: "可评估试单", WATCH: "待验证", DROP: "暂缓", BLOCK: "风险阻断" };
const platformLabels = { amazon: "Amazon", lazada: "Lazada", shopee: "Shopee", youtube: "YouTube", reddit: "Reddit", tiktok: "TikTok" };

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
  document.querySelector("#top-decision").textContent = decisionLabels[top.decision] || top.decision;
  document.querySelector("#top-decision").className = `decision ${top.decision}`;
  document.querySelector("#overview-summary").textContent = `${data.candidates.length} 个候选 · ${(data.evidence || []).length} 条已收录样本 · 目标市场 新加坡`;
  document.querySelector("#top-score").textContent = Number(top.score).toFixed(2);
  document.querySelector("#median-price").textContent = data.lazada_summary.median_price_sgd == null ? "--" : `S$${Number(data.lazada_summary.median_price_sgd).toFixed(2)}`;
  document.querySelector("#sample-size").textContent = `${data.lazada_summary.sample_size} 条 · ${data.lazada_summary.sampled_at || "无快照"}${data.lazada_summary.stale ? " · 已过期" : ""}`;
  document.querySelector("#median-sold").textContent = formatNumber(data.lazada_summary.median_sold_count);
  document.querySelector("#max-sold").textContent = formatNumber(data.lazada_summary.max_sold_count);
  document.querySelector("#updated-at").textContent = `页面同步 ${new Date(data.generated_at).toLocaleString("zh-CN")}`;
  renderCandidates(data.candidates);
  renderAccess(data.marketplace_access);
  const selector = document.querySelector("#research-candidate");
  selector.replaceChildren(...data.candidates.map(candidate => {
    const option = element("option", "", candidate.name_zh);
    option.value = candidate.product_id;
    return option;
  }));
  state.researchId = data.candidates.some(candidate => candidate.product_id === state.researchId) ? state.researchId : top.product_id;
  selector.value = state.researchId;
  renderResearch();
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
      ["", `${(Number(candidate.contribution_margin) * 100).toFixed(1)}%`], ["", candidate.research?.total ? `${candidate.research.total} 条 / ${Object.values(candidate.research.counts).reduce((total, count) => total + count, 0)} 条` : "尚未采集"]
    ];
    values.forEach(([className, value], valueIndex) => {
      const cell = element("td", className);
      if (valueIndex === 2) { cell.append(element("span", `pill ${value}`, decisionLabels[value] || value)); cell.title = candidate.reason; }
      else cell.textContent = value;
      row.append(cell);
    });
    const action = element("td");
    const actions = element("div", "row-actions");
    const evidenceButton = actionButton("scan-search", `查看 ${candidate.name_zh} 的证据`, () => {
      state.researchId = candidate.product_id;
      state.evidencePage = 1;
      document.querySelector("#research-candidate").value = candidate.product_id;
      invalidateQuote();
      renderResearch();
      document.querySelector("#evidence").scrollIntoView({ behavior: "smooth" });
    });
    actions.append(evidenceButton);
    if (!state.readOnly) {
      const button = element("button", "edit-button");
      button.type = "button";
      button.title = `编辑 ${candidate.name_zh}`;
      button.setAttribute("aria-label", button.title);
      button.append(icon("square-pen"));
      button.addEventListener("click", () => openEditor(candidate));
      actions.append(button);
    }
    action.append(actions);
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
    item.append(element("span", `access-status ${source.status}`, source.status === "accessible" ? "采样时可访问" : "采样时受限"));
    const note = element("small", "", `${source.sampled_at?.slice(0, 10) || ""} · ${source.notes}`);
    note.title = note.textContent;
    item.append(note);
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
    document.querySelectorAll(".local-only").forEach(node => { node.hidden = true; });
    document.querySelector('a[href="#collection"]').hidden = true;
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

function actionButton(symbol, title, handler) {
  const button = element("button", "icon-button");
  button.type = "button";
  button.title = title;
  button.setAttribute("aria-label", title);
  button.append(icon(symbol));
  button.addEventListener("click", handler);
  return button;
}

function listingData(record) {
  if (record.kind !== "listing") return null;
  try {
    const data = JSON.parse(record.text);
    return data && typeof data === "object" && !Array.isArray(data) ? data : null;
  } catch { return null; }
}

function observedNumber(value) {
  if (value == null || String(value).trim() === "") return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

function renderEvidenceBody(item, record) {
  const data = listingData(record);
  if (!data) {
    item.append(element("p", "evidence-text", record.text));
    return;
  }
  const price = observedNumber(data.price_sgd);
  const rating = observedNumber(data.rating);
  const reviews = observedNumber(data.ratings_count ?? data.reviews_count);
  const sold = observedNumber(data.sold_count);
  const facts = element("dl", "listing-facts");
  [
    ["采样价格", price === null ? "未记录" : `S$${price.toFixed(2)}`],
    ["评分", rating === null ? "未记录" : `${rating.toFixed(1)} / 5`],
    ["累计评价数", reviews === null ? "未记录" : formatNumber(reviews)],
    ["累计已售", sold === null ? "未记录" : formatNumber(sold)],
  ].forEach(([label, value]) => {
    const fact = element("div");
    fact.append(element("dt", "", label), element("dd", value === "未记录" ? "missing-value" : "", value));
    facts.append(fact);
  });
  item.append(facts);
  if (data.ship_from) item.append(element("p", "listing-note", `发货地：${data.ship_from}`));
  if (data.notes) item.append(element("p", "listing-note", data.notes));
  const raw = element("details", "raw-evidence");
  raw.append(element("summary", "", "原始采样记录"), element("pre", "", JSON.stringify(data, null, 2)));
  item.append(raw);
}

function isRecentRecord(record) {
  const observed = new Date(`${record.published_at || record.observed_at}T00:00:00`);
  const reference = new Date(state.dashboard.generated_at);
  reference.setHours(0, 0, 0, 0);
  const age = Math.round((reference - observed) / 86400000);
  return age >= 0 && age <= 30;
}

function renderPlatformComparison(records) {
  const container = document.querySelector("#platform-comparison");
  container.replaceChildren();
  const platforms = [...new Set(records.filter(record => record.kind === "listing" && !record.excluded).map(record => record.platform))];
  container.hidden = !platforms.length;
  if (!platforms.length) return;
  container.append(element("h3", "", "商品采样价格"), element("p", "comparison-note", "不同规格的混合样本，不代表同款比价；累计评价与已售数不代表近期成交。"));
  platforms.forEach(platform => {
    const listings = records.filter(record => record.platform === platform && record.kind === "listing" && !record.excluded);
    const prices = listings.map(record => observedNumber(listingData(record)?.price_sgd)).filter(price => price !== null).sort((first, second) => first - second);
    const middle = Math.floor(prices.length / 2);
    const median = prices.length ? (prices[Math.floor((prices.length - 1) / 2)] + prices[middle]) / 2 : null;
    const row = element("div", `platform-row platform-${platform in platformLabels ? platform : "other"}`);
    const label = element("div", "platform-name");
    label.append(element("strong", "", platformLabels[platform] || platform), element("small", "", `${listings.length} 条商品 · ${prices.length} 条有价格`));
    row.append(label);
    const central = element("div");
    central.append(element("span", "", "中位采样价"), element("strong", "", median === null ? "未记录" : `S$${median.toFixed(2)}`));
    const range = element("div");
    range.append(element("span", "", "样本价格范围"), element("strong", "", prices.length ? `S$${prices[0].toFixed(2)} ~ S$${prices[prices.length - 1].toFixed(2)}` : "未记录"));
    row.append(central, range);
    container.append(row);
  });
}

function renderResearch() {
  const candidate = state.dashboard.candidates.find(item => item.product_id === state.researchId);
  if (!candidate) return;
  const summary = candidate.research;
  const allRecords = (state.dashboard.evidence || []).filter(record => record.product_id === state.researchId);
  const eligibleCount = Object.values(summary.counts).reduce((total, count) => total + count, 0);
  const platformNames = [...new Set(allRecords.map(record => record.platform))];
  const dates = allRecords.map(record => record.observed_at).sort();
  document.querySelector("#inventory-title").textContent = allRecords.length ? `已收录 ${allRecords.length} 条样本，近期可用 ${eligibleCount} 条` : "这个候选还没有原始采样记录";
  document.querySelector("#inventory-detail").textContent = allRecords.length
    ? `${platformNames.map(platform => platformLabels[platform] || platform).join("、")} · 最近采样 ${dates[dates.length - 1]}。${summary.stale ? `${summary.stale} 条已超过 30 天，保留作历史参考。` : ""}${summary.excluded ? `${summary.excluded} 条已排除。` : ""}`
    : "现有参考分来自人工假设，商品、评论与供应报价尚待采集。";
  if (state.monid && !state.monid.configured) document.querySelector("#inventory-detail").append(" Monid 未连接，尚未启动新的 API 采集。");
  document.querySelector("#inventory-status").textContent = summary.ready ? "证据齐备" : allRecords.length ? "待补近期证据" : "尚未采集";
  const verdict = document.querySelector("#research-verdict");
  verdict.replaceChildren(element("span", `pill ${candidate.decision}`, decisionLabels[candidate.decision] || candidate.decision), element("span", "", candidate.reason), element("small", "", `参考分 ${Number(candidate.score).toFixed(2)} · 人工置信度 ${candidate.evidence_confidence}%`));
  const counts = document.querySelector("#research-counts");
  counts.replaceChildren();
  Object.entries(recordLabels).forEach(([kind, label]) => {
    const total = allRecords.filter(record => record.kind === kind).length;
    const item = element("div", "research-count");
    const caption = element("span", "count-caption");
    caption.append(icon({ listing: "package", review: "messages-square", social: "video", supplier: "file-check-2" }[kind]), element("span", "", label));
    item.append(caption, element("strong", total ? "" : "not-collected", total ? `${total} 条` : "未采集"));
    item.append(element("small", "", `${kindLabels[kind]}近期可用 ${summary.counts[kind] || 0} / ${summary.requirements[kind]}`));
    counts.append(item);
  });
  renderPlatformComparison(allRecords);
  const gaps = document.querySelector("#research-gaps");
  gaps.replaceChildren(...(summary.gaps.length ? summary.gaps : ["证据覆盖齐备；复核报价、样品和合规后再决定测试"]).map(text => element("li", "", text)));
  const themes = document.querySelector("#research-themes");
  themes.replaceChildren(...(summary.themes.length ? summary.themes.map(theme => element("span", "theme", `${theme.tag} · ${theme.count}`)) : [element("span", "muted", allRecords.some(record => record.kind === "review" || record.kind === "social") ? "暂无近期已标注的评论或内容信号" : "尚未采集评论或内容原文，无法判断用户痛点。商品页的评价总数不是评论样本。") ]));
  document.querySelector("#research-freshness").textContent = `共 ${summary.total} 条 · ${summary.stale} 条过期 · ${summary.excluded || 0} 条已排除 · ${summary.platforms.length} 个近期需求平台 · 有效期 ${summary.freshness_days} 天`;
  const kind = document.querySelector("#evidence-kind").value;
  const search = document.querySelector("#evidence-search").value.toLowerCase();
  const platformSelect = document.querySelector("#evidence-platform");
  const previousPlatform = platformSelect.value;
  platformSelect.replaceChildren(element("option", "", "全部平台"));
  platformSelect.firstChild.value = "";
  platformNames.forEach(platform => { const option = element("option", "", platformLabels[platform] || platform); option.value = platform; platformSelect.append(option); });
  platformSelect.value = platformNames.includes(previousPlatform) ? previousPlatform : "";
  const filterStatus = document.querySelector("#evidence-status").value;
  const records = allRecords.filter(record => (!kind || record.kind === kind)
    && (!platformSelect.value || record.platform === platformSelect.value)
    && `${record.title} ${record.text} ${record.tags} ${record.platform}`.toLowerCase().includes(search)
    && (filterStatus === "all" || (filterStatus === "excluded" ? record.excluded : !record.excluded && (filterStatus === "recent" ? isRecentRecord(record) : !isRecentRecord(record)))));
  const sort = document.querySelector("#evidence-sort").value;
  records.sort((first, second) => {
    if (sort !== "date") {
      const firstPrice = observedNumber(listingData(first)?.price_sgd);
      const secondPrice = observedNumber(listingData(second)?.price_sgd);
      if (firstPrice === null && secondPrice !== null) return 1;
      if (secondPrice === null && firstPrice !== null) return -1;
      if (firstPrice !== null && secondPrice !== null && firstPrice !== secondPrice) return (firstPrice - secondPrice) * (sort === "price-asc" ? 1 : -1);
    }
    return second.observed_at.localeCompare(first.observed_at);
  });
  document.querySelector("#evidence-match-count").textContent = `样本明细 · ${records.length} / ${allRecords.length} 条`;
  const pageSize = 6;
  const totalPages = Math.max(1, Math.ceil(records.length / pageSize));
  state.evidencePage = Math.max(1, Math.min(state.evidencePage, totalPages));
  document.querySelector("#evidence-pagination").hidden = totalPages <= 1;
  document.querySelector("#evidence-page-status").textContent = `第 ${state.evidencePage} / ${totalPages} 页 · 每页 ${pageSize} 条`;
  document.querySelector("#evidence-previous").disabled = state.evidencePage === 1;
  document.querySelector("#evidence-next").disabled = state.evidencePage === totalPages;
  const container = document.querySelector("#evidence-records");
  container.replaceChildren();
  if (!records.length) {
    const empty = element("div", "empty-state evidence-empty");
    empty.append(icon("inbox"), element("strong", "", allRecords.length ? "当前筛选下没有样本" : "这个候选尚未采样"));
    empty.append(element("p", "", allRecords.length ? `当前条件下没有匹配记录，已有 ${allRecords.length} 条样本仍保留。` : "当前只有人工评分假设，还没有可核对的原始商品、评论或报价。"));
    if (allRecords.length) {
      const reset = element("button", "button secondary", "清除筛选"); reset.type = "button";
      reset.addEventListener("click", () => { ["#evidence-kind", "#evidence-search", "#evidence-platform"].forEach(selector => { document.querySelector(selector).value = ""; }); document.querySelector("#evidence-status").value = "all"; renderResearch(); });
      empty.append(reset);
    }
    container.append(empty);
  }
  records.slice((state.evidencePage - 1) * pageSize, state.evidencePage * pageSize).forEach(record => {
    const item = element("article", "evidence-record");
    if (record.excluded) item.classList.add("excluded");
    const metadata = element("div", "record-meta");
    metadata.append(element("strong", `platform-label ${record.platform in platformLabels ? record.platform : ""}`, platformLabels[record.platform] || record.platform));
    metadata.append(element("span", "market-label", record.market === "UNKNOWN" ? "市场待核实" : record.market === "SG" ? "新加坡" : record.market));
    metadata.append(element("span", "record-date", `${record.observed_at} 采样${record.published_at ? ` · ${record.published_at} 发布` : ""}`));
    metadata.append(element("span", `record-age ${isRecentRecord(record) ? "recent" : "historical"}`, isRecentRecord(record) ? "近 30 天" : "历史样本"));
    const source = element("a", "source-link", "查看来源");
    source.append(icon("arrow-up-right"));
    source.href = record.url; source.target = "_blank"; source.rel = "noopener noreferrer";
    metadata.append(source);
    if (!state.readOnly) metadata.append(actionButton(record.excluded ? "undo-2" : "circle-minus", record.excluded ? "恢复证据" : "排除证据", async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await request("/api/evidence/exclude", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: record.id, excluded: !record.excluded }) });
        await loadDashboard(); showToast(record.excluded ? "证据已恢复" : "证据已排除，原文保留");
      } catch (error) { showToast(error.message); button.disabled = false; }
    }));
    if (record.excluded) metadata.append(element("span", "", "已排除"));
    item.append(metadata);
    if (record.title) item.append(element("h3", "", record.title));
    renderEvidenceBody(item, record);
    if (record.tags) item.append(element("small", "muted", record.tags));
    container.append(item);
  });
  refreshIcons();
}

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = element("a"); link.href = url; link.download = name; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function openImport(records) {
  document.querySelector("#import-error").textContent = "";
  if (records) {
    document.querySelector("#import-format").value = "json";
    document.querySelector("#import-content").value = JSON.stringify(records, null, 2);
  }
  document.querySelector("#import-dialog").showModal();
}

async function withButton(button, errorSelector, action) {
  button.disabled = true;
  document.querySelector(errorSelector).textContent = "";
  try { await action(); }
  catch (error) { document.querySelector(errorSelector).textContent = error.message; }
  finally { button.disabled = false; refreshIcons(); }
}

function monidRequest(action, payload) {
  return request(`/api/monid/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}

function invalidateQuote() {
  state.quote = null;
  document.querySelector("#run-quote").hidden = true;
  document.querySelector("#confirm-charge").checked = false;
  document.querySelector("#execute-run").disabled = true;
}

async function loadMonid() {
  if (state.readOnly) return;
  const config = await request("/api/monid/status");
  state.monid = config;
  document.querySelector("#monid-connection").hidden = config.configured;
  if (state.dashboard) renderResearch();
  document.querySelector("#monid-status").textContent = !config.configured ? "未配置密钥" : config.runs_enabled && config.workspace_cap_confirmed ? "已配置 · 运行需逐次批准" : "已配置 · 付费运行关闭";
  const jobs = document.querySelector("#collection-jobs"); jobs.replaceChildren();
  if (!config.jobs.length) jobs.append(element("p", "empty-state", "暂无采集任务"));
  config.jobs.forEach(job => {
    const row = element("div", "job-row");
    const text = element("div");
    text.append(element("strong", "", `${job.provider} ${job.endpoint}`));
    const candidate = state.dashboard?.candidates.find(item => item.product_id === job.product_id);
    text.append(element("small", "muted", `${candidate?.name_zh || job.product_id} · ${job.status} · 预估 $${job.estimate_usd}`));
    row.append(text);
    row.append(actionButton("folder-open", "查看任务与原始结果", event => withButton(event.currentTarget, "#collection-error", async () => showJob(await monidRequest("load", { id: job.id })))));
    if (job.run_id) row.append(actionButton("refresh-cw", "刷新远程任务状态", event => withButton(event.currentTarget, "#collection-error", async () => { showJob(await monidRequest("refresh", { id: job.id })); await loadMonid(); })));
    jobs.append(row);
  });
  refreshIcons();
}

function showJob(job) {
  state.job = job;
  document.querySelector("#job-detail").hidden = false;
  document.querySelector("#job-title").textContent = `${job.provider} · ${job.status} · ${job.id.slice(0, 8)}`;
  const result = job.result || {};
  const cost = result.cost || result.billing?.actualCost;
  document.querySelector("#job-billing").textContent = `预估 $${job.estimate_usd} · 实际费用 ${cost ? JSON.stringify(cost) : "待结算"} · 供应商 HTTP ${result.providerResponse?.httpStatus ?? "未返回"}`;
  document.querySelector("#job-output").textContent = JSON.stringify(result, null, 2);
  document.querySelector("#mapping-form").hidden = result.status !== "COMPLETED" || (result.providerResponse?.httpStatus ?? 200) >= 400;
  if (job.status === "PREPARED") {
    state.quote = job;
    document.querySelector("#endpoint-editor").hidden = false;
    document.querySelector("#endpoint-title").textContent = `${job.provider} ${job.endpoint}`;
    document.querySelector("#endpoint-schema").textContent = JSON.stringify(job.inspection, null, 2);
    state.endpoint = { provider: job.provider, endpoint: job.endpoint };
    document.querySelector("#run-input").value = JSON.stringify(job.input, null, 2);
    document.querySelector("#research-candidate").value = job.product_id;
    state.researchId = job.product_id; renderResearch();
    renderQuote(job);
  }
}

function renderQuote(job) {
  state.quote = job;
  document.querySelector("#run-quote").hidden = false;
  const candidate = state.dashboard.candidates.find(item => item.product_id === job.product_id);
  document.querySelector("#quote-summary").textContent = `${candidate.name_zh} · 预估 $${job.estimate_usd} USD · 本地预检阈值 $${state.monid.max_estimate_usd} · 15 分钟有效`;
  document.querySelector("#confirm-charge").checked = false;
  document.querySelector("#execute-run").disabled = true;
}

document.querySelector("#research-candidate").addEventListener("change", event => { state.researchId = event.target.value; state.evidencePage = 1; invalidateQuote(); renderResearch(); });
for (const selector of ["#evidence-kind", "#evidence-platform", "#evidence-status", "#evidence-sort"]) {
  document.querySelector(selector).addEventListener("change", () => { state.evidencePage = 1; renderResearch(); });
}
document.querySelector("#evidence-search").addEventListener("input", () => { state.evidencePage = 1; renderResearch(); });
for (const [selector, direction] of [["#evidence-previous", -1], ["#evidence-next", 1]]) {
  document.querySelector(selector).addEventListener("click", () => { state.evidencePage += direction; renderResearch(); document.querySelector(".record-toolbar").scrollIntoView({ behavior: "instant", block: "start" }); });
}
document.querySelectorAll(".nav-item").forEach(link => link.addEventListener("click", () => {
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item === link));
}));
document.querySelector("#open-import").addEventListener("click", () => openImport());
document.querySelector("#close-import").addEventListener("click", () => document.querySelector("#import-dialog").close());
document.querySelector("#download-template").addEventListener("click", () => download("evidence-template.csv", "product_id,platform,kind,market,observed_at,published_at,url,text,source_id,title,tags\n", "text/csv;charset=utf-8"));
document.querySelector("#import-file").addEventListener("change", async event => {
  const file = event.target.files[0]; if (!file) return;
  if (file.size > 1_500_000) { document.querySelector("#import-error").textContent = "文件超过 1.5MB，请分批导入"; return; }
  document.querySelector("#import-content").value = await file.text();
  document.querySelector("#import-format").value = file.name.endsWith(".csv") ? "csv" : "json";
});
document.querySelector("#import-form").addEventListener("submit", event => {
  event.preventDefault();
  withButton(event.submitter, "#import-error", async () => {
    const result = await request("/api/evidence/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format: document.querySelector("#import-format").value, content: document.querySelector("#import-content").value }) });
    document.querySelector("#import-dialog").close(); await loadDashboard();
    showToast(`新增 ${result.added} · 更新 ${result.updated} · 重复 ${result.duplicates}`);
  });
});
document.querySelector("#source-task").addEventListener("change", event => { document.querySelector("#discover-query").value = event.target.value; });
document.querySelector("#discover-form").addEventListener("submit", event => {
  event.preventDefault();
  withButton(event.submitter, "#collection-error", async () => {
    const data = await monidRequest("discover", { query: document.querySelector("#discover-query").value });
    const results = document.querySelector("#endpoint-results"); results.replaceChildren();
    if (!data.results?.length) results.append(element("p", "empty-state", "没有匹配接口"));
    (data.results || []).forEach(endpoint => {
      const row = element("div", "endpoint-row");
      const text = element("div"); text.append(element("strong", "", `${endpoint.provider} ${endpoint.endpoint}`)); text.append(element("p", "muted", endpoint.description));
      row.append(text, actionButton("list-checks", "检查参数与计费", click => withButton(click.currentTarget, "#collection-error", async () => {
        const details = await monidRequest("inspect", { provider: endpoint.provider, endpoint: endpoint.endpoint });
        state.endpoint = endpoint; invalidateQuote();
        document.querySelector("#endpoint-editor").hidden = false;
        document.querySelector("#endpoint-title").textContent = `${endpoint.provider} ${endpoint.endpoint}`;
        document.querySelector("#endpoint-schema").textContent = JSON.stringify(details, null, 2);
        document.querySelector("#endpoint-schema").parentElement.open = true;
        document.querySelector("#run-input").value = "{}";
      })));
      results.append(row);
    });
  });
});
document.querySelector("#run-input").addEventListener("input", invalidateQuote);
document.querySelector("#prepare-run").addEventListener("click", event => withButton(event.currentTarget, "#collection-error", async () => {
  invalidateQuote();
  const job = await monidRequest("prepare", { product_id: state.researchId, provider: state.endpoint.provider, endpoint: state.endpoint.endpoint, input: JSON.parse(document.querySelector("#run-input").value) });
  await loadMonid(); renderQuote(job);
}));
document.querySelector("#confirm-charge").addEventListener("change", event => { document.querySelector("#execute-run").disabled = !event.target.checked || !state.quote; });
document.querySelector("#execute-run").addEventListener("click", event => withButton(event.currentTarget, "#collection-error", async () => {
  if (!state.quote) throw new Error("请先重新检查报价");
  const { id } = state.quote; invalidateQuote();
  try { showJob(await monidRequest("execute", { id, confirmed: true })); }
  finally { await loadMonid(); document.querySelector("#run-quote").hidden = true; }
}));
document.querySelector("#reload-jobs").addEventListener("click", event => withButton(event.currentTarget, "#collection-error", loadMonid));
document.querySelector("#download-result").addEventListener("click", () => download(`monid-${state.job.id}.json`, JSON.stringify(state.job.result || {}, null, 2), "application/json"));
document.querySelector("#mapping-form").addEventListener("submit", event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  withButton(event.submitter, "#collection-error", async () => {
    const mapping = { text: values.text_path, url: values.url_path };
    if (values.source_id_path) mapping.source_id = values.source_id_path;
    if (values.published_at_path) mapping.published_at = values.published_at_path;
    const preview = await monidRequest("preview", { id: state.job.id, items_path: values.items_path, mapping, defaults: { platform: values.platform, kind: values.kind, market: values.market, observed_at: values.observed_at } });
    openImport(preview.records);
  });
});
if (document.querySelector('meta[name="app-mode"]')?.content !== "static") {
  loadMonid().catch(error => { document.querySelector("#monid-status").textContent = error.message; });
}