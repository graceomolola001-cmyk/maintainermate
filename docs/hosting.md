# Alternative: host the Python app on Render

For Netlify instead, follow [the Netlify guide](netlify.md); it does not require Render.

This alternative uses **Render for FastAPI** and **Groq for AI responses**. The visitor only needs a browser. Your laptop and Ollama do not need to stay on. Local development still defaults to Ollama.

The repository explicitly selects Render's **free** web-service plan. Use a Groq **free-tier** account, keep paid billing disabled, and confirm the current model/quotas in its console. Free-plan availability and signup requirements can change; stop if either service asks you to purchase an upgrade. No code here creates a paid resource or changes billing settings.

## Deploy

1. Create/sign in to https://console.groq.com. Under **API Keys**, create a server API key. Keep it private; do not paste it in chat, source files, screenshots, or the browser interface. Check that `llama-3.1-8b-instant` is supported by your account; otherwise choose an available model in the same free tier and set `GROQ_MODEL` to its exact ID.
2. Create/sign in to https://dashboard.render.com and connect the GitHub repository `graceomolola001-cmyk/maintainermate`.
3. Open https://render.com/deploy?repo=https://github.com/graceomolola001-cmyk/maintainermate . This reads `render.yaml` from `main`. Confirm the service plan says **Free**.
4. Enter the key in Render's secure **GROQ_API_KEY** environment-variable field when prompted. Leave `AI_PROVIDER=groq`, `PUBLIC_MODE=true`, and `MOCK_AI=false`. The key stays on the server and is not included in frontend assets.
5. Deploy. Render will give you an HTTPS URL. Use the actual URL it assigns; this repository does not reserve one or prove that a deployment exists.
6. Open that URL in a private browser window. Generate a plan from the sample, then paste a different issue and verify you get an appropriate new response. The result should identify **Groq** and the configured model, with no `DEMO ONLY` label. Try copying and downloading it.

If you prefer manual setup, create a **Web Service** from the repository with these settings:

| Setting | Value |
|---|---|
| Branch | `main` |
| Runtime | Python |
| Instance type | **Free** |
| Build command | `python -m pip install -r requirements.txt` |
| Start command | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 32 --no-access-log` |
| Health check path | `/ready` |
| Environment variables | Copy the non-secret names/values from `render.yaml`; enter your key only in Render's environment settings. |

Do not use the old Ollama/Hugging Face deployment branch for this lightweight version. The default branch does not download or run a model on the hosting server.

## What each check means

- `/ready` returns 200 when the configured provider and required key are present. It does **not** test key validity, connectivity, remaining quota, or model availability.
- `/health` reports `api_configured` for Groq when a nonempty server key is present, or `api_key_missing` otherwise. It makes no model request and never returns the key.
- A successful `/api/analyze` request is the actual live-inference check. A successful build or health probe alone is insufficient.
- Tests use simulated provider responses. They do not establish that your account, credentials, or live deployment work.

## Limits that keep the demo small

- One generation at a time, with a shared minimum 30 seconds between starts.
- At most 100 admitted requests per UTC day per running process, including attempts that later fail. This counter resets on process restart and is not a billing control; keep the provider account on its free plan.
- A 32 KiB request-body limit and the existing 6000-character issue limit.
- The client cannot select a model other than the server's configured `GROQ_MODEL`.
- Each request asks for at most 750 output tokens. The app does not retry model requests automatically. Provider limits can reject requests before the app's own limits are reached.
- Use one server worker. These limits are in memory and are not shared between multiple workers or service instances.

Free Render services may sleep when unused and take time to wake up. Groq has model-specific request/token quotas. There is no always-on or unlimited-usage guarantee. Check current terms at https://render.com/docs/free and https://console.groq.com/docs/rate-limits before relying on the app.

## Privacy

In hosted mode, issue text is sent to your server and to Groq for inference. Public URL mode also contacts `api.github.com`. Do not enter private documents, tokens, or other sensitive information. The app does not persist prompts, and access logs are disabled by the deployment command. Hosting and AI-provider policies still apply; review https://console.groq.com/docs/your-data .

This is a small public portfolio app without user accounts. Its limits are not distributed denial-of-service protection. Production or sensitive deployments need additional controls.

## Run the hosted provider from PowerShell

Create the normal project virtual environment first. Set `GROQ_API_KEY` through your process's secure environment configuration. The app intentionally does not auto-load `.env` files. Never put the key in a command you plan to share or commit.

```powershell
$env:AI_PROVIDER = 'groq'
$env:GROQ_MODEL = 'llama-3.1-8b-instant'
$env:MOCK_AI = 'false'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For local Ollama instead, set `$env:AI_PROVIDER = 'ollama'` and use the original README commands. No Groq key is needed in that mode. For a fixed sample without either provider, set `MOCK_AI=true`; that mode is explicitly labelled and is not real inference.

## Troubleshooting

| Symptom | Action |
|---|---|
| Render health check fails | Verify `AI_PROVIDER=groq`, `GROQ_API_KEY` is set, and the model ID is valid. No key should appear in logs. |
| Credentials need attention | Replace the key securely in Render's environment settings and redeploy. Never paste the rejected key in an issue. |
| Model/account unavailable | Check the current free-tier model list and account restrictions in Groq; update `GROQ_MODEL` if necessary. |
| HTTP 429 | The app or provider has reached a limit. Wait for the retry period; do not switch to a paid plan automatically. |
| Provider unreachable/timeouts | Check provider status and outbound HTTPS access to `api.groq.com`. |
| Site wakes slowly | Allow the free hosting service time to start. This is separate from model generation time. |
