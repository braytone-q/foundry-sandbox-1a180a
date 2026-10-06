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
This version accepts text only: reporting an attached photo does not supply a
photo, and `evidence_received` remains empty. A failed Azure call still returns
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
curl -X POST http://127.0.0.1:8000/api/submissions \
  -H 'Content-Type: application/json' \
  -d '{"description":"We watered seedlings in the community nursery today."}'
curl 'http://127.0.0.1:8000/api/submissions?status=ALL&limit=25&offset=0'
```

The returned `id` identifies the record. Send its current integer `version` as
`expected_version` when calling `/api/submissions/{id}/analyze`, `/revisions`, or
`/reviews`. Review bodies also contain `action`, `reviewer_name`, and `notes`;
revision bodies also contain the complete `description`. OpenAPI includes all
request and response schemas. Analysis is synchronous, with a 90-second SDK
request timeout and no automatic SDK retries; credential acquisition can add time.
`/api/health` checks local readiness and does not test Azure connectivity.

Settings are environment variables: `REGEN_PROJECT_ENDPOINT`, `REGEN_AGENT_NAME`,
`REGEN_AGENT_VERSION`, `REGEN_DATABASE_PATH`, `REGEN_REQUEST_TIMEOUT_SECONDS`
(positive and at most 600), and `REGEN_PORT` (launch port, default 8000).
Keep the existing working agent and Search setup unless deliberately testing a
new version. Runtime records contain submitted text and are excluded from Git;
keep a copy of the SQLite file with the server stopped if you need a backup.

This is a trusted single-operator local prototype. Keep the loopback binding.
Shared hosting, authenticated submitter/verifier roles, file uploads, rewards,
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
