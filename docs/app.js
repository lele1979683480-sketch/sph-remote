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
const ST_NAMES = { pending: "排队中", processing: "处理中", success: "已达标",
  failed: "失败", partial_success: "部分成功" };

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
    showMsg("✅ 订单已提交，正在排队处理（约1-3分钟），可在「订单列表」查看进度", true);
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
    state.logs = data.logs || [];
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
  const labels = { like: "赞", heart: "爱心", play: "播放", share: "转发" };
  const itst = { wait: "等待中", processing: "处理中", success: "成功", failed: "失败" };
  const items = o.items || {};
  const targets = o.targets || {};
  const rows = ["like", "heart", "play", "share"].map(k => {
    const qty = targets[k] || 0;
    if (!qty) return "";
    const it = items[k] || {};
    const stc = it.status === "success" ? "done"
      : it.status === "failed" ? "undone" : "";
    const init = (o.init && o.init[k]) || 0;
    const cur = (o.cur && o.cur[k]) || 0;
    const progress = `(${cur}/${init + qty})`;
    return `<div class="proj ${stc}">
      <span class="pl">${labels[k]}</span> ×${qty} ${progress}
      <span class="badge-s ${it.status || ""}">${itst[it.status] || (it.status || "等待中")}</span>
      <div class="pstep">${escHtml(it.step || "")}</div>
    </div>`;
  }).join("");
  const errs = Object.keys(labels).map(k => (items[k] || {}).error).filter(Boolean);
  const errBlock = errs.length
    ? `<div class="errbox">${errs.map(e => `<div>❌ ${escHtml(e)}</div>`).join("")}</div>` : "";
  const orderNo = o.platform_order_no
    ? `<div class="meta">平台订单号: ${escHtml(o.platform_order_no)}</div>` : "";
  return `<div class="order">
    <div class="head">
      <span class="no">${o.order_no || ""}</span>
      <span class="badge ${o.status}">${st}</span>
    </div>
    <div class="title">${escHtml((o.video_name ? "【" + o.video_name + "】" : "") + (o.title || "数据待抓取"))}</div>
    <div class="meta">步骤: ${escHtml(o.step || "等待处理")}</div>
    ${rows}
    ${orderNo}
    ${errBlock}
    <div class="meta">${(o.created_at || "").slice(5, 16)}</div>
  </div>`;
}

