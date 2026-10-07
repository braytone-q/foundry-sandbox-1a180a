# VS Code for the Web - Microsoft Foundry

We've generated a simple development environment for you to play with sample code to create and run the agent that you built in the Microsoft Foundry playground.

The Microsoft Foundry extension provides tools to help you build, test, and deploy AI models and AI Applications directly from VS Code. It offers simplified operations for interacting with your models, agents, and threads without leaving your development environment. Click on the Microsoft Foundry Icon on the left to see more.

Follow the instructions below to get started!

## Open the terminal

Press ``Ctrl-` `` &nbsp; to open a terminal window.

## Run your agent locally

To run the agent that you created in AI Foundry, and view the output in the terminal run the following command:

```bash
python run_agent.py
```

## Update your agent configuration

In the left hand activity bar:

- Open the Microsoft Foundry tab in the navigation bar
- Under "Resources", expand the "Agents" section and click on the corresponding agent name
- Click "Open YAML File"
- Make any changes to the agent definition
- Update the agent in Microsoft Foundry

## Add, provision and deploy web app that uses the agent

To add a web app that uses your agent, run the next command. When asked what you would like to do with the files, we suggest selecting `Overwrite with versions from template`.

```bash
azd init -t https://github.com/Azure-Samples/get-started-with-ai-agents
```

You can provision and deploy this web app using:

```bash
azd up
```

To delete the web app and stop incurring any charges, run:

```bash
azd down
```

## Continuing on your local desktop

You can keep working locally on VS Code Desktop by clicking "Continue On Desktop..." at the bottom left of this screen. Be sure to take the .env file with you using these steps:

- Right-click the .env file
- Select "Download"
- Move the file from your Downloads folder to the local git repo directory
- For Windows, you will need to rename the file back to .env using right-click "Rename..."

## More examples

Check out [Azure AI Projects client library for Python](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/README.md) for more information on using this SDK.

## Troubleshooting

- If you are instantiating your client via endpoint on an Microsoft Foundry project, ensure the endpoint is set in the `run_agent` script as `https://{your-foundry-resource-name}.services.ai.azure.com/api/projects/{your-foundry-project-name}`

## Local API and human review prototype

The browser interface runs on this computer and uses the live `regen` Foundry
agent, pinned to version `11`. Source descriptions, analysis attempts, and named
human review events are stored in `runtime/regen.sqlite3`.

Install and launch from this project directory:

```bash
python3 -m venv .venv  # only if the environment does not already exist
.venv/bin/python -m pip install -r requirements-api.txt
export PATH="$PWD/.venv/azure-cli/bin:$PATH"
export AZURE_CONFIG_DIR="$PWD/.venv/azure-config"
az login --tenant 4fdb2788-8d68-473f-8248-de04e7e24cd9
bash run_api.sh
```

Use browser sign-in, including your tenant's MFA prompts. Skip login while your
existing session is valid. If using a system Azure CLI instead of the separate
installation, use its existing `AZURE_CONFIG_DIR`. The launch script automatically
uses the separate CLI/cache when available and respects an explicit cache path.

