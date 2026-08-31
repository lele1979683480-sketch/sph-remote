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
const ST_NAMES = { pending: "排队中", processing: "已下单·执行中", success: "达标",
  failed: "未执行", partial_success: "部分达标" };

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
  // 赞+爱心同时填:合并为同一个任务,数量取较小值(与电脑版一致),提交前明确告知
  if (targets.like > 0 && targets.heart > 0) {
    const m = Math.min(targets.like, targets.heart);
    const ok = confirm(`赞(${targets.like})和爱心(${targets.heart})将合并为同一个任务，\n数量按较少者执行：赞×${m} + 爱心×${m}（1次任务同时做两个动作）。\n确定提交？`);
    if (!ok) return;
    targets.like = m;
    targets.heart = m;
  }
  // 用无引号的文本格式提交,避免 GitHub Actions 对 JSON 引号的处理问题
  const bodyText = Object.entries(targets)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${k}:${v}`)
    .join(";");
  showMsg("正在提交...", true);
  const btn = $("btn-submit");
  btn.disabled = true;  // 防重复提交
  try {
    const res = await fetch(`https://api.github.com/repos/${state.owner}/${state.repo}/issues`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${state.pat}`,
        "Content-Type": "application/json", "Accept": "application/vnd.github+json" },
      body: JSON.stringify({
        title: `order: ${url}`,
        body: bodyText,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showMsg(`提交失败: ${err.message || res.status}`, false);
      btn.disabled = false;
      return;
    }
    showMsg("⏳ 订单已提交，处理中（约1-3分钟）完成前按钮锁定，处理完自动解锁", true);
    $("in-url").value = ""; $("in-play").value = ""; $("in-like").value = "";
    $("in-heart").value = ""; $("in-share").value = "";
    startOrderWait(url);  // 锁定按钮直到该订单被处理完
  } catch (e) {
    showMsg(`提交失败: ${e.message}`, false);
    btn.disabled = false;
  }
}
let submitWaitTimer = null;
function startOrderWait(url) {
  // 轮询该链接的订单, 状态离开"排队中"即视为处理完成, 解锁按钮继续下单
  const btn = $("btn-submit");
  clearInterval(submitWaitTimer);
  let tried = 0;
  submitWaitTimer = setInterval(async () => {
    tried++;
    try {
      const data = await fetchOrdersJson();
      const ord = (data.orders || []).filter(o => o.url === url)
        .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
      if (ord && ord.status !== "pending") {
        clearInterval(submitWaitTimer);
        btn.disabled = false;
        showMsg(`✅ 订单 ${ord.order_no} 已处理（${ST_NAMES[ord.status] || ord.status}），可继续下单`, true);
        loadOrders();
        return;
      }
    } catch (e) { /* 网络抖动忽略, 继续轮询 */ }
    if (tried >= 12) {  // 最多等约6分钟
      clearInterval(submitWaitTimer);
      btn.disabled = false;
      showMsg("订单已提交但等待确认超时，请到订单列表查看；按钮已恢复", false);
    }
  }, 30000);
}
function showMsg(t, ok) {
  const m = $("msg");
  m.textContent = t;
  m.className = "msg " + (ok ? "ok" : "err");
}

