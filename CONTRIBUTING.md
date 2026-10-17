# Contributing to MaintainerMate

Help newcomers contribute confidently to open source. Reports and small, focused improvements are welcome.

## Development setup

Follow the [README](README.md) to create `.venv`. Install test dependencies and run tests from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux/macOS, use `.venv/bin/python`. Tests mock GitHub and Ollama; no model downloads or credentials are needed. Use `MOCK_AI=true` to develop the interface without Ollama. To check actual AI output, use your installed model and disclose that manual check separately from mocked tests.

## Before opening a pull request

1. Search existing issues and pull requests. For a large change, discuss it with the maintainer first.
2. Fork the repository, clone your fork, and create a descriptive feature branch.
3. Make a focused change and add regression tests when fixing behavior.
4. Run the tests and update documentation when setup or behavior changes.
5. Open a pull request describing the problem, change, and validation. Include screenshots for UI changes and disclose checks you could not run.

Treat contributors respectfully. AI-assisted contributions are welcome when you understand the change, verify it, and explain how it was tested. Generated plans alone do not demonstrate that code works. Maintainers review contributions before merging; submitting a PR does not guarantee acceptance.

## Useful first contributions

- Improve keyboard navigation and screen-reader feedback, with browser checks.
- Add tests for GitHub rate-limit and malformed-response handling.
- Document verified setup steps for additional operating systems.
- Improve error messages using reproducible, redacted examples.

Use [issue templates](https://github.com/graceomolola001-cmyk/maintainermate/issues/new/choose) for bugs and suggestions. Never commit tokens, `.env` files, private issue text, model weights, or virtual environments. For vulnerabilities, follow [SECURITY.md](SECURITY.md).

By submitting a contribution, you agree it can be distributed under this project's [MIT License](LICENSE).