Open [the local interface](http://127.0.0.1:8000),
[API documentation](http://127.0.0.1:8000/docs), or
[OpenAPI schema](http://127.0.0.1:8000/openapi.json).
Stop the server with Ctrl+C. Run one process without reload: startup recovery
marks unfinished analysis attempts as interrupted. Start it again to continue
with the same saved records. A second process on the same database is unsupported.

Submit a complete activity description. The saved record shows the original
source, AI recommendation, missing information, questions, and reported evidence.
The MVP accepts text and up to 20 JPEG, PNG or WebP images per activity.
Reporting a photo without uploading it does not supply evidence. Completed
analysis records list the images actually supplied in `evidence_received`.
A failed Azure call still returns
the saved record and a safe failure message; its Retry Analysis action adds an
attempt without changing the source. A description update saves a full replacement
revision and preserves older source, analysis, and review history.

A local operator records human actions with a reviewer name and notes, then
confirms Approve, Reject, or Request Clarification. The name is asserted by the
operator; there are no user accounts or verified reviewer identities yet. AI
recommendations never make these decisions or award points, tokens, or payments.
Approve and reject are final in this prototype. A review needs the latest
successful analysis of the current revision, and every mutation uses the viewed
record version to prevent conflicting actions. A conflict refreshes the record
for inspection instead of repeating the decision automatically.

Example API requests (these make live analysis calls):

```bash
curl http://127.0.0.1:8000/api/health
curl 'http://127.0.0.1:8000/api/submissions?status=ALL&limit=25&offset=0'
```

The returned `id` identifies the record. Send its current integer `version` as
`expected_version` when calling `/api/submissions/{id}/analyze`, `/revisions`, or
`/reviews`. Review bodies also contain `action`, `reviewer_name`, and `notes`;
Create and revision bodies require `device_location` as well as the complete
`description`; see the current coordinate schema below. OpenAPI includes all
request and response schemas. Analysis is synchronous, with a 90-second SDK
request timeout and no automatic SDK retries; credential acquisition can add time.
`/api/health` checks local readiness and does not test Azure connectivity.

Settings are environment variables: `REGEN_PROJECT_ENDPOINT`, `REGEN_AGENT_NAME`,
`REGEN_AGENT_VERSION`, `REGEN_DATABASE_PATH`, `REGEN_REQUEST_TIMEOUT_SECONDS`
(positive and at most 600), and `REGEN_PORT` (launch port, default 8000).
Keep the existing working agent and Search setup unless deliberately testing a
new version. Runtime records contain submitted text and are excluded from Git;
back up both the SQLite file and its sibling `evidence/` directory with the
server stopped. The originals and image associations must be restored together.

This is a trusted single-operator local prototype. Keep the loopback binding.
Shared hosting, authenticated submitter/verifier roles, rewards,
reopening final reviews, and cloud deployment belong to later phases.

Offline verification:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
node --check regen_api/static/app.js
bash -n run_api.sh
```

Tests use real temporary SQLite databases and replace only the external Foundry
boundary. For controlled browser QA, run
`.venv/bin/python -m uvicorn tests.browser_fixture:create_app --factory --host 127.0.0.1 --port 8001`.
Only that test fixture uses controlled results (`QA clarification` / `QA failure`
in its descriptions). Production never falls back to demo analysis. The API explicitly requires a tool
call and validates a successful Search result before accepting an analysis; see
[Microsoft’s Search tool example](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/ai-search).
The existing CLI uses automatic tool choice and can occasionally omit retrieval;
the API records such a response as a failed attempt rather than accepting it.

## Image evidence MVP

Choose images below the description, inspect the previews, and remove unwanted
files before submitting. The limit is 20 saved images per activity, 8 MiB per
file, 32 million decoded pixels and 16,000 pixels on either side. JPEG, PNG and
WebP must be valid and non-animated. The server verifies actual contents rather
than trusting filenames or browser MIME labels. A whole invalid batch is rejected.
The total multipart body limit is 161 MiB.

Source revisions retain earlier images and may append more up to the combined
20-image limit. Saved originals cannot be removed or replaced in this MVP. Open
a gallery image to inspect its original; revision and analysis history show the
images associated with that event. Text-only revisions and analysis retries use
the same saved image set. Failed analysis keeps the source and images for retry.

Original bytes are stored under generated names in `runtime/evidence/`, next to
the SQLite database (or next to `REGEN_DATABASE_PATH`). Records include verified
MIME type, size, dimensions, SHA-256 and upload time. Smaller, oriented JPEG copies
with a maximum 1,600-pixel edge and no EXIF metadata are sent to the existing
Foundry agent. Originals remain unchanged for human reviewers.

The AI can describe visible content, but photographs alone do not authenticate
the claimed date, place, species or exact quantity. Image receipts mean supplied
to a completed analysis, not authenticated or approved. Approved Search rules
still govern recommendations, and a person must make the review decision.

Image routes use multipart forms (do not manually set the multipart boundary).
`device-fix.json` must contain a fresh fix from the client device, as documented
below; use the browser interface for automatic capture:

```bash
curl -X POST http://127.0.0.1:8000/api/submissions/with-images \
  -F 'description=Describe the actual work and the supplied photographs.' \
  -F 'device_location=<device-fix.json' \
  -F 'images=@photo-1.jpg' -F 'images=@photo-2.png'
# Append files in a new revision, using the current saved version:
curl -X POST http://127.0.0.1:8000/api/submissions/SUBMISSION_ID/revisions/with-images \
  -F 'description=Complete updated account.' -F 'expected_version=2' \
  -F 'device_location=<device-fix.json' \
  -F 'images=@photo-3.webp'
```

Repeat `images` for each file. Originals are served by `GET /api/images/{id}`.
Existing JSON create, revision, retry and human-review routes remain available.
Runtime image data is excluded from Git along with the database. Keep this
prototype bound to loopback and use it on a trusted computer.

## Image consistency and required device coordinates

The app first inspects actual pixels with the existing `gpt-5-mini` deployment.
Every supplied image gets a visible-content summary and a comparison with the
reported activity: SUPPORTS, UNRELATED, CONTRADICTS or UNCLEAR. These observations
then go to agent `regen`11 for approved Search rule checks. An unrelated or
contradicting image gives MISMATCH; unclear evidence gives INCONCLUSIVE. Both force
FLAG_FOR_REVIEW even if the rule-checking output suggests readiness. A recruitment
poster containing trees is still a poster, not proof of the reported planting
event. The displayed activity type and quantity are explicitly reported claims.

Each analysis attempt preserves its own inspection. Old attempts have no new
inspection result; Retry Analysis applies the new pipeline to the same source
and originals. Visual support does not authenticate date, exact counts, identity
or activity site. A human still decides whether to approve or reject. Inspection
or Search failure saves a failed attempt and keeps evidence available for retry.

The browser automatically requests a fresh device location when saving a new
activity or revision. Allow the site's location permission and enable device
location services. Permission denial, missing support, failure or timeout blocks
submission and preserves the draft. Capture uses high accuracy and no cached fix.
The app also stops waiting for an unanswered permission prompt after 20 seconds.
Use localhost here; shared hosting would need a secure HTTPS context.

JSON create/revision bodies require this additional object; multipart uses the
JSON object as the `device_location` text field:

```json
{
  "latitude": -1.234567,
  "longitude": 36.234567,
  "accuracy_m": 12.0,
  "captured_at": "FRESH_DEVICE_FIX_ISO_TIMESTAMP_WITH_TIMEZONE",
  "source": "browser_geolocation"
}
```

Values above are illustrative placeholders. API clients must acquire their own
fresh device fix. Latitude and longitude must be finite numbers within [-90,90]
and [-180,180], accuracy must be nonnegative, and capture time must be timezone
aware, no more than five minutes old or 30 seconds in the future.

Device coordinates, reported accuracy and capture time are stored by source
revision and displayed separately from the reported activity location. Retries
reuse that snapshot. Historic submissions retain missing coordinates rather than
inventing a retrospective location. Precise device coordinates stay in local
storage and are not sent to Foundry. Browser-provided coordinates are not attested
proof of where an image was taken or an activity occurred.

`REGEN_IMAGE_MODEL` selects the vision deployment (default `gpt-5-mini`). The two
model calls may take longer than the previous single call; the SDK request timeout
applies to each call. Keep one server process on the local database.

## General questions and Ask Re-gen

Open `http://127.0.0.1:8000/#ask`, or select **Ask Re-gen** in the sidebar.
Ask everyday questions, conservation questions, or questions about the programme,
then follow up in the same conversation. Questions do not create activity records,
request device location, inspect stored images, or make human review decisions.
Use **Submit Activity** to supply work and images for an assessment.

Questions also receive a fresh, read-only database summary of total submissions,
pending human review, clarification requested, approved, rejected and the active
Review Queue total. Pending human review means `PENDING_REVIEW`; the default
active queue also includes `CLARIFICATION_REQUESTED`. The snapshot is timestamped
and refreshed for each question, including follow-ups. Counts do not come from
programme Search or old chat answers. Individual source descriptions, reviewer
notes, images and device coordinates are not included in the summary. A failed
database read returns a sanitized storage error before any model call.

Ask Re-gen also receives a maintained briefing of the implemented project:
its purpose, navigation screens, submission/review workflow, pixel inspection,
image limits, required location capture, storage and current local-only scope.
It combines those application facts with the verification agent's approved
Search knowledge when answering project questions and follow-ups. The briefing
does not define new programme requirements; undocumented project facts must be
acknowledged instead of invented. Update the briefing in `regen_api/questions.py`
when implemented capabilities change.

The question path uses the existing Foundry deployment directly with a separate
instruction set. A typed first response distinguishes everyday questions,
application facts and programme-policy questions. Application answers use the
maintained briefing without unrelated rule citations. Programme and mixed
questions and their relevant follow-ups retrieve fresh approved
Re-gen Search knowledge. Retrieved programme rules govern policy answers; ordinary
advice is general knowledge and must not be represented as programme policy.
It cannot check live news, weather or other current facts with this configuration.
It cannot approve, reject, verify or reward activities. The verification agent
`regen`11 and its structured analysis contract remain separate.

```bash
curl http://127.0.0.1:8000/api/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the capital of Kenya?"}'
# Follow up with complete user/assistant pairs from the previous answer:
curl http://127.0.0.1:8000/api/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"And what is its country?","history":[{"role":"user","content":"What is the capital of Kenya?"},{"role":"assistant","content":"Nairobi."}]}'
```

Successful answers contain `answer`, `response_id`, `citations` and
`knowledge_searched` (false for general knowledge or project-briefing answers,
true when approved Search retrieval occurred).
The opt-in live project checks make model calls against the running app:
`.venv/bin/python -m pytest -q -s tests/live_project_questions.py`.
Missing required Search, incomplete or invalid answers, authentication
and provider failures return a sanitized502 error. No question or activity is
written to SQLite. The browser retains a failed question draft for retry.

A question can have up to4,000 characters. Context accepts up to12 messages in
complete alternating user/assistant pairs, each up to12,000 characters and
24,000 characters in total. The interface sends the newest complete pairs that
fit those limits. Conversation and draft persist across navigation in this page
session; **New conversation** or a reload clears them. Question text, recent
context and aggregate review counts are sent to the configured Foundry service; provider-side retention is
separate from the browser's temporary history. Images and coordinates are not
included automatically.

`REGEN_QUESTION_MODEL` selects the question deployment (default `gpt-5-mini`).
`REGEN_SEARCH_CONNECTION_NAME` and `REGEN_SEARCH_INDEX_NAME` select approved
knowledge for questions (defaults `regen-verification-search-mi` and
`regen-verification-index`). Use the configured approved source consistently.
