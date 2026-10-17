# Contributing to MaintainerMate

Thanks for helping newcomers contribute confidently to open source.

## Run locally

Follow the PowerShell instructions in [README.md](README.md) or run the tests with:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

## Before opening a PR

1. Create or select an issue. Describe the problem and expected outcome.
2. Create a feature branch, for example `docs/improve-windows-setup`.
3. Keep the PR focused; avoid unrelated changes.
4. Test any changes locally and disclose what you could not test.
5. Update the README when behavior changes.
6. Open a PR with a clear summary, how to test, and screenshots for UI changes.

All contributions need maintainer review before merging. This assistant provides suggestions and does not determine whether changes are safe or correct.

## Good first issue suggestions

- Improve the Windows setup troubleshooting table.
- Add tests for malformed GitHub issue URLs.
- Improve screen-reader labels and keyboard navigation.
- Add a realistic example issue from a public GitHub repository.
- Document common Ollama errors with screenshots and clear resolutions.

Please never commit API keys, secret tokens, private repository data, or local `.env` files.
