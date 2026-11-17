/* Edits tab: follow-up questions and recommendation decisions. */
const STATUS_BADGE = { pending: ["Pending", ""], accepted: ["Accepted", "badge-good"], rejected: ["Rejected", ""], unresolved: ["Unresolved", "badge-warn"] };
const RESOLUTION_LABELS = {
  answered: "Answered",
  skipped: "Skipped",
  dont_know: "Didn't know",
  confidential: "Confidential",
  use_existing: "Kept existing wording",
};
const DECISION_TOASTS = {
  accept: "Accepted. The revised CV has been updated.",
  alternative: "An alternative wording is shown under the suggestion.",
  reject: "Rejected. Your original wording stays.",
  unresolved: "Marked as unresolved.",
  undo: "Undone. The original wording is restored.",
};
const FILTERS = [["pending", "To review"], ["accepted", "Accepted"], ["unresolved", "Unresolved"], ["rejected", "Rejected"], ["all", "All"]];

function evidenceBadge(rec) {
  const cls = { verified_quote: "badge-good", explicit_omission: "badge-info" }[rec.evidence_type] || "";
  return badge(EVIDENCE_LABELS[rec.evidence_type] || "Suggestion", cls);
}

function recBody(rec) {
  const text = rec.user_edited_text || rec.suggested_text;
  if (state.editingRec === rec.rec_id) {
    return `<label class="field">Your version<span class="hint">Use real facts only. Anything in [brackets] blocks export until you replace it.</span>
        <textarea data-edit-text style="min-height:90px">${esc(text || rec.original_text)}</textarea></label>
      <div class="row"><button class="btn btn-primary btn-sm" data-save-edit>Save and accept</button><button class="btn btn-ghost btn-sm" data-cancel-edit>Cancel</button></div>`;
  }
  if (rec.action === "keep") {
    return `<div class="ba-box ba-after"><span class="eyebrow">Keep as it is</span>${esc(rec.original_text)}</div>`;
  }
  if (rec.action === "cut" && !text) {
    return `${beforeAfter(rec.original_text, "", ["Remove this line", ""])}`;
  }
  const alternative = rec.alternative_text && rec.status !== "accepted"
    ? `<p class="small"><b>Alternative:</b> ${markPlaceholders(rec.alternative_text)}</p>`
    : "";
  return beforeAfter(rec.original_text, text, ["Your CV", rec.action === "add" ? "Add" : "Suggested"]) + alternative;
}

function recButtons(rec) {
  if (state.editingRec === rec.rec_id) return "";
  if (rec.status === "accepted" || rec.status === "rejected") {
    return `<button class="btn btn-sm" data-decision="undo">Undo</button>`;
  }
  return `<button class="btn btn-good btn-sm" data-decision="accept">Accept</button>
    ${rec.action === "keep" ? "" : `<button class="btn btn-sm" data-edit>Edit</button>`}
    ${rec.alternative_text
      ? `<button class="btn btn-sm" data-use-alt>Use alternative</button>`
      : ["rewrite", "condense", "verify"].includes(rec.action) ? `<button class="btn btn-sm" data-decision="alternative">Show an alternative</button>` : ""}
    <button class="btn btn-bad btn-sm" data-decision="reject">Reject</button>
    ${rec.status === "pending" ? `<button class="btn btn-ghost btn-sm" data-decision="unresolved">Decide later</button>` : ""}`;
}

function recCard(rec) {
  const [statusLabel, statusClass] = STATUS_BADGE[rec.status] || [rec.status, ""];
  const extras = [
    rec.why_stronger ? `<p class="small"><b>Why:</b> ${esc(rec.why_stronger)}</p>` : "",
    rec.recruiter_benefit ? `<p class="small muted">${esc(rec.recruiter_benefit)}</p>` : "",
    rec.missing_info_required ? `<div class="callout callout-warn small"><b>Needs from you:</b> ${esc(rec.missing_info_required)}</div>` : "",
    rec.action === "cut" && rec.value_lost_if_removed ? `<p class="faint">What you lose: ${esc(rec.value_lost_if_removed)}</p>` : "",
    rec.action === "move" && rec.target_destination ? `<p class="faint">Move to: ${esc(rec.target_destination)}</p>` : "",
  ].join("");
  return `<div class="card rec ${rec.status} stack" data-rec="${esc(rec.rec_id)}">
    <div class="spread">
      <div class="row">${badge(ACTION_LABELS[rec.action] || rec.action, "badge-accent")}${badge(rec.priority, PRIORITY_BADGE[rec.priority])}<span class="faint">${esc(rec.section_name)}</span></div>
      <div class="row">${evidenceBadge(rec)}${badge(statusLabel, statusClass)}</div>
    </div>
    ${recBody(rec)}
    ${extras}
    <div class="rec-actions">${recButtons(rec)}</div>
  </div>`;
}

