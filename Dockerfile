# Official Ollama artifacts; Docker verifies content digests during pulls.
FROM ollama/ollama:0.40.6@sha256:40c61dbf5091e0b4cc46f406f912fb061cfeca51208f0f7173c87c3b5f795c95 AS ollama
# The shared host is CPU-only. Keep CPU runners and licenses, excluding GPU subdirectories.
RUN mkdir /opt/ollama-cpu \
    && find /usr/lib/ollama -mindepth 1 -maxdepth 1 ! -type d \
       -exec cp -a -t /opt/ollama-cpu -- {} +
FROM python:3.12-slim-trixie AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 libstdc++6 libopenblas0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app
COPY --from=ollama /bin/ollama /usr/local/bin/ollama
COPY --from=ollama /opt/ollama-cpu/ /usr/lib/ollama/
WORKDIR /home/app/project
COPY requirements.txt ./
# Optional trusted CA bundle for enterprise build proxies; verification stays enabled.
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m pip install --no-cache-dir -r requirements.txt
ENV HOME=/home/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODELS=/home/app/.ollama/models \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=1 \
    OLLAMA_MAX_QUEUE=1 \
    OLLAMA_NO_CLOUD=1 \
    OLLAMA_MODEL=qwen3:1.7b \
    PUBLIC_MODE=true \
    MOCK_AI=false
COPY --chown=1000:1000 deploy/serve.py deploy/cache_model.py ./deploy/
USER 1000
FROM runtime AS model-cache
# A separate cache stage keeps any generated Ollama identity out of the final image.
RUN --mount=type=secret,id=build_ca,uid=1000,mode=0400 \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    python deploy/cache_model.py
FROM runtime AS app-runtime
COPY --chown=1000:1000 app ./app
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:7860/health',timeout=4)); assert d['status']=='ready'"
ENTRYPOINT ["python", "deploy/serve.py"]

FROM app-runtime AS final
COPY --from=model-cache --chown=1000:1000 /home/app/.ollama/models/ /home/app/.ollama/models/
