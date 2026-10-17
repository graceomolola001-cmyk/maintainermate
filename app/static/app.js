const el = id => document.getElementById(id);
const EXAMPLE = 'Our open-source project README includes installation steps for Linux and macOS, but newcomers on Windows cannot complete setup. Add clear Windows 11 instructions using PowerShell, explain how to install dependencies, and include troubleshooting advice for common PATH and execution policy errors.';
const STATIC_DEMO = document.documentElement.dataset.demo === 'true';
const runLabel = STATIC_DEMO ? 'View sample plan' : 'Generate contribution plan';
let mode = 'paste';

if (STATIC_DEMO) {
  el('demo-banner').classList.remove('hidden');
  el('issue-text').value = EXAMPLE;
  el('issue-text').readOnly = true;
  el('url-tab').classList.add('hidden');
  el('sample-button').textContent = 'Use the sample issue';
  el('model-select').disabled = true;
  el('run-label').textContent = runLabel;
  el('result-loading').querySelector('p').textContent = 'Loading the sample contribution plan…';
}

async function loadDemoPlan() {
  const response = await fetch('./demo-plan.json');
  if (!response.ok) throw new Error('The sample could not load. Please refresh and try again.');
  return response.json();
}


function setMode(next) {
  mode = next;
  el('text-field').classList.toggle('hidden', mode !== 'paste');
  el('url-field').classList.toggle('hidden', mode !== 'url');
  for (const value of ['paste', 'url']) {
    el(`${value}-tab`).classList.toggle('selected', mode === value);
    el(`${value}-tab`).setAttribute('aria-pressed', String(mode === value));
  }
}

function showState(state) {
  for (const value of ['empty', 'loading', 'ready', 'error']) {
    const target = value === 'ready' ? 'result-ready' : `result-${value}`;
    el(target).classList.toggle('hidden', value !== state);
  }
}

function updateChars() {
  el('char-count').textContent = `${el('issue-text').value.length} / 6000`;
}

el('paste-tab').addEventListener('click', () => setMode('paste'));
el('url-tab').addEventListener('click', () => setMode('url'));
el('issue-text').addEventListener('input', updateChars);
el('sample-button').addEventListener('click', () => {
  setMode('paste'); el('issue-text').value = EXAMPLE; updateChars(); el('issue-text').focus();
});

async function checkModels() {
  try {
    const response = STATIC_DEMO
      ? {ok: true, json: async () => ({status: 'mock', models: [], default_model: 'Sample response (no AI)'})}
      : await fetch('/health');
    if (!response.ok) throw new Error('Health request failed');
    const data = await response.json();
    if (data.public_mode) {
      el('hosted-banner').classList.remove('hidden');
      if (data.status === 'mock') {
        el('hosted-banner').querySelector('strong').textContent = 'Sample responses on a shared server';
      }
      el('result-loading').querySelector('p').textContent = 'Generating your plan on the shared AI server. This may take a few minutes…';
    }
    const select = el('model-select');
    select.replaceChildren();
    const choices = data.models.length ? data.models : [data.default_model];
    for (const model of choices) {
      const option = document.createElement('option');
      option.value = model; option.textContent = model;
      select.appendChild(option);
    }
    if (choices.includes(data.default_model)) select.value = data.default_model;
    if (data.status === 'ready') {
      el('runtime-status').textContent = `✓ Ollama connected · ${choices.length} model${choices.length === 1 ? '' : 's'} available`;
    } else if (data.status === 'mock') {
      el('runtime-status').textContent = 'Demo mode. No Ollama model will be called.';
    } else if (data.status === 'ollama_offline') {
      el('runtime-status').textContent = data.public_mode
        ? 'The shared AI server is starting or unavailable. Please try again shortly.'
        : 'Ollama offline. Open Ollama or run ollama serve.';
    } else {
      el('runtime-status').textContent = `No models installed. Run ollama pull ${data.default_model}`;
    }
  } catch {
    el('runtime-status').textContent = 'Cannot check Ollama connection. Check that the app is running.';
  }
}

el('analyze-form').addEventListener('submit', async event => {
  event.preventDefault();
  const payload = {
    issue_text: mode === 'paste' ? el('issue-text').value.trim() : '',
    github_url: mode === 'url' ? el('issue-url').value.trim() : '',
    model: el('model-select').value
  };
  if (!payload.issue_text && !payload.github_url) {
    el('result-error').textContent = 'Add some issue text or paste a GitHub issue URL first.';
    showState('error'); return;
  }
  el('run-button').disabled = true;
  el('run-label').textContent = STATIC_DEMO ? 'Loading sample…' : 'Generating contribution plan…';
  el('copy-button').textContent = 'Copy';
  showState('loading');
  try {
    let data;
    if (STATIC_DEMO) {
      data = await loadDemoPlan();
    } else {
      const response = await fetch('/api/analyze', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check the issue and try again.');
    }
    // Model output remains literal text. Never interpolate it into HTML.
    el('result-text').textContent = data.analysis;
    el('result-meta').textContent = `${data.model} · ${data.issue_source} · Always request human review`;
    showState('ready');
  } catch (err) {
    el('result-error').textContent = err.message || 'An unexpected error occurred.';
    showState('error');
  } finally {
    el('run-button').disabled = false;
    el('run-label').textContent = runLabel;
  }
});

el('copy-button').addEventListener('click', async () => {
  try {
    const attribution = STATIC_DEMO ? 'Sample response — no AI model was used.\n\n' : '';
    await navigator.clipboard.writeText(attribution + el('result-text').textContent);
    el('copy-button').textContent = 'Copied ✓';
  } catch { el('copy-button').textContent = 'Select to copy'; }
});

el('download-button').addEventListener('click', () => {
  const content = `# MaintainerMate contribution plan\n\n${el('result-meta').textContent}\n\n${el('result-text').textContent}\n\n---\nDraft guidance. Request human maintainer review.\n`;
  const file = new Blob([content], {type:'text/markdown;charset=utf-8'});
  const url = URL.createObjectURL(file);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = 'maintainermate-plan.md'; anchor.click();
  URL.revokeObjectURL(url);
});
updateChars();
checkModels();
