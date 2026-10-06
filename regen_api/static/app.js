"use strict";
const $ = (selector) => document.querySelector(selector);
const labels = {
  PENDING_REVIEW: "Pending human review", CLARIFICATION_REQUESTED: "Human requested clarification",
  APPROVED: "Approved by human", REJECTED: "Rejected by human",
  READY_FOR_HUMAN_REVIEW: "Ready for human review", NEEDS_CLARIFICATION: "Needs clarification",
  FLAG_FOR_REVIEW: "Flag for review", RUNNING: "Analysis running", FAILED: "Analysis failed",
  SUCCEEDED: "Analysis complete", APPROVE: "Approve", REJECT: "Reject", REQUEST_CLARIFICATION: "Request clarification"
};
let current = null, pendingReview = null, busy = false, offset = 0, total = 0, routeSequence = 0;
const pageSize = 25;

// All record content is untrusted. Build elements and assign text, never HTML.
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}
function date(value) { return value ? new Date(value).toLocaleString() : "—"; }
function badge(value) {
  const tone = ["APPROVED", "READY_FOR_HUMAN_REVIEW", "SUCCEEDED"].includes(value) ? "green" :
    ["REJECTED", "FAILED"].includes(value) ? "red" :
    ["CLARIFICATION_REQUESTED", "NEEDS_CLARIFICATION", "FLAG_FOR_REVIEW"].includes(value) ? "amber" : "neutral";
  return node("span", labels[value] || value, `tag ${tone}`);
}
function statusPair(record) {
  const pair = node("div", null, "status-pair");
  const human = node("div"); human.append(node("span", "HUMAN STATUS", "status-label"), badge(record.review_status));
  const ai = node("div"); ai.append(node("span", "AI RECOMMENDATION", "status-label"),
    badge(record.latest_attempt?.analysis?.recommendation || record.latest_attempt?.state || "No analysis"));
  pair.append(human, ai); return pair;
}
function notice(message, error = false) {
  const target = $("#notice"); target.textContent = message; target.className = `notice${error ? " error" : ""}`;
  target.hidden = !message;
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll("fieldset").forEach((field) => { field.disabled = value || field.dataset.blocked === "true"; });
  $("#confirm-review").disabled = value;
  $("#cancel-review").disabled = value;
}
async function api(path, body) {
  const options = body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)};
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error("The server could not be reached. Refresh to check whether your activity or review was saved before trying again."); }
  let data;
  try { data = await response.json(); }
  catch { throw new Error("The server returned an unreadable response. Refresh to check the saved record."); }
  if (!response.ok) {
    const message = typeof data.detail === "string" ? data.detail : "Check the required fields and text limits, then try again.";
    const error = new Error(message); error.status = response.status; throw error;
  }
  return data;
}
function path(id = current?.id) { return `/api/submissions/${encodeURIComponent(id)}`; }
function empty(title, text) {
  const box = node("div", null, "empty-state"); box.append(node("h2", title), node("p", text)); return box;
}
function list(values) {
  const ul = node("ul", null, "text-list"); values.forEach((value) => ul.append(node("li", value))); return ul;
}
function card(title, kicker) {
  const box = node("section", null, "card");
  if (kicker) box.append(node("p", kicker, "card-kicker"));
  box.append(node("h2", title)); return box;
}
function button(text, action, className = "secondary") {
  const result = node("button", text, className); result.type = "button"; result.addEventListener("click", action); return result;
}
function field(label, id, tag = "input", maxLength) {
  const wrapper = node("div"), labelNode = node("label", label), input = node(tag);
  labelNode.htmlFor = id; input.id = id; input.required = true;
  if (maxLength) input.maxLength = maxLength;
  wrapper.append(labelNode, input); return wrapper;
}
function showDetail(id) { location.hash = `submission/${encodeURIComponent(id)}`; }

