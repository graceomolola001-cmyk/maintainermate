# Deploy on Netlify

This version uses **Netlify for the website and its API functions**, plus **Groq for AI responses**. Your laptop can be switched off. The original Python/FastAPI + Ollama app remains available for local use; Render is optional and is not needed for this deployment.

## Launch the website

1. Sign in at https://app.netlify.com/start and choose **Import an existing project → GitHub**. Select `graceomolola001-cmyk/maintainermate`, using branch `main`.
2. Let Netlify read `netlify.toml`. It specifies the build command, publish directory, and functions directory. Use the **Free** plan and review its current credit/function limits. Stop if your account requires a paid upgrade; do not enable paid add-ons or automatic credit purchases to follow this guide.
3. Under the project's **Environment variables**, add `GROQ_API_KEY` with a key from https://console.groq.com/keys . Use the Functions/runtime scope if the dashboard offers scope selection. Never put the value in GitHub, `netlify.toml`, frontend code, screenshots, or chat.
4. Optionally set `GROQ_MODEL` to a model offered by your Groq free-tier account. The default is `llama-3.1-8b-instant`; check its current availability in your console. Keep paid Groq billing disabled.
5. Deploy. If you added the environment variable after deploying, trigger another deployment so the functions receive it.
6. Open the actual HTTPS URL Netlify assigns. Paste an issue or select the sample, then generate a plan. Test again in a private browser window before adding the link to your portfolio.

Use GitHub import so Netlify builds the functions. Uploading only the static files through drag-and-drop does not prepare this backend.

## How to confirm it works

- The page should say **AI powered by Groq** and explain that issue text is sent to Groq.
- `/health` reports `api_configured` when a server key is present, or `api_key_missing` otherwise. It never exposes or validates the key.
- `/ready` checks configuration only. A 200 response is not evidence that the key, model, or remaining quota works.
- Generate an actual plan. The result should identify Groq and the configured model, with no `DEMO ONLY` label. Try a different issue and verify the response addresses it.
- Copy and download the result. Wait at least a minute between repeated public tests because the analysis function has a shared rate limit.

The repository does not reserve a Netlify URL or demonstrate a live deployment. Local tests simulate provider responses; real AI must be validated after the key is configured on your account.

## Limits and cost

The analysis function declares Netlify's native rate-limit rule: **two requests per 60-second sliding window per site domain**. This is platform configuration, not an in-memory Python limit. Netlify's bundler recognizes and includes the rule; verify deployment acceptance and actual enforcement in your account. Platform rate-limit responses can be plain text, which the interface handles with a friendly message.

The server accepts at most 32 KiB of JSON and 6000 characters of pasted issue text. Visitors cannot switch to an unconfigured model. Provider requests have a 25-second deadline, ask for at most 750 output tokens, and are not automatically retried. Hosting-plan function limits may apply sooner.

The Python backend's daily counter and concurrency gate do not apply to separate Netlify function instances. Netlify account credits, its platform rules, and Groq's own free-tier quotas are the limits for this deployment. Free plans are not unlimited or an always-on guarantee. Confirm current terms at https://www.netlify.com/pricing/ and https://console.groq.com/docs/rate-limits . This code does not enable billing, buy credits, or guarantee that a particular account is eligible for free hosting.

## Privacy and security

The API key is read only by server functions. The build script copies only the HTML, JavaScript, and CSS into the publish directory. Server source, credentials, and local environment files are not published as website assets.

Issue text goes to the server and to Groq. URL mode also contacts `api.github.com`; issue fetching does not inspect repository code. The app does not persist prompts. Hosting/provider policies still apply, so use public issue information only. Responses are rendered as literal text, not executable HTML. Raw provider error bodies are not returned to visitors.

This is a small public portfolio app without user accounts, not a guarantee of protection against distributed abuse.

## Developer checks

The Netlify backend is a small JavaScript serverless adapter because Netlify does not run the existing FastAPI/Ollama server as a native Python web service. It uses the same `app/prompt.json` as FastAPI. It needs no additional application npm packages.

With Node.js 22 or newer:

```powershell
node --test tests/netlify/*.test.mjs
node scripts/build_netlify.mjs
```

Build output is `_netlify/`; API handlers are in `netlify/functions/`. FastAPI tests still run with `.venv` and `pytest` as documented in the README. GitHub Actions checks both versions.

## Troubleshooting

| Problem | Action |
|---|---|
| AI key missing | Add `GROQ_API_KEY` privately in Netlify environment settings and redeploy. |
| Credentials/model need attention | Check the key and available free-tier model in Groq. Replace the key securely or update `GROQ_MODEL`, then redeploy. |
| HTTP 429 | Wait for the shared site/provider quota window. Do not purchase an upgrade automatically. |
| `/health` returns 404 | Confirm the repository was imported with `netlify.toml` and that Netlify built all three functions. |
| Build rejects rate-limit configuration | Share the redacted error. Check whether your plan supports it before proceeding; do not enable a paid upgrade. |
| Function timeout | Check the provider status and your account's function-duration limits; do not describe a timed-out request as successful AI output. |