/* ---------- 平台配置(写入 GitHub Secrets, 手机端管理) ---------- */
const SECRETS = [
  { name: "JUZI_ACCOUNT", el: "in-jz-acct", label: "橘子账号" },
  { name: "JUZI_PASSWORD", el: "in-jz-pwd", label: "橘子密码" },
  { name: "JUZI_PLAY_GOODS", el: "in-play-goods", label: "播放商品编码" },
  { name: "JUZI_FORWARD_GOODS", el: "in-share-goods", label: "转发商品编码" },
  { name: "IMT_ACCOUNT", el: "in-imt-acct", label: "imt账号" },
  { name: "IMT_PASSWORD", el: "in-imt-pwd", label: "imt密码" },
  { name: "IMT_LIKE_GOODS", el: "in-like-goods", label: "点赞商品编码" },
  { name: "IMT_HEART_GOODS", el: "in-heart-goods", label: "爱心商品编码" },
];
async function ghApi(path, opts = {}) {
  const res = await fetch("https://api.github.com" + path, {
    ...opts,
    headers: {
      ...(opts.headers || {}),
      "Authorization": `Bearer ${state.pat}`,
      "Accept": "application/vnd.github+json",
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || `HTTP ${res.status}`);
  }
  return res;
}
async function loadSecretStatus() {
  if (!state.owner || !state.repo || !state.pat) {
    $("cfg-status").textContent = "请先在「新建订单」填写连接配置";
    return;
  }
  try {
    const res = await ghApi(`/repos/${state.owner}/${state.repo}/actions/secrets`);
    const data = await res.json();
    const names = new Set((data.secrets || []).map(s => s.name));
    const list = SECRETS.map(s => (names.has(s.name) ? s.label : ""));
    const done = list.filter(Boolean);
    $("cfg-status").textContent = done.length
      ? `已配置: ${done.join("、")}　未配置: ${SECRETS.filter(s => !names.has(s.name)).map(s => s.label).join("、") || "无"}`
      : "尚未配置任何平台账号（密码不会回显，重新填写保存即可覆盖）";
  } catch (e) {
    $("cfg-status").textContent = `读取配置状态失败: ${e.message}`;
  }
}
async function savePlatformCfg() {
  saveCfg();
  const msg = $("cfg-msg");
  if (!state.owner || !state.repo || !state.pat) {
    msg.textContent = "请先填写 GitHub 连接配置"; msg.className = "msg err"; return;
  }
  if (!window.libsodium) { msg.textContent = "加密库未加载，请检查网络"; msg.className = "msg err"; return; }
  await libsodium.ready;
  // 收集非空项
  const items = SECRETS.filter(s => $(s.el).value.trim());
  if (!items.length) { msg.textContent = "没有需要保存的内容"; msg.className = "msg err"; return; }
  msg.textContent = "加密并保存中..."; msg.className = "msg";
  try {
    const pkRes = await ghApi(`/repos/${state.owner}/${state.repo}/actions/secrets/public-key`);
    const pk = await pkRes.json();
    const pubKey = libsodium.from_base64(pk.key, libsodium.base64_variants.ORIGINAL);
    for (const s of items) {
      const enc = libsodium.crypto_box_seal(libsodium.from_string($(s.el).value.trim()), pubKey);
      const b64 = libsodium.to_base64(enc, libsodium.base64_variants.ORIGINAL);
      await ghApi(`/repos/${state.owner}/${state.repo}/actions/secrets/${s.name}`, {
        method: "PUT",
        body: JSON.stringify({ encrypted_value: b64, key_id: pk.key_id }),
      });
    }
    msg.textContent = "保存成功！下单时自动使用新配置";
    msg.className = "msg ok";
    ["in-jz-pwd", "in-imt-pwd"].forEach(id => { $(id).value = ""; });
    loadSecretStatus();
  } catch (e) {
    msg.textContent = `保存失败: ${e.message}`;
    msg.className = "msg err";
  }
}

/* ---------- 日志 + 系统控制 ---------- */
function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}
function renderLogs() {
  const box = $("log-list");
  if (!state.logs || !state.logs.length) { box.innerHTML = '<div class="empty">暂无日志（有下单/检查动作后出现）</div>'; return; }
  box.innerHTML = state.logs.slice().reverse().map(l => {
    const cls = { ok: "log-ok", error: "log-err", warn: "log-warn", order: "log-order" }[l.kind] || "";
    return `<div class="logline ${cls}"><span class="lt">${escHtml((l.time || "").slice(5, 19))}</span> ${escHtml(l.message)}</div>`;
  }).join("");
}
async function loadLogs() {
  if (!state.owner || !state.repo) { renderLogs(); return; }
  try {
    const res = await fetch(
      `https://raw.githubusercontent.com/${state.owner}/${state.repo}/main/data/orders.json`,
      { cache: "no-store" });
    if (!res.ok) throw new Error("读取失败");
    const data = await res.json();
    state.logs = data.logs || [];
  } catch (e) {
    state.logs = [{ time: "", kind: "error", message: "日志读取失败: " + e.message }];
  }
  renderLogs();
}
async function loadPauseState() {
  if (!state.owner || !state.repo || !state.pat) {
    $("sys-state").textContent = "请先填写连接配置";
    $("btn-pause").hidden = true; $("btn-resume").hidden = true;
    return;
  }
  try {
    const res = await fetch(
      `https://api.github.com/repos/${state.owner}/${state.repo}/contents/data/pause.flag`,
      { headers: { Authorization: `Bearer ${state.pat}`, Accept: "application/vnd.github+json" } });
    const paused = res.status === 200;
    $("sys-state").textContent = paused ? "⏸️ 已暂停（新订单会被拒绝）" : "▶️ 运行中（正常接收订单）";
    $("btn-pause").hidden = paused;
    $("btn-resume").hidden = !paused;
  } catch (e) {
    $("sys-state").textContent = "状态读取失败: " + e.message;
  }
}
async function pauseSystem() {
  if (!state.owner || !state.repo || !state.pat) { alert("请先填写连接配置"); return; }
  try {
    await ghApi(`/repos/${state.owner}/${state.repo}/contents/data/pause.flag`, {
      method: "PUT",
      body: JSON.stringify({ message: "pause system [skip ci]", content: btoa("paused"), branch: "main" }),
    });
    loadPauseState();
  } catch (e) { alert("停止失败: " + e.message); }
}
async function resumeSystem() {
  if (!state.owner || !state.repo || !state.pat) { alert("请先填写连接配置"); return; }
  try {
    const res = await fetch(
      `https://api.github.com/repos/${state.owner}/${state.repo}/contents/data/pause.flag`,
      { headers: { Authorization: `Bearer ${state.pat}`, Accept: "application/vnd.github+json" } });
    if (res.status === 200) {
      const meta = await res.json();
      await ghApi(`/repos/${state.owner}/${state.repo}/contents/data/pause.flag`, {
        method: "DELETE",
        body: JSON.stringify({ message: "resume system [skip ci]", sha: meta.sha, branch: "main" }),
      });
    }
    loadPauseState();
  } catch (e) { alert("启动失败: " + e.message); }
}

/* ---------- 初始化 ---------- */
document.addEventListener("DOMContentLoaded", () => {
  loadCfg();
  $("tab-new").onclick = () => switchTab("new");
  $("tab-list").onclick = () => switchTab("list");
  $("tab-cfg").onclick = () => switchTab("cfg");
  $("tab-log").onclick = () => switchTab("log");
  $("btn-submit").onclick = submitOrder;
  $("btn-save-cfg").onclick = savePlatformCfg;
  $("btn-pause").onclick = pauseSystem;
  $("btn-resume").onclick = resumeSystem;
  $("sel-status").onchange = renderOrders;
  ["in-owner", "in-repo", "in-pat"].forEach(id => $(id).addEventListener("change", saveCfg));
  loadOrders();
  setInterval(() => { if (!$("panel-list").hidden) loadOrders(); }, 30000);
});
function switchTab(which) {
  ["new", "list", "cfg", "log"].forEach(k => {
    $(`tab-${k}`).className = "tab" + (k === which ? " active" : "");
    $(`panel-${k}`).hidden = k !== which;
  });
  if (which === "list") loadOrders();
  if (which === "cfg") loadSecretStatus();
  if (which === "log") { loadLogs(); loadPauseState(); }
}