async function renderRoute() {
  // A confirmation belongs to the viewed record, never to a later navigation.
  pendingReview = null;
  if ($("#review-dialog").open) $("#review-dialog").close();
  const sequence = ++routeSequence;
  const hash = location.hash.slice(1) || "submit";
  const view = hash.startsWith("submission/") ? "detail" : hash === "history" ? "history" : hash === "queue" ? "queue" : "submit";
  document.querySelectorAll(".view").forEach((element) => { element.hidden = true; });
  $(view === "history" ? "#queue-view" : `#${view}-view`).hidden = false;
  document.querySelectorAll("[data-nav]").forEach((link) => {
    const active = link.dataset.nav === (view === "detail" ? "queue" : view);
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  if (view === "detail") {
    current = null;
    $("#detail-content").replaceChildren(empty("Loading activity…", "Fetching the source record and review history."));
    try {
      const record = await api(path(decodeURIComponent(hash.slice(11))));
      if (sequence !== routeSequence) return;
      current = record; renderDetail();
    } catch (error) { if (sequence === routeSequence) $("#detail-content").replaceChildren(empty("Activity unavailable", error.message)); }
  } else if (view === "queue" || view === "history") {
    offset = 0;
    $("#status-filter").value = view === "history" ? "ALL" : "";
    $("#queue-title").textContent = view === "history" ? "Activity history" : "Review queue";
    $("#queue-eyebrow").textContent = view === "history" ? "A RECORD OF THE WORK" : "A HUMAN PERSPECTIVE";
    $("#queue-description").textContent = view === "history" ? "Revisit sources, analyses and named human decisions." : "Take a closer look at the work on the ground.";
    await loadQueue(sequence);
  }
}

async function loadQueue(sequence = routeSequence) {
  $("#queue-list").replaceChildren(empty("Loading activities…", "Fetching the latest local records."));
  $("#previous-page").disabled = true; $("#next-page").disabled = true;
  const params = new URLSearchParams({limit: pageSize, offset});
  for (const [parameter, selector] of [["status", "#status-filter"], ["recommendation", "#recommendation-filter"], ["analysis_state", "#state-filter"]]) {
    if ($(selector).value) params.set(parameter, $(selector).value);
  }
  try {
    const page = await api(`/api/submissions?${params}`);
    if (sequence !== routeSequence) return;
    total = page.total;
    $("#queue-total").textContent = total.toLocaleString();
    $("#queue-total-label").textContent = $("#status-filter").value === "" ? "activities awaiting review" : "matching activities";
    const entries = page.items.map((record) => {
      const entry = node("a", null, "queue-item"); entry.href = `#submission/${record.id}`;
      const top = node("div", null, "queue-item-top"), title = node("div");
      title.append(node("h2", titleFor(record)), node("span", `Revision ${record.current_revision} · ${record.id.slice(0, 8)}`, "card-kicker"));
      top.append(title, statusPair(record));
      const meta = node("div", null, "item-meta");
      meta.append(node("span", `Submitted ${date(record.created_at)}`), node("span", `${record.attempts.length} analysis attempt${record.attempts.length === 1 ? "" : "s"}`));
      entry.append(top, node("p", record.description.slice(0, 230) + (record.description.length > 230 ? "…" : ""), "excerpt"), meta);
      return entry;
    });
    $("#queue-list").replaceChildren(...(entries.length ? entries : [empty("No activities here yet", "Submit an activity or adjust your filters to see more records.")]));
    $("#page-label").textContent = total ? `${offset + 1}–${Math.min(offset + pageSize, total)} of ${total}` : "0 activities";
    $("#previous-page").disabled = offset === 0;
    $("#next-page").disabled = offset + pageSize >= total;
  } catch (error) { if (sequence === routeSequence) $("#queue-list").replaceChildren(empty("Could not load activities", error.message)); }
}
function titleFor(record) {
  const activity = record.latest_attempt?.analysis?.activity_type;
  return activity ? activity.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase()) : "Conservation activity";
}

function renderDetail() {
  const record = current, attempt = record.latest_attempt, analysis = attempt?.analysis;
  const container = $("#detail-content"); container.replaceChildren();
  const back = node("a", "← Back to review queue", "back-link"); back.href = "#queue"; container.append(back);
  const heading = node("div", null, "detail-heading"), text = node("div");
  text.append(node("p", "THE ACTIVITY RECORD", "eyebrow"), node("h1", titleFor(record)), statusPair(record),
    node("p", `Revision ${record.current_revision} · Updated ${date(record.updated_at)} · ${record.id.slice(0, 8)}`, "detail-meta"));
  heading.append(text, button("Refresh record ↻", refresh)); container.append(heading);
  const layout = node("div", null, "detail-layout"), main = node("div", null, "detail-main"), side = node("div", null, "detail-side");
  const source = card("The activity, in their words", `SOURCE DESCRIPTION · REVISION ${record.current_revision}`);
  source.append(node("p", record.description, "source-text")); main.append(source);
  const ai = card("AI analysis", attempt ? `FOUNDRY AGENT ${attempt.agent_name} · VERSION ${attempt.agent_version}` : "NO ATTEMPT");
  if (analysis) {
    ai.append(badge(analysis.recommendation));
    const facts = node("dl", null, "facts");
    for (const [key, label] of [["activity_type", "Activity"], ["quantity", "Quantity"], ["species", "Species"], ["species_category", "Species category"], ["activity_date", "Activity date as reported"], ["location", "Location"], ["community_group", "Community group"]]) {
      const fact = node("div"); fact.append(node("dt", label), node("dd", analysis[key] ?? "Not stated")); facts.append(fact);
    }
    ai.append(facts, node("h3", "Why this recommendation"), node("p", analysis.reason, "reason"));
    for (const [values, label] of [[analysis.missing_information, "Missing information"], [analysis.inconsistencies, "Inconsistencies"]]) {
      if (values.length) { const findings = node("div", null, "finding"); findings.append(node("h3", label), list(values)); ai.append(findings); }
    }
    if (analysis.clarification_question) { const question = node("div", null, "finding"); question.append(node("h3", "AI clarification question"), node("p", analysis.clarification_question)); ai.append(question); }
    const evidence = node("div", null, "evidence-grid");
    for (const [values, label, fallback] of [[analysis.evidence_reported, "Evidence reported", "No evidence reported."], [analysis.evidence_received, "Evidence received", "None. This prototype accepts text only."]]) {
      const part = node("div"); part.append(node("h3", label), values.length ? list(values) : node("p", fallback)); evidence.append(part);
    }
    ai.append(evidence);
    if (attempt.citations.length) {
      const sources = node("ul", null, "source-links");
      for (const citation of attempt.citations) {
        try {
          const url = new URL(citation.url);
          if (url.protocol !== "https:" || !url.hostname || url.username || url.password) continue;
          const li = node("li"), link = node("a", citation.title); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
          li.append(link); sources.append(li);
        } catch { /* Omit unsafe source URLs. */ }
      }
      if (sources.childElementCount) ai.append(node("h3", "Retrieved sources"), sources);
    }
    ai.append(node("p", `Analyzed ${date(attempt.finished_at)}. The recommendation does not change human status.`, "field-help"));
  } else {
    const failure = node("div", null, "failure-block"); failure.append(node("h3", labels[attempt?.state] || "No analysis available"),
      node("p", attempt?.failure_message || "Analysis is in progress. Refresh this record to check for completion."));
    if (attempt?.state === "FAILED" && !isFinal(record)) failure.append(button("Retry analysis ↻", () => mutate("analyze", {expected_version: record.version}), "primary"));
    ai.append(failure);
  }
  main.append(ai, historyCard(record));
  side.append(reviewCard(record));
  if (!isFinal(record)) side.append(revisionCard(record));
  layout.append(main, side); container.append(layout);
  setBusy(busy);
}
function isFinal(record) { return ["APPROVED", "REJECTED"].includes(record.review_status); }
function reviewCard(record) {
  const box = card("Your human review", "A PERSON MAKES THIS DECISION");
  if (isFinal(record) || record.latest_attempt?.state !== "SUCCEEDED") {
    box.append(badge(record.review_status), node("p", isFinal(record) ? "This activity has a final human decision. Its source and history remain available below." : "Human review is available after the latest analysis succeeds. Retry a failed analysis or refresh a running one.", "review-explanation"));
    return box;
  }
  const form = node("form", null, "review-form"), fields = node("fieldset");
  fields.append(field("Reviewer name", "reviewer-name", "input", 120), field("Review notes", "review-notes", "textarea", 4000));
  const actions = node("div", null, "review-actions");
  for (const [action, className] of [["APPROVE", "primary"], ["REQUEST_CLARIFICATION", "secondary"], ["REJECT", "secondary"]]) {
    actions.append(button(`${labels[action]} →`, () => {
      if (busy || !form.reportValidity()) return;
      const reviewer = $("#reviewer-name").value.trim(), notes = $("#review-notes").value.trim();
      if (!reviewer || !notes) { notice("Enter a reviewer name and meaningful review notes.", true); return; }
      pendingReview = {action, reviewer_name: reviewer, notes, expected_version: record.version};
      $("#confirm-action").textContent = `Human action: ${labels[action]}`;
      $("#confirm-reviewer").textContent = `Reviewer: ${reviewer}`;
      $("#confirm-notes").textContent = notes;
      $("#review-dialog").showModal();
    }, className));
  }
  form.addEventListener("submit", (event) => event.preventDefault());
  fields.append(actions); form.append(fields);
  box.append(node("p", "Record your own assessment. Your choice is independent of the AI recommendation.", "field-help"), form); return box;
}
function revisionCard(record) {
  const box = card("Update the description", "A NEW SOURCE REVISION");
  box.append(node("p", "Replace the complete description with your updated account. Earlier words and reviews stay in history.", "field-help"));
  const form = node("form", null, "revision-form"), fields = node("fieldset");
  fields.append(field("Complete updated description", "revision-description", "textarea", 16000));
  fields.querySelector("textarea").value = record.description;
  const submit = node("button", "Save revision & analyze ↗", "secondary"); submit.type = "submit";
  fields.append(submit); form.append(fields);
  if (record.latest_attempt?.state === "RUNNING") { fields.dataset.blocked = "true"; fields.disabled = true; box.append(node("p", "Wait for the running analysis before saving a revision.", "field-help")); }
  form.addEventListener("submit", (event) => {
    event.preventDefault(); if (busy) return;
    const description = fields.querySelector("textarea").value;
    if (!description.trim()) { notice("Describe the activity before saving a revision.", true); return; }
    mutate("revisions", {description, expected_version: record.version});
  });
  box.append(form); return box;
}
function historyCard(record) {
  const box = card("Record history", "SOURCES, ANALYSES & HUMAN EVENTS"); box.classList.add("history-card");
  box.append(node("p", "Earlier events are kept for context. Human actions refer to the exact revision and analysis reviewed.", "field-help"));
  for (const [heading, values, render] of [
    ["HUMAN REVIEW EVENTS", record.reviews, (value) => [`${labels[value.action]} · ${value.reviewer_name}`, `Revision ${value.revision} · ${date(value.created_at)}`, value.notes]],
    ["SOURCE REVISIONS", [...record.revisions].reverse(), (value) => [`Source revision ${value.revision}`, date(value.created_at), value.description]],
    ["ANALYSIS ATTEMPTS", record.attempts, (value) => [`${labels[value.state]} · Revision ${value.revision}`, `${date(value.started_at)} · ${value.agent_name} v${value.agent_version}`, value.analysis ? JSON.stringify(value.analysis, null, 2) : value.failure_message || "Analysis running."]]
  ]) {
    box.append(node("p", heading, "history-kind"));
    if (!values.length) box.append(node("p", "No human review events yet.", "field-help"));
    for (const value of values) {
      const [title, timestamp, content] = render(value), entry = node("details"), summary = node("summary", title);
      summary.append(node("small", timestamp)); entry.append(summary, node(heading === "ANALYSIS ATTEMPTS" ? "pre" : "p", content, "source-text")); box.append(entry);
    }
  }
  return box;
}
async function refresh() {
  if (!current || busy) return;
  try { current = await api(path()); renderDetail(); }
  catch (error) { notice(error.message, true); }
}
async function mutate(action, body) {
  if (busy || !current) return;
  const id = current.id;
  setBusy(true); notice(action === "reviews" ? "Saving your human review…" : "Your source is saved before analysis. Checking the approved knowledge source…");
  try {
    const record = await api(`${path(id)}/${action}`, body);
    if (current?.id === id) { current = record; renderDetail(); }
    notice(action === "reviews" ? "Your named human review has been recorded." : record.latest_attempt.state === "FAILED" ? "Your source is saved. Analysis needs attention; see the failure below." : "Analysis complete. The activity is ready for your assessment.");
  } catch (error) {
    if (error.status === 409) {
      try { const record = await api(path(id)); if (current?.id === id) { current = record; renderDetail(); } } catch { /* Keep the conflict visible. */ }
      notice("This record changed. Its latest state has been refreshed where available. Inspect it before taking a new action.", true);
    } else notice(error.message, true);
  } finally { setBusy(false); }
}

$("#submission-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (busy) return;
  const description = $("#description").value;
  if (!description.trim()) { notice("Describe the activity before submitting.", true); return; }
  setBusy(true); notice(""); $("#submit-progress").hidden = false;
  try {
    const record = await api("/api/submissions", {description});
    $("#submission-form").reset(); $("#character-count").textContent = "0 / 16,000";
    showDetail(record.id); notice(record.latest_attempt.state === "FAILED" ? "Your activity is saved. Analysis needs attention; you can retry from its record." : "Your activity and AI analysis are saved. A human decision is still required.");
  } catch (error) { notice(error.message, true); }
  finally { setBusy(false); $("#submit-progress").hidden = true; }
});
$("#description").addEventListener("input", () => { $("#character-count").textContent = `${$("#description").value.length.toLocaleString()} / 16,000`; });
$("#filter-form").addEventListener("submit", (event) => { event.preventDefault(); offset = 0; loadQueue(); });
$("#previous-page").addEventListener("click", () => { offset = Math.max(0, offset - pageSize); loadQueue(); });
$("#next-page").addEventListener("click", () => { if (offset + pageSize < total) { offset += pageSize; loadQueue(); } });
$("#cancel-review").addEventListener("click", () => { pendingReview = null; $("#review-dialog").close(); });
$("#review-dialog").addEventListener("cancel", () => { pendingReview = null; });
$("#confirmation-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (busy || !pendingReview) return;
  const body = pendingReview; pendingReview = null; $("#review-dialog").close(); await mutate("reviews", body);
});
window.addEventListener("hashchange", renderRoute);
renderRoute();
