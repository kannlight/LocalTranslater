"use strict";

const MESSAGES = {
  ja: {
    uiLangAuto: "自動 (OS)",
    logout: "ログアウト",
    password: "パスワード",
    login: "ログイン",
    invalidPassword: "パスワードが違います",
    locked: "試行回数が多すぎます。{s}秒後に再試行してください",
    swap: "言語を入れ替え",
    inputPlaceholder: "翻訳する文章を入力",
    clear: "クリア",
    copy: "コピー",
    copied: "コピーしました",
    instruction: "追加の指示 (任意)",
    instructionPlaceholder: "例: ですます調で / 専門用語は英語のまま / 子ども向けにやさしく",
    translate: "翻訳",
    stop: "停止",
    autoDetect: "自動検出",
    chars: "{n} / {max} 文字",
    queued: "順番待ち中…",
    translating: "翻訳中…",
    done: "完了 ({s}秒)",
    stopped: "停止しました",
    error: "エラー",
    tooLong: "文字数が上限を超えています",
    model: "モデル: {m}",
  },
  en: {
    uiLangAuto: "Auto (OS)",
    logout: "Log out",
    password: "Password",
    login: "Log in",
    invalidPassword: "Incorrect password",
    locked: "Too many attempts. Try again in {s} seconds",
    swap: "Swap languages",
    inputPlaceholder: "Enter text to translate",
    clear: "Clear",
    copy: "Copy",
    copied: "Copied",
    instruction: "Additional instructions (optional)",
    instructionPlaceholder: "e.g. Use a formal tone / Keep technical terms in English",
    translate: "Translate",
    stop: "Stop",
    autoDetect: "Detect language",
    chars: "{n} / {max} chars",
    queued: "Waiting in queue…",
    translating: "Translating…",
    done: "Done ({s}s)",
    stopped: "Stopped",
    error: "Error",
    tooLong: "Text exceeds the character limit",
    model: "Model: {m}",
  },
  zh: {
    uiLangAuto: "自动 (系统)",
    logout: "退出登录",
    password: "密码",
    login: "登录",
    invalidPassword: "密码错误",
    locked: "尝试次数过多，请在 {s} 秒后重试",
    swap: "交换语言",
    inputPlaceholder: "输入要翻译的文本",
    clear: "清空",
    copy: "复制",
    copied: "已复制",
    instruction: "附加指示 (可选)",
    instructionPlaceholder: "例如: 使用正式语气 / 专业术语保留英文",
    translate: "翻译",
    stop: "停止",
    autoDetect: "自动检测",
    chars: "{n} / {max} 字",
    queued: "排队中…",
    translating: "翻译中…",
    done: "完成 ({s}秒)",
    stopped: "已停止",
    error: "错误",
    tooLong: "文本超过字数上限",
    model: "模型: {m}",
  },
};

const $ = (id) => document.getElementById(id);

const store = {
  get(key, fallback = null) {
    try {
      const v = localStorage.getItem("lt." + key);
      return v === null ? fallback : v;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try { localStorage.setItem("lt." + key, value); } catch { /* storage unavailable */ }
  },
};

const state = {
  uiLang: "ja",
  config: null,
  controller: null,
  statusKey: "",
  statusVars: {},
};

function detectUiLang() {
  for (const lang of navigator.languages || [navigator.language]) {
    const base = (lang || "").toLowerCase().split("-")[0];
    if (base in MESSAGES) return base;
  }
  return "ja";
}

function t(key, vars = {}) {
  const msg = MESSAGES[state.uiLang][key] ?? MESSAGES.en[key] ?? key;
  return msg.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
}

function applyUiLang() {
  const pref = store.get("uiLang", "auto");
  state.uiLang = pref === "auto" ? detectUiLang() : pref;
  $("ui-lang").value = pref;
  document.documentElement.lang = state.uiLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
  if (state.config) {
    renderLanguageOptions();
    $("model").textContent = t("model", { m: state.config.model });
  }
  updateCharCount();
  renderStatus();
}

function languageLabel(code, fallback) {
  try {
    const names = new Intl.DisplayNames([state.uiLang], { type: "language" });
    const name = names.of(code);
    if (name && name !== code) return name;
  } catch { /* Intl.DisplayNames unsupported */ }
  return fallback;
}

function renderLanguageOptions() {
  const source = $("source");
  const target = $("target");
  const sourceValue = source.value || store.get("source", "auto");
  const targetValue = target.value || store.get("target", "en");

  const options = state.config.languages.map(({ code, name }) => new Option(languageLabel(code, name), code));
  source.replaceChildren(new Option(t("autoDetect"), "auto"), ...options.map((o) => o.cloneNode(true)));
  target.replaceChildren(...options);

  source.value = sourceValue;
  if (!source.value) source.value = "auto";
  target.value = targetValue;
  if (!target.value) target.value = "en";
  updateSwap();
}

function updateSwap() {
  $("swap").disabled = $("source").value === "auto";
}

function updateCharCount() {
  if (!state.config) return;
  const n = $("input").value.length;
  const max = state.config.max_input_chars;
  const el = $("char-count");
  el.textContent = t("chars", { n, max });
  el.classList.toggle("error", n > max);
}

function setStatus(key, vars = {}) {
  state.statusKey = key;
  state.statusVars = vars;
  renderStatus();
}

function renderStatus() {
  $("status").textContent = state.statusKey ? t(state.statusKey, state.statusVars) : "";
}

function showView(name) {
  $("login-view").hidden = name !== "login";
  $("app-view").hidden = name !== "app";
}

async function loadApp() {
  const res = await fetch("/api/config");
  if (res.status === 401) {
    showView("login");
    $("password").focus();
    return;
  }
  state.config = await res.json();
  $("instruction").maxLength = state.config.max_instruction_chars;
  showView("app");
  applyUiLang();
}

async function init() {
  $("instruction").value = store.get("instruction", "");
  if ($("instruction").value) $("instruction-box").open = true;
  applyUiLang();

  const session = await (await fetch("/api/session")).json();
  $("logout").hidden = !session.auth_required;
  await loadApp();
}

async function login(event) {
  event.preventDefault();
  const errorEl = $("login-error");
  errorEl.textContent = "";
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: $("password").value }),
  });
  if (res.ok) {
    $("password").value = "";
    await loadApp();
    return;
  }
  const body = await res.json().catch(() => ({}));
  errorEl.textContent = res.status === 429 ? t("locked", { s: body.retry_after }) : t("invalidPassword");
}

