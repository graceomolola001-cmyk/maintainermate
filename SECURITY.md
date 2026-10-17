# Security

The default configuration is intended for local use on a trusted machine. Keep it bound to loopback. The optional Docker deployment provides request-size limits, one-at-a-time inference, a shared cooldown, and a private Ollama endpoint for a small public demonstration. It does not provide user accounts, distributed rate limiting, or denial-of-service protection. Read [the hosting guide](docs/hosting.md) before deploying; production or sensitive use requires additional design.

Do not paste credentials, private repository content, or sensitive documents into the app or issue tracker. AI output is untrusted advice and must be reviewed before use.

## Reporting a vulnerability

Do not post exploit details, credentials, or private data in a public issue. If the repository's Security tab offers **Report a vulnerability**, use that private reporting feature. If it is unavailable, open a minimal issue requesting a private reporting channel without disclosing vulnerability details.

There is no guaranteed response time. Report the affected version, reproduction steps, and potential impact privately once a channel is available. Redact all personal data and credentials.
