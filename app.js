const el = id => document.getElementById(id);
const EXAMPLE = 'Our open-source project README includes installation steps for Linux and macOS, but newcomers on Windows cannot complete setup. Add clear Windows 11 instructions using PowerShell, explain how to install dependencies, and include troubleshooting advice for common PATH and execution policy errors.';
let mode = 'paste';

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
    const response = await fetch('/health');
    if (!response.ok) throw new Error('Health request failed');
    const data = await response.json();
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
      el('runtime-status').textContent = 'Ollama offline. Open Ollama for Windows or run ollama serve.';
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
  el('run-label').textContent = 'Generating contribution plan…';
  showState('loading');
  try {
    const response = await fetch('/api/analyze', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check the issue and try again.');
    // Model output remains literal text. Never interpolate it into HTML.
    el('result-text').textContent = data.analysis;
    el('result-meta').textContent = `${data.model} · ${data.issue_source} · Always request human review`;
    showState('ready');
  } catch (err) {
    el('result-error').textContent = err.message || 'An unexpected error occurred.';
    showState('error');
  } finally {
    el('run-button').disabled = false;
    el('run-label').textContent = 'Generate contribution plan';
  }
});

el('copy-button').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(el('result-text').textContent);
    el('copy-button').textContent = 'Copied ✓';
  } catch { el('copy-button').textContent = 'Select to copy'; }
});

el('download-button').addEventListener('click', () => {
  const content = `# MaintainerMate contribution plan\n\n${el('result-text').textContent}\n\n---\nDraft guidance. Request human maintainer review.\n`;
  const file = new Blob([content], {type:'text/markdown;charset=utf-8'});
  const url = URL.createObjectURL(file);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = 'maintainermate-plan.md'; anchor.click();
  URL.revokeObjectURL(url);
});
updateChars();
checkModels();
