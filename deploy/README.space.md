---
title: MaintainerMate AI
emoji: 🛠️
colorFrom: purple
colorTo: teal
sdk: docker
app_port: 7860
license: mit
short_description: Turn public GitHub issues into contribution plans
---

# MaintainerMate AI

Paste an issue description or a public GitHub issue URL to generate an explanation, implementation plan, testing checklist, and draft pull request description.

The application runs **qwen3:1.7b through Ollama on this server**, not on the visitor's computer. CPU generation can take a few minutes. One request runs at a time with a short shared cooldown. If the server is busy, wait and try again.

This is AI-generated guidance. The app does not inspect repository code, edit files, execute tests for you, or submit contributions. Review all suggestions.

Do not enter credentials or private information. Your issue text is processed by this server; the application does not persist it. Public URL mode also contacts the GitHub API. Your hosting provider may retain operational metadata under its own policies.

Source code and local setup: https://github.com/graceomolola001-cmyk/maintainermate

Code is MIT licensed. Ollama and Qwen have separate licenses; model weights are downloaded from Ollama's registry during the image build. No paid model API is used.

## Deployment notes for the owner

The Docker image starts FastAPI on port 7860 and keeps Ollama private on 127.0.0.1:11434. It includes qwen3:1.7b, so each restart does not have to download model weights.

Check your account's current hosting terms **before** deploying. CPU Basic has no hourly charge, but current Hugging Face documentation says creating compute Spaces requires a paid plan. This repository does not select or purchase hardware. There is no guarantee this Space is available on a free account.

Use CPU Basic only if your account offers it within your budget. Do not set MOCK_AI=true for real inference. Inspect /health and verify an actual generated plan after deployment before sharing the URL.
