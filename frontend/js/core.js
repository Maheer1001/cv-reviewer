/* Shared state and helpers. The scripts are classic (non-module) and share these globals. */
const state = {
  config: null,
  session: null,
  tab: "overview",
  file: null,
  editFilter: "pending",
  editingRec: null,
  busy: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const ACTION_LABELS = { keep: "Keep", rewrite: "Rewrite", cut: "Cut", add: "Add", move: "Move", condense: "Condense", verify: "Verify" };
const PRIORITY_BADGE = { critical: "badge-bad", high: "badge-warn", medium: "badge-info", low: "" };
const TIER_LABELS = {
  tier_0_generic: "Generic",
  tier_1_responsibility_only: "Duty only",
  tier_2_technical_detail: "Detail",
  tier_3_concrete_evidence: "Evidence",
  tier_4_verified_outcome: "Proven result",
};
const TIER_BADGE = {
  tier_0_generic: "badge-bad",
  tier_1_responsibility_only: "badge-bad",
  tier_2_technical_detail: "badge-warn",
  tier_3_concrete_evidence: "badge-good",
  tier_4_verified_outcome: "badge-good",
};
const EVIDENCE_LABELS = {
  verified_quote: "Quoted from your CV",
  explicit_omission: "Missing from your CV",
  structural_observation: "Layout and structure",
};
const LEVEL_LABELS = {
  student_graduate: "Student / graduate",
  junior: "Junior",
  mid_level: "Mid-level",
  senior_lead: "Senior / lead",
  career_changer: "Career changer",
  executive: "Executive",
};
const READINESS_BADGE = {
  "Apply now": "badge-good",
  "Apply with targeted edits": "badge-info",
  "Stretch: build evidence first": "badge-warn",
  "Long-term pivot": "badge-bad",
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function markPlaceholders(text) {
  return esc(text).replace(/\[[^\]\n]{2,120}\]/g, (match) => `<mark class="ph">${match}</mark>`);
}

function plural(count, singular, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const type = response.headers.get("content-type") || "";
  const body = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = body && typeof body === "object" ? body.detail : body;
    const error = new Error(typeof detail === "string" && detail ? detail : `Request failed (${response.status})`);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

function postJSON(path, payload) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload || {}) });
}

function toast(message, kind = "") {
  const node = document.createElement("div");
  node.className = `toast ${kind}`;
  node.textContent = message;
  $("#toasts").appendChild(node);
  setTimeout(() => node.remove(), kind === "error" ? 6500 : 3200);
}

function tokens(text) {
  const found = [];
  const pattern = /(\s*)(\[[^\]\n]{2,120}\]|[\w'’][\w'’-]*|[^\s\w])/g;
  let match;
  while ((match = pattern.exec(String(text || ""))) && found.length < 400) {
    found.push({ space: match[1] ? " " : "", text: match[2], key: match[2].toLowerCase() });
  }
  return found;
}

/* Word-level diff using a longest-common-subsequence table. Punctuation is its own token,
   case is ignored, and placeholders stay whole. Mostly-different texts are shown without markup. */
function wordDiff(before, after) {
  const a = tokens(before);
  const b = tokens(after);
  const dp = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i].key === b[j].key ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  if (dp[0][0] < 0.3 * Math.min(a.length, b.length)) {
    return { before: esc(before), after: markPlaceholders(after) };
  }
  const left = [];
  const right = [];
  const push = (side, type, token, html) => {
    const last = side[side.length - 1];
    if (type !== "same" && last && last.type === type) last.html += token.space + html;
    else side.push({ type, space: token.space, html });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i].key === b[j].key) {
      push(left, "same", a[i], esc(a[i].text));
      push(right, "same", b[j], markPlaceholders(b[j].text));
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push(left, "del", a[i], esc(a[i].text));
      i += 1;
    } else {
      push(right, "ins", b[j], markPlaceholders(b[j].text));
      j += 1;
    }
  }
  for (; i < a.length; i += 1) push(left, "del", a[i], esc(a[i].text));
  for (; j < b.length; j += 1) push(right, "ins", b[j], markPlaceholders(b[j].text));
  const render = (side) =>
    side.map((seg) => (seg.type === "same" ? seg.space + seg.html : `${seg.space}<${seg.type}>${seg.html}</${seg.type}>`)).join("").trim();
  return { before: render(left), after: render(right) };
}

function beforeAfter(before, after, labels = ["Before", "After"]) {
  if (!before && !after) return "";
  if (!before) {
    return `<div class="ba-box ba-after"><span class="eyebrow">${esc(labels[1])}</span>${markPlaceholders(after)}</div>`;
  }
  if (!after) {
    return `<div class="ba-box ba-before"><span class="eyebrow">${esc(labels[0])}</span>${esc(before)}</div>`;
  }
  const diff = wordDiff(before, after);
  return `<div class="before-after">
    <div class="ba-box ba-before"><span class="eyebrow">${esc(labels[0])}</span>${diff.before}</div>
    <div class="ba-box ba-after"><span class="eyebrow">${esc(labels[1])}</span>${diff.after}</div>
  </div>`;
}

function scoreTone(value) {
  return value >= 75 ? "good" : value >= 55 ? "warn" : "bad";
}

function scoreBand(value) {
  if (value >= 80) return "Strong";
  if (value >= 65) return "Solid, with gaps";
  if (value >= 50) return "Needs work";
  return "Weak in current form";
}

function badge(text, cls = "") {
  return `<span class="badge ${cls}">${esc(text)}</span>`;
}

function bar(value, tone) {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  return `<div class="bar ${tone || scoreTone(clamped)}"><span style="width:${clamped}%"></span></div>`;
}

function ring(value, caption = "out of 100") {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  const radius = 72;
  const circumference = 2 * Math.PI * radius;
  const colour = { good: "var(--good)", warn: "#d08a1c", bad: "var(--bad)" }[scoreTone(clamped)];
  return `<div class="ring">
    <svg width="170" height="170" viewBox="0 0 170 170" aria-hidden="true">
      <circle cx="85" cy="85" r="${radius}" fill="none" stroke="#e9ebf2" stroke-width="13"></circle>
      <circle cx="85" cy="85" r="${radius}" fill="none" stroke="${colour}" stroke-width="13" stroke-linecap="round"
        stroke-dasharray="${circumference}" stroke-dashoffset="${circumference * (1 - clamped / 100)}"></circle>
    </svg>
    <div class="ring-label"><div><b>${Math.round(clamped)}</b><br><span>${esc(caption)}</span></div></div>
  </div>`;
}

function list(items, cls = "bullets") {
  if (!items || !items.length) return "";
  return `<ul class="${cls}">${items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`;
}

function currentReport() {
  return state.session ? state.session.initial_report : null;
}

function pendingCount() {
  const report = currentReport();
  return report ? report.recommendations.filter((rec) => rec.status === "pending").length : 0;
}

function emptyState(message) {
  return `<div class="card empty">${esc(message)}</div>`;
}