/* ---------- 订单列表 ---------- */
async function fetchOrdersJson(timeoutMs = 12000) {
  // 优先读同域 Pages 静态文件(不依赖 raw CDN, 大陆网络稳定); 失败再退回 API/raw
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    // 1) 同域 Pages 静态文件(最新同步, 无墙)
    try {
      const res = await fetch("data/orders.json", { cache: "no-store", signal: ctl.signal });
      if (res.ok) return await res.json();
    } catch (e) { /* 继续尝试下一来源 */ }
    // 2) GitHub API(带PAT)
    if (state.owner && state.repo && state.pat) {
      try {
        const res = await fetch(
          `https://api.github.com/repos/${state.owner}/${state.repo}/contents/data/orders.json`,
          { cache: "no-store", signal: ctl.signal,
            headers: { "Authorization": `Bearer ${state.pat}`, "Accept": "application/vnd.github+json" } });
        if (res.ok) {
          const meta = await res.json();
          return JSON.parse(atob(meta.content));
        }
      } catch (e) { /* API 失败则继续 */ }
    }
    // 3) raw CDN(最后兜底)
    const res = await fetch(
      `https://raw.githubusercontent.com/${state.owner}/${state.repo}/main/data/orders.json`,
      { cache: "no-store", signal: ctl.signal });
    if (!res.ok) throw new Error("无法读取订单数据(可能还没有订单)");
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}
async function loadOrders() {
  saveCfg();
  const box = $("order-list");
  if (!state.owner || !state.repo) {
    box.innerHTML = '<div class="empty">请先在「新建订单」填写连接配置</div>';
    return;
  }
  box.innerHTML = '<div class="empty">加载中...</div>';
  try {
    const data = await fetchOrdersJson();
    state.orders = (data.orders || []).slice().reverse();
    state.logs = data.logs || [];
    renderOrders();
  } catch (e) {
    box.innerHTML = `<div class="empty">加载失败: ${e.message}（请检查网络，稍后自动重试）</div>`;
  }
}
function renderOrders() {
  const box = $("order-list");
  const st = $("sel-status").value;
  const list = state.orders.filter(o => !st || o.status === st);
  const bar = $("del-bar");
  if (!list.length) { box.innerHTML = '<div class="empty">暂无订单</div>'; if (bar) bar.hidden = true; return; }
  if (bar) bar.hidden = false;
  box.innerHTML = list.map(orderCard).join("");
}
function fmtTime(s) {
  // orders.json 时间由 Actions(UTC) 生成,统一转北京时间显示
  if (!s) return "";
  try {
    const t = new Date(String(s).replace(" ", "T") + "Z");
    const b = new Date(t.getTime() + 8 * 3600 * 1000);
    const p = n => String(n).padStart(2, "0");
    return `${b.getUTCFullYear()}-${p(b.getUTCMonth() + 1)}-${p(b.getUTCDate())} ${p(b.getUTCHours())}:${p(b.getUTCMinutes())}`;
  } catch (e) { return s; }
}
async function triggerFetch(orderNo, btn) {
  // 手动抓取指定订单的最新数据并重新判定达标
  if (!state.owner || !state.repo || !state.pat) { alert("请先填写连接配置"); return; }
  if (btn) { btn.disabled = true; btn.textContent = "抓取中..."; }
  try {
    const res = await fetch(
      `https://api.github.com/repos/${state.owner}/${state.repo}/actions/workflows/check.yml/dispatches`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${state.pat}`, "Content-Type": "application/json",
        "Accept": "application/vnd.github+json" },
      body: JSON.stringify({ ref: "main", inputs: { order_no: orderNo } }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`触发抓取失败: ${err.message || res.status}（需要 PAT 有 Actions 写权限）`);
      return;
    }
    alert("已触发抓取，约1分钟内完成，随后自动刷新");
    setTimeout(() => loadOrders(), 50000);
  } catch (e) {
    alert("触发抓取失败: " + e.message);
  } finally {
    if (btn) setTimeout(() => { btn.disabled = false; btn.textContent = "抓取数据"; }, 70000);
  }
}
function checkedOrders() {
  return [...document.querySelectorAll(".order-check:checked")].map(c => c.value);
}
async function deleteChecked() {
  const nos = checkedOrders();
  if (!nos.length) { alert("请先勾选要删除的订单"); return; }
  if (!confirm(`确认删除 ${nos.length} 个订单？删除后不可恢复。`)) return;
  await deleteOrders(nos);
}
async function deleteAll() {
  if (!state.orders.length) { alert("暂无订单"); return; }
  if (!confirm(`确认删除全部 ${state.orders.length} 个订单？删除后不可恢复。`)) return;
  await deleteOrders(state.orders.map(o => o.order_no));
}
async function deleteOrders(nos) {
  // 从 orders.json 移除选中订单(同步 data/ 与 docs/data/), 需要 PAT 写文件权限
  try {
    const data = await fetchOrdersJson();
    data.orders = (data.orders || []).filter(o => !nos.includes(o.order_no));
    const text = JSON.stringify(data, null, 2);
    const enc = btoa(unescape(encodeURIComponent(text)));
    for (const p of ["data/orders.json", "docs/data/orders.json"]) {
      const meta = await ghApi(`/repos/${state.owner}/${state.repo}/contents/${p}`);
      const sha = (await meta.json()).sha;
      await ghApi(`/repos/${state.owner}/${state.repo}/contents/${p}`, {
        method: "PUT",
        body: JSON.stringify({ message: "delete orders [skip ci]", content: enc, sha }),
      });
    }
    alert("删除成功");
    loadOrders();
  } catch (e) {
    alert("删除失败: " + e.message + "（需要 PAT 有写文件权限）");
  }
}
function copyLink(url, ev) {
  ev && ev.stopPropagation();
  const done = () => {
    const btn = ev && ev.currentTarget;
    if (btn) { const t = btn.textContent; btn.textContent = "✓ 已复制"; setTimeout(() => { btn.textContent = t; }, 1500); }
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(url).then(done).catch(() => legacyCopy(url, done));
  } else {
    legacyCopy(url, done);
  }
}
function legacyCopy(url, done) {
  try {
    const ta = document.createElement("textarea");
    ta.value = url;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    done();
  } catch (e) {
    alert("复制失败，请长按链接手动复制");
  }
}
function escAttr(s) {
  return escHtml(s).replace(/'/g, "&#39;");
}
function orderCard(o) {
  const st = ST_NAMES[o.status] || o.status;
  const labels = { like: "赞", heart: "爱心", play: "播放", share: "转发" };
  const targets = o.targets || {};
  const init = o.init || {};
  const cur = o.cur || {};

  // 链接行(纯文字 + 复制按钮)
  const url = o.url || "";
  const linkRow = url
    ? `<div class="meta link-row">
        <span class="link-text">🔗 ${escHtml(url)}</span>
        <button class="btn-link" onclick="copyLink('${escAttr(url)}', event)">复制</button>
      </div>` : "";

  // 视频初始数据(赞/爱心/转发/评论/播放)
  const initParts = [];
  [["like", "赞"], ["heart", "爱心"], ["share", "转发"], ["comment", "评论"], ["play", "播放"]].forEach(([k, lb]) => {
    if (init[k] !== undefined) initParts.push(`${lb} ${init[k]}`);
  });
  const initRow = initParts.length
    ? `<div class="meta">视频初始数据：${escHtml(initParts.join(" ｜ "))}</div>` : "";

  // 现在数据(最新抓取值)
  const curParts = [];
  [["like", "赞"], ["heart", "爱心"], ["share", "转发"], ["comment", "评论"], ["play", "播放"]].forEach(([k, lb]) => {
    if (cur[k] !== undefined) curParts.push(`${lb} ${cur[k]}`);
  });
  const curRow = curParts.length
    ? `<div class="meta">现在数据：${escHtml(curParts.join(" ｜ "))}</div>` : "";

  // 已完成进度: 增长 = 当前 - 初始, 封顶为预期
  const progParts = [];
  ["like", "heart", "play", "share"].forEach(k => {
    const qty = targets[k] || 0;
    if (!qty) return;
    const grow = Math.max(0, (cur[k] || 0) - (init[k] || 0));
    const done = Math.min(grow, qty);
    const cls = grow >= qty ? "done" : "undone";
    progParts.push(`<span class="${cls}">${labels[k]} ${done}/${qty}${grow >= qty ? "✓" : ""}</span>`);
  });
  const progRow = progParts.length
    ? `<div class="tgt">已完成：${progParts.join(" ｜ ")}</div>` : "";

  const badgeCls = o.status === "success" ? "success"
    : o.status === "failed" ? "failed"
    : o.status === "partial_success" ? "partial_success"
    : o.status === "pending" ? "pending" : "processing";

  return `<div class="order" id="ord-${escAttr(o.order_no)}">
    <div class="head">
      <label class="ck"><input type="checkbox" class="order-check" value="${escAttr(o.order_no)}"></label>
      <span class="no">${escHtml(o.order_no || "")}</span>
      <span class="badge ${badgeCls}">${st}</span>
    </div>
    ${linkRow}
    <div class="title">${escHtml((o.video_name ? "【" + o.video_name + "】" : "") + (o.title || "数据待抓取"))}</div>
    ${initRow}
    ${curRow}
    ${progRow}
    <div class="meta row-foot">
      <span>${fmtTime(o.created_at)}</span>
      <button class="btn-fetch" onclick="triggerFetch('${escAttr(o.order_no)}', this)">抓取数据</button>
    </div>
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
  { name: "JUZI_LOCALSTORAGE", el: "in-jz-localstorage", label: "橘子登录凭证" },
  { name: "IMT_LOCALSTORAGE", el: "in-imt-localstorage", label: "imt登录凭证" },
  { name: "IMT_SAMPLE_IMG", el: "in-imt-sample", label: "imt样图地址" },
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
  if (!window.sodium) { msg.textContent = "加密库未加载，请检查网络"; msg.className = "msg err"; return; }
  const libsodium = window.sodium;
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
    ["in-jz-pwd", "in-imt-pwd", "in-jz-localstorage", "in-imt-localstorage"].forEach(id => { $(id).value = ""; });
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
    return `<div class="logline ${cls}"><span class="lt">${escHtml(fmtTime(l.time))}</span> ${escHtml(l.message)}</div>`;
  }).join("");
}
async function loadLogs() {
  if (!state.owner || !state.repo) { renderLogs(); return; }
  try {
    const data = await fetchOrdersJson();
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
    $("sys-state").textContent = paused
      ? "⏸️ 已紧急停止（新订单会被拒绝，点「恢复下单」继续）"
      : "▶️ 运行中（提交订单立即下单）";
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
