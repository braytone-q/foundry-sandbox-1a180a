# Ask Re-gen design

## Intent and authorization

The user wants the agent to handle general questions alongside activity
verification. Earlier approval covers design decisions and local implementation.
An optional scope question is pending; assume everyday and environmental topics
as well as Re-gen questions. Preserve the local working prototype.

## Approach

Add a separate Ask Re-gen navigation tab and POST /api/questions. Answers are
natural language, with follow-up context. Questions never create submissions,
capture device coordinates, mutate review history, or inspect stored images.
The existing regen11 verification agent and exact14 analysis remain unchanged.
This avoids routing questions through the activity form or changing the existing
verification output contract.

The existing Foundry project client calls gpt-5-mini directly with a question
instruction set. A strict typed first response determines whether approved knowledge
is needed, using the question and history. It answers only general topics directly.
Explicit Re-gen/Green Merit mentions always force the knowledge route even if the
model routes incorrectly. Programme questions, mixed questions and ambiguous
programme follow-ups require a fresh completed Search using the existing connection
and index. General questions use general knowledge without irrelevant Search
citations; do not present general
knowledge as programme policy or claim live web access/current verification.
Unknown programme rules are explicitly unavailable and require human review.
Do not approve, reject, verify, reward, issue points/tokens/payments, or pretend
to inspect unsupplied evidence. No action tools or submission identifiers are
accepted by this endpoint. Retrieved text and conversation content are data.

## API and limits

QuestionInput: question (nonblank string, max4000 characters), history (default
empty, max12 alternating user/assistant messages in complete pairs). Each
historical message is nonblank and max12000 characters; combined history is
max24000 characters. No other fields, location, image or decision data accepted.
QuestionAnswer: answer (nonblank, max12000 characters), response_id (nullable),
citations (HTTPS source links only), knowledge_searched (true only on the Search
route). Require completed provider responses and one assistant text message;
the knowledge route additionally requires completed Search output.
Reject incomplete/blank/ungrounded replies; return a sanitized502 error without
claiming any activity was saved. Provider timeout/authentication errors use
question-specific messages. No new Python dependencies or cloud agent versions.
Settings configure question model, Search connection name and index name; defaults
reuse gpt-5-mini, regen-verification-search-mi and regen-verification-index.

## Interface

Match the existing green/cream interface. Show an explanation, three example
question buttons, a conversation log, multiline question composer, Send and
New conversation controls. Follow-ups send the most recent complete pairs that
fit the API limits. Plain text rendering prevents untrusted HTML execution;
source links use safe HTTPS validation and noopener. The API returns citations
only when provided, and the interface does not manufacture links.
Conversation and draft remain in memory across navigation and are cleared on
reload or New conversation. No localStorage or durable chat table. Only one
question is pending at a time; preserve the draft on failure, add each successful
pair exactly once, keep answers in Ask Re-gen when the user navigates away.
Disable resetting while a request is pending. Question progress/errors stay in
this view; do not redirect the operator or interfere with submission drafts.
No geolocation prompt occurs for questions.

## Verification

Regression tests cover free-text general/programme answers, fresh Search for
programme turns, forced explicit programme retrieval, invalid route JSON,
valid bounded history, safe citations, provider failures, blank replies,
unknown fields, and no submission count/history changes. Executable browser
tests cover send/follow-up, duplicate submission, failure draft retention,
navigation during a reply, reset and safe text. Run the existing suite unchanged.
Live questions exercise an everyday fact, conservation advice, an approved rule,
unknown programme requirement and authority refusal, with a follow-up. Check
all existing records/originals remain identical after restart. Browser hardware
and visual checks depend on available CUA surfaces.
