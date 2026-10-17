# MaintainerMate AI (Hacktoberfest MVP)

A **local-first GitHub issue-to-contribution-plan app** built with FastAPI, JavaScript, Ollama, and **your already-installed `qwen3:1.7b`**. Switch to **`gemma3:1b`** from the app's model dropdown after its download completes.

**What it does:** Paste an issue or a public GitHub issue URL → select a local model → click **Generate contribution plan**. It produces an issue explanation, first checks, suggested implementation steps, a testing checklist, and a draft pull request description. Copy or download the plan as Markdown. Humans still review all changes.

## Start on Windows with PowerShell

1. Extract the ZIP. Open the extracted `maintainermate_mvp` folder in File Explorer, click its address bar, type `powershell`, and press Enter.
2. Check Ollama is running and your installed model shows up:

   ```powershell
   ollama list
   ```

   You already have `qwen3:1.7b` installed. **Let Gemma's download finish in the separate PowerShell window; don't restart it unless necessary.**

3. Install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   If `python` is unavailable, try `py -3 -m venv .venv`.

4. Start the application:

   ```powershell
   $env:OLLAMA_MODEL = 'qwen3:1.7b'
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

5. Open **http://127.0.0.1:8000**. Click **Use a sample Hacktoberfest issue** → **Generate contribution plan**. The initial model may take a minute to load on 8GB RAM.

6. When Gemma finishes downloading, **refresh the web page** and select `gemma3:1b` in the model dropdown. No code changes or restart needed.

You can alternatively run `./setup.ps1` and `./start.ps1` if scripts are permitted, though the commands above also work when PowerShell blocks `.ps1` files.

## Debug quick reference

| Problem | What to do |
|---|---|
| Ollama offline | Open Ollama for Windows; only run `ollama serve` in another window if the server isn't already running |
| Model missing | Run `ollama list` and pick an installed model in the app's dropdown |
| Python not found | Install Python 3.10+ (check `py --version`), then re-run the venv command |
| App takes a long time | Close memory-heavy tabs/apps and let Ollama load the model; try Qwen first |
| `Address already in use` | Stop the other server using port 8000 or start with `--port 8001` |
| GitHub URL fails | Paste the public issue title and description manually; URL mode needs internet |

### Run automated tests

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Tests simulate the model API so no online AI call is needed.

### See API docs and service health

- `http://127.0.0.1:8000/api/docs`
- `http://127.0.0.1:8000/health`

### Demo without a running model

```powershell
$env:MOCK_AI = 'true'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

This produces a **fake demonstration response**, not AI output. Stop the server with Ctrl+C, then unset the variable using `Remove-Item Env:MOCK_AI`.

## Architecture

- `app/main.py`: FastAPI routes (`GET /health`, `POST /api/analyze`) and Ollama chat request.
- `app/static`: browser interface; model picker, sample issue, copy and Markdown download.
- `setup.ps1` / `start.ps1`: Windows helper scripts.
- `tests/test_app.py`: mocked, reproducible backend tests.

The local model runs at `http://127.0.0.1:11434` through Ollama. The web app runs at `http://127.0.0.1:8000`.

**Security:** Run the app on localhost only. Do not expose ports 8000 or 11434 to the internet. GitHub URL parsing restricts requests to public `github.com/.../issues/...` and fetches through `api.github.com`. Do not paste secrets. The assistant cannot modify files, create pull requests, or confirm real test results. Cloud deployment requires further authentication and infrastructure design.

## Next milestone after the hackathon demo

Turn this into a public GitHub repo with `CONTRIBUTING.md`, open beginner issues, and get your first contributor-reviewed PR. Later, add GitHub OAuth, per-repo instructions, and reviewer feedback.
