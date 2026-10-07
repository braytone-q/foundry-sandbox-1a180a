"use strict";

function questionHistory(turns) {
  const history = [];
  let characters = 0;
  for (const turn of turns.slice(-6).reverse()) {
    const size = turn.question.length + turn.answer.length;
    if (characters + size > 24000) break;
    history.unshift({role: "user", content: turn.question}, {role: "assistant", content: turn.answer});
    characters += size;
  }
  return history;
}

class QuestionChat {
  constructor(request) {
    this.request = request;
    this.turns = [];
    this.pending = false;
    this.examples = [];
    for (const question of ["How does Re-gen work?", "What information is required for tree planting?", "Why do trees help the environment?"]) {
      const example = button(question, () => {
        if (this.pending) return;
        $("#question-input").value = question;
        $("#question-input").focus?.();
      });
      this.examples.push(example);
      $("#question-examples").append(example);
    }
    $("#question-form").addEventListener("submit", (event) => {
      event.preventDefault(); return this.send();
    });
    $("#question-reset").addEventListener("click", () => this.reset());
    this.reset();
  }

  status(message, error = false) {
    const progress = $("#question-progress");
    progress.textContent = message;
    progress.className = error ? "notice error" : "progress";
    progress.hidden = !message;
  }

  setPending(value) {
    this.pending = value;
    $("#question-input").disabled = value;
    $("#question-send").disabled = value;
    $("#question-reset").disabled = value;
    this.examples.forEach((example) => { example.disabled = value; });
  }

  reset() {
    if (this.pending) return;
    this.turns = [];
    $("#question-input").value = "";
    $("#question-log").replaceChildren(empty("What would you like to know?", "Ask about Re-gen, conservation, or an everyday topic. You can follow up on an answer."));
    this.status("");
  }

  appendTurn(turn) {
    if (this.turns.length === 1) $("#question-log").replaceChildren();
    const question = node("article", null, "question-message question-user");
    question.append(node("h2", "You"), node("p", turn.question, "question-text"));
    const answer = node("article", null, "question-message question-assistant");
    answer.append(node("h2", "Re-gen"), node("p", turn.answer, "question-text"));
    const sources = node("div", null, "question-sources");
    for (const citation of turn.citations || []) {
      try {
        const url = new URL(citation.url);
        if (url.protocol !== "https:" || url.username || url.password) continue;
        const link = node("a", citation.title || "Retrieved source");
        link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
        sources.append(link);
      } catch { /* Do not render unsafe or malformed source links. */ }
    }
    if (sources.children.length) answer.append(node("p", "Retrieved sources", "field-help"), sources);
    $("#question-log").append(question, answer);
  }

  async send() {
    if (this.pending) return;
    const input = $("#question-input"), draft = input.value, question = draft.trim();
    if (!question || draft.length > 4000) {
      this.status("Enter a question of up to 4,000 characters.", true); return;
    }
    this.setPending(true);
    this.status("Preparing your answer…");
    try {
      const result = await this.request("/api/questions", {question, history: questionHistory(this.turns)});
      const turn = {question, answer: result.answer, citations: result.citations};
      this.turns.push(turn); this.appendTurn(turn);
      if (input.value === draft) input.value = "";
      this.status("");
    } catch (error) {
      this.status(error.message, true);
    } finally {
      this.setPending(false);
    }
  }
}