async function logout() {
  await fetch("/api/logout", { method: "POST" });
  state.config = null;
  showView("login");
}

function setBusy(busy) {
  $("translate").hidden = busy;
  $("stop").hidden = !busy;
}

async function translate() {
  const text = $("input").value;
  if (!text.trim() || state.controller) return;
  if (text.length > state.config.max_input_chars) {
    setStatus("tooLong");
    return;
  }

  const output = $("output");
  output.textContent = "";
  output.classList.remove("error");
  const controller = new AbortController();
  state.controller = controller;
  setBusy(true);
  setStatus("translating");
  const started = performance.now();

  try {
    const res = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        source: $("source").value,
        target: $("target").value,
        instruction: $("instruction").value,
      }),
      signal: controller.signal,
    });
    if (res.status === 401) {
      showView("login");
      return;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;
    while (!finished) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.status === "queued") setStatus("queued");
        else if (event.status === "started") setStatus("translating");
        else if (event.delta) output.textContent += event.delta;
        else if (event.error) throw new Error(event.error);
        else if (event.done) finished = true;
      }
    }
    // Models sometimes end the output with a trailing newline; drop it.
    output.textContent = output.textContent.replace(/\s+$/, "");
    setStatus("done", { s: ((performance.now() - started) / 1000).toFixed(1) });
  } catch (err) {
    if (err.name === "AbortError") {
      setStatus("stopped");
    } else {
      setStatus("error");
      output.classList.add("error");
      output.textContent = `${t("error")}: ${err.message}`;
    }
  } finally {
    state.controller = null;
    setBusy(false);
  }
}

function swapLanguages() {
  const source = $("source");
  const target = $("target");
  if (source.value === "auto") return;
  [source.value, target.value] = [target.value, source.value];
  const out = $("output");
  if (out.textContent && !out.classList.contains("error")) {
    $("input").value = out.textContent;
    out.textContent = "";
    setStatus("");
  }
  store.set("source", source.value);
  store.set("target", target.value);
  updateCharCount();
}

async function copyOutput() {
  const text = $("output").textContent;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // navigator.clipboard needs a secure context (HTTPS); plain-HTTP LAN access falls back to execCommand.
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  setStatus("copied");
}

$("login-form").addEventListener("submit", login);
$("logout").addEventListener("click", logout);
$("ui-lang").addEventListener("change", (e) => { store.set("uiLang", e.target.value); applyUiLang(); });
$("source").addEventListener("change", (e) => { store.set("source", e.target.value); updateSwap(); });
$("target").addEventListener("change", (e) => store.set("target", e.target.value));
$("swap").addEventListener("click", swapLanguages);
$("input").addEventListener("input", updateCharCount);
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    translate();
  }
});
$("instruction").addEventListener("input", (e) => store.set("instruction", e.target.value));
$("clear").addEventListener("click", () => { $("input").value = ""; $("output").textContent = ""; setStatus(""); updateCharCount(); $("input").focus(); });
$("copy").addEventListener("click", copyOutput);
$("translate").addEventListener("click", translate);
$("stop").addEventListener("click", () => state.controller?.abort());

init();
