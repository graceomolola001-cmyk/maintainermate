# Security

The default Ollama configuration is for local use; keep its services bound to loopback. The optional Python Render/Groq deployment has request-size limits, a shared cooldown, a daily request budget, and one-at-a-time inference. It is a small public demo without user accounts or distributed abuse protection. The Netlify version uses a platform rate-limit rule rather than a shared Python counter. See the [Netlify guide](docs/netlify.md) and [Render guide](docs/hosting.md) for the limits of each deployment.

Do not paste credentials, private repository content, or sensitive documents into the app or issue tracker. Hosted mode sends issue text to Groq; keep the provider key only in server-side environment settings, never in frontend files or logs. AI output is untrusted advice and must be reviewed before use.

## Reporting a vulnerability

Do not post exploit details, credentials, or private data in a public issue. If the repository's Security tab offers **Report a vulnerability**, use that private reporting feature. If it is unavailable, open a minimal issue requesting a private reporting channel without disclosing vulnerability details.

There is no guaranteed response time. Report the affected version, reproduction steps, and potential impact privately once a channel is available. Redact all personal data and credentials.