function questionCard(question) {
  return `<div class="card question stack" data-question="${esc(question.question_id)}">
    <div class="spread"><b>${esc(question.primary_question)}</b>${badge(question.priority, PRIORITY_BADGE[question.priority])}</div>
    <div class="quote small">${esc(question.original_excerpt)}</div>
    ${list(question.sub_questions, "bullets small")}
    <p class="faint">Why a recruiter asks: ${esc(question.why_recruiter_asks)}</p>
    <textarea data-answer style="min-height:70px" placeholder="Answer with real facts only. Leave it blank if you don't know."></textarea>
    <div class="row">
      <button class="btn btn-primary btn-sm" data-resolution="answered">Use my answer</button>
      <button class="btn btn-sm" data-resolution="dont_know">I don't know</button>
      <button class="btn btn-sm" data-resolution="confidential">It's confidential</button>
      <button class="btn btn-sm" data-resolution="use_existing">Keep my wording</button>
      <button class="btn btn-ghost btn-sm" data-resolution="skipped">Skip</button>
    </div>
  </div>`;
}

function renderEdits() {
  const report = currentReport();
  const recs = report.recommendations;
  const counts = { all: recs.length, pending: 0, accepted: 0, rejected: 0, unresolved: 0 };
  recs.forEach((rec) => {
    counts[rec.status] = (counts[rec.status] || 0) + 1;
  });
  const decided = counts.accepted + counts.rejected;
  const visible = recs.filter((rec) => state.editFilter === "all" || rec.status === state.editFilter);
  const open = report.follow_up_questions.filter((question) => question.resolution_type === "unanswered");
  const closed = report.follow_up_questions.filter((question) => question.resolution_type !== "unanswered");
  const filters = FILTERS.map(
    ([key, label]) => `<button class="chip ${state.editFilter === key ? "active" : ""}" data-filter="${key}">${esc(label)}<span class="count">${counts[key] || 0}</span></button>`
  ).join("");
  return `<div class="stack-lg">
    <div class="card stack">
      <div class="progress-wrap">
        <div><div class="spread"><b>Review progress</b><span class="faint">${decided} of ${recs.length} decided</span></div>${bar(recs.length ? (decided / recs.length) * 100 : 0, "good")}</div>
        <button class="btn" data-goto="document">Preview revised CV</button>
      </div>
      <p class="small muted">Accepting a suggestion changes the revised CV only. Your original file is never modified, and every change can be undone.</p>
    </div>
    ${open.length ? `<section class="stack"><div class="spread"><h2>Answer these first</h2><span class="faint">Your answers turn [placeholders] into real, specific lines</span></div>${open.map(questionCard).join("")}</section>` : ""}
    ${closed.length ? `<details class="card flat"><summary style="cursor:pointer"><b>${plural(closed.length, "answered question")}</b></summary>
        <ul class="clean-list" style="margin-top:8px">${closed.map((question) => `<li class="small">${badge(RESOLUTION_LABELS[question.resolution_type] || question.resolution_type)} ${esc(question.primary_question)}${question.synthesized_rewrite ? `<div class="faint">${esc(question.synthesized_rewrite)}</div>` : ""}</li>`).join("")}</ul></details>` : ""}
    <section class="stack">
      <div class="spread"><h2>Suggested edits</h2><div class="chips">${filters}</div></div>
      ${visible.map(recCard).join("") || emptyState(state.editFilter === "pending" ? "Everything has been reviewed. Preview the revised CV or reassess it." : "Nothing in this list.")}
    </section>
  </div>`;
}

async function decide(recId, decision, editedText = "") {
  try {
    state.session = await postJSON(`/api/sessions/${state.session.session_id}/recommendations/${encodeURIComponent(recId)}`, { decision, edited_text: editedText });
    state.editingRec = null;
    refreshView();
    toast(DECISION_TOASTS[decision] || "Updated.");
  } catch (error) {
    toast(error.message, "error");
  }
}

async function answerQuestion(questionId, resolution, text) {
  if (resolution === "answered" && !text.trim()) {
    toast("Type an answer first, or choose 'I don't know'.");
    return;
  }
  try {
    state.session = await postJSON(`/api/sessions/${state.session.session_id}/questions/${encodeURIComponent(questionId)}`, { resolution, answer: text });
    refreshView();
    toast(resolution === "answered" ? "Answer used. Check the updated suggestion below." : "Noted. No facts were invented.");
  } catch (error) {
    toast(error.message, "error");
  }
}

function handleEditsClick(event) {
  const filter = event.target.closest("[data-filter]");
  if (filter) {
    state.editFilter = filter.dataset.filter;
    refreshView();
    return true;
  }
  const question = event.target.closest("[data-question]");
  const resolution = event.target.closest("[data-resolution]");
  if (question && resolution) {
    answerQuestion(question.dataset.question, resolution.dataset.resolution, $("[data-answer]", question).value);
    return true;
  }
  const card = event.target.closest("[data-rec]");
  if (!card) return false;
  const recId = card.dataset.rec;
  if (event.target.closest("[data-edit]")) {
    state.editingRec = recId;
    refreshView();
  } else if (event.target.closest("[data-cancel-edit]")) {
    state.editingRec = null;
    refreshView();
  } else if (event.target.closest("[data-save-edit]")) {
    const text = $("[data-edit-text]", card).value.trim();
    if (!text) {
      toast("The edited text is empty. Use Reject to keep the original.");
      return true;
    }
    decide(recId, "accept", text);
  } else if (event.target.closest("[data-use-alt]")) {
    const rec = currentReport().recommendations.find((item) => item.rec_id === recId);
    if (rec && rec.alternative_text) decide(recId, "accept", rec.alternative_text);
  } else {
    const decision = event.target.closest("[data-decision]");
    if (decision) decide(recId, decision.dataset.decision);
  }
  return true;
}
