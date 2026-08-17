/* SPH 下单助手 - 手机端 */
const LS = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};

const state = {
  owner: LS.get("owner", ""),
  repo: LS.get("repo", ""),
  pat: LS.get("pat", ""),
  orders: [],
};

const $ = (id) => document.getElementById(id);
const ST_NAMES = { pending: "待处理", processing: "处理中", submitted: "已提交",
  failed: "失败", completed: "已达标" };

function saveCfg() {
  state.owner = $("in-owner").value.trim();
  state.repo = $("in-repo").value.trim();
  state.pat = $("in-pat").value.trim();
  LS.set("owner", state.owner); LS.set("repo", state.repo); LS.set("pat", state.pat);
  updateCfgHint();
}
function updateCfgHint() {
  $("cfg-hint").textContent = state.owner && state.repo
    ? `${state.owner}/${state.repo}` : "未配置 GitHub 连接";
}
function loadCfg() {
  $("in-owner").value = state.owner;
  $("in-repo").value = state.repo;
  $("in-pat").value = state.pat;
  updateCfgHint();
}

/* ---------- 新建订单 ---------- */
async function submitOrder() {
  saveCfg();
  const msg = $("msg");
  const url = $("in-url").value.trim();
  if (!url) { showMsg("请填写视频链接", false); return; }
  if (!state.owner || !state.repo || !state.pat) {
    showMsg("请先填写 GitHub 连接配置", false); return;
  }
  const targets = {
    like: +$("in-like").value || 0,
    heart: +$("in-heart").value || 0,
    play: +$("in-play").value || 0,
    share: +$("in-share").value || 0,
  };
  if (Object.values(targets).every(v => !v)) {
    showMsg("请至少填写一个下单项目数量", false); return;
  }
  showMsg("正在提交...", true);
  try {
    const res = await fetch(`https://api.github.com/repos/${state.owner}/${state.repo}/issues`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${state.pat}`,
        "Content-Type": "application/json", "Accept": "application/vnd.github+json" },
      body: JSON.stringify({
        title: `order: ${url}`,
        body: JSON.stringify(targets),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showMsg(`提交失败: ${err.message || res.status}`, false);
      return;
    }
    showMsg("已提交，服务器开始自动下单，约1-2分钟完成", true);
    $("in-url").value = ""; $("in-play").value = ""; $("in-like").value = "";
    $("in-heart").value = ""; $("in-share").value = "";
    setTimeout(() => loadOrders(), 5000);
  } catch (e) {
    showMsg(`提交失败: ${e.message}`, false);
  }
}
function showMsg(t, ok) {
  const m = $("msg");
  m.textContent = t;
  m.className = "msg " + (ok ? "ok" : "err");
}

/* ---------- 订单列表 ---------- */
async function loadOrders() {
  saveCfg();
  const box = $("order-list");
  if (!state.owner || !state.repo) {
    box.innerHTML = '<div class="empty">请先在「新建订单」填写连接配置</div>';
    return;
  }
  box.innerHTML = '<div class="empty">加载中...</div>';
  try {
    const res = await fetch(
      `https://raw.githubusercontent.com/${state.owner}/${state.repo}/main/data/orders.json`,
      { cache: "no-store" });
    if (!res.ok) throw new Error("无法读取订单数据(可能还没有订单)");
    const data = await res.json();
    state.orders = (data.orders || []).slice().reverse();
    renderOrders();
  } catch (e) {
    box.innerHTML = `<div class="empty">加载失败: ${e.message}</div>`;
  }
}
function renderOrders() {
  const box = $("order-list");
  const st = $("sel-status").value;
  const list = state.orders.filter(o => !st || o.status === st);
  if (!list.length) { box.innerHTML = '<div class="empty">暂无订单</div>'; return; }
  box.innerHTML = list.map(orderCard).join("");
}
function orderCard(o) {
  const st = ST_NAMES[o.status] || o.status;
  const t = o.targets || {};
  const tg = [];
  const labels = { like: "赞", heart: "爱心", comment: "评论", share: "转发", play: "播放" };
  for (const k of ["like", "heart", "comment", "share", "play"]) {
    if (t[k]) {
      const init = (o.init && o.init[k]) || 0;
      const cur = (o.cur && o.cur[k]) || 0;
      const done = cur >= init + t[k];
      tg.push(`<span class="${done ? "done" : "undone"}">${labels[k]} ${cur}/${init + t[k]}</span>`);
    }
  }
  const res = o.result ? `<div class="meta">平台: ${o.result}</div>` : "";
  return `<div class="order">
    <div class="head">
      <span class="no">${o.order_no || ""}</span>
      <span class="badge ${o.status}">${st}</span>
    </div>
    <div class="title">${(o.video_name ? "【" + o.video_name + "】" : "")} ${o.title || "数据待抓取"}</div>
    <div class="meta">目标: ${tg.join("　")}</div>
    ${res}
    <div class="meta">${(o.created_at || "").slice(5, 16)}</div>
  </div>`;
}

/* ---------- 初始化 ---------- */
document.addEventListener("DOMContentLoaded", () => {
  loadCfg();
  $("tab-new").onclick = () => switchTab("new");
  $("tab-list").onclick = () => switchTab("list");
  $("btn-submit").onclick = submitOrder;
  $("sel-status").onchange = renderOrders;
  ["in-owner", "in-repo", "in-pat"].forEach(id => $(id).addEventListener("change", saveCfg));
  loadOrders();
  setInterval(() => { if (!$("panel-list").hidden) loadOrders(); }, 30000);
});
function switchTab(which) {
  $("tab-new").className = "tab" + (which === "new" ? " active" : "");
  $("tab-list").className = "tab" + (which === "list" ? " active" : "");
  $("panel-new").hidden = which !== "new";
  $("panel-list").hidden = which !== "list";
  if (which === "list") loadOrders();
}
