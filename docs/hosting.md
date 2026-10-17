# Hosting real AI responses

The static Pages demo uses fixed examples. A live AI deployment must run FastAPI **and** Ollama on the same server. The supplied Docker image provides both, using only `qwen3:1.7b`.

## Hosting cost and access

**Check current account eligibility first.** [Hugging Face's official documentation](https://github.com/huggingface/hub-docs/blob/main/docs/hub/spaces-overview.md#hardware-resources) currently says creating compute Spaces (Docker or Gradio) requires a paid plan, although CPU Basic itself has no hourly charge. Static Spaces are free. A free username alone does not establish access to Docker hosting. Do not select a paid upgrade if your requirement is zero cost.

The deployment files can also be used on an existing Linux machine with Docker. They do not create any cloud resource, purchase a plan, or guarantee free hosted inference. For a completely free portfolio link, retain the sample-only GitHub Pages demo; the full application can still run locally with Ollama.

## Build and test the container

Requires Docker with Linux amd64 containers and adequate disk space. The official Ollama build stage includes a large download; the final image retains only CPU runtimes and the selected model. Initial builds also download the same qwen3:1.7b model used by the local app, roughly 1.4 GB. No other model is requested. Artifact hashes and TLS verification remain enabled.

```powershell
docker build --platform linux/amd64 -t maintainermate .
docker run --name maintainermate-test --cpus 2 --memory 8g -p 127.0.0.1:7860:7860 maintainermate
```

Open http://127.0.0.1:7860 on that machine. In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:7860/health
$body = @{ issue_text = 'Add clear Windows PowerShell installation instructions for new contributors.' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:7860/api/analyze -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 240
```

The health result must have `status: ready`, `public_mode: true`, and `qwen3:1.7b` in `models`. A generated response must name `qwen3:1.7b`, not DEMO ONLY. Use `docker stop maintainermate-test` to stop this test container. A later run needs a different container name or a deliberate cleanup of the old test container.

### Builds behind a trusted corporate proxy

If a proxy uses a private certificate authority, supply its trusted CA bundle as an optional BuildKit secret named `build_ca`. The Dockerfile uses it for dependency and model downloads without disabling certificate verification. It is not copied into the runtime image. Standard public builds need no extra flag. Network access to `registry.ollama.ai` and its model-blob destinations is also required.

## Upload to Hugging Face (only if hosting fits your account)

1. Run `python scripts/build_space.py` from the repository root. This creates `_space/` containing only deployment files. Existing output is preserved; the exporter stops rather than overwriting it.
2. At https://huggingface.co/new-space choose owner `Gracie-AI`, name `maintainermate`, visibility Public, SDK Docker, and a blank template. Confirm the hardware and account terms before creating it. Do not purchase an upgrade to follow this guide.
3. Upload the **contents** of `_space/` to the Space repository, preserving the `app/` and `deploy/` folders. `Dockerfile` and the generated `README.md` belong at the Space root. Do not upload a ZIP as a replacement for these files.
4. Wait for the image build, model download, and application startup. Read build/runtime logs if it fails. Hugging Face access/authentication is required; a GitHub token does not grant it. Never share an access token in chat.
5. Verify health and generate a plan in the App tab. Only after successful validation share https://huggingface.co/spaces/Gracie-AI/maintainermate. The address is a planned destination, not proof a Space exists.

## Limits and operations

- One Uvicorn worker, one active generation, and a shared 30-second minimum interval between starts. Busy or too-frequent requests return HTTP 429 with Retry-After.
- Hosted mode accepts only qwen3:1.7b and limits JSON bodies to 32 KiB, including streamed bodies; the existing 6000-character issue limit also applies.
- The UI explains that issue text is processed by a shared server. The application does not persist prompts. Operational metadata is subject to hosting-provider policies.
- Ollama listens only on loopback; only FastAPI port 7860 is exposed. Container services terminate together on failure or shutdown.
- This is intended for a small public demonstration, with no user accounts. It is not protection against distributed denial-of-service attacks or a service-level guarantee.
- Local setup remains unchanged when PUBLIC_MODE is unset. PUBLIC_MODE=true is enabled by default only in the container.
