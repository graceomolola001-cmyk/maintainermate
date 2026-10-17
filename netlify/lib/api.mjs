// Server-only API for Netlify. The browser never receives the Groq credential.
import prompt from '../../app/prompt.json' with { type: 'json' };

const DEFAULT_MODEL = 'openai/gpt-oss-20b';
const SUPPORTED_MODELS = ['openai/gpt-oss-20b', 'llama-3.3-70b-versatile', 'qwen/qwen3-32b'];
const GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODELS_URL = 'https://api.groq.com/openai/v1/models';
const MAX_BYTES = 32 * 1024;

class Problem extends Error {
  constructor(status, message, headers = {}, diagnostics = {}) {
    super(message);
    this.status = status;
    this.headers = headers;
    this.diagnostics = diagnostics;
  }
}

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers},
  });
}

function parseIssueUrl(value) {
  // Check the original authority too: URL normalizes an explicit :443 away.
  if (!/^https:\/\/(?:www\.)?github\.com\//i.test(value)) {
    throw new Problem(422, 'Use a public GitHub issue URL ending in /owner/repo/issues/number.');
  }
  let url;
  try { url = new URL(value); } catch {
    throw new Problem(422, 'Invalid GitHub issue URL.');
  }
  const match = /^\/([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)\/issues\/([0-9]+)\/?$/.exec(url.pathname);
  if (!match || url.search || url.hash || url.username || url.password || url.port) {
    throw new Problem(422, 'Use a public GitHub issue URL ending in /owner/repo/issues/number.');
  }
  return match.slice(1);
}

async function readInput(request) {
  const type = request.headers.get('content-type')?.split(';')[0].trim().toLowerCase();
  if (type !== 'application/json') throw new Problem(415, 'Send a JSON request.');
  const length = request.headers.get('content-length');
  if (length && /^\d+$/.test(length) && Number(length) > MAX_BYTES) {
    throw new Problem(413, 'Request is too large. Use a shorter issue description.');
  }
  const reader = request.body?.getReader();
  const chunks = [];
  let size = 0;
  if (reader) {
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BYTES) {
        await reader.cancel();
        throw new Problem(413, 'Request is too large. Use a shorter issue description.');
      }
      chunks.push(value);
    }
  }
  let data;
  try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch {
    throw new Problem(422, 'Enter valid JSON issue data.');
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Problem(422, 'Enter valid issue data.');
  }
  const input = {};
  for (const [name, max] of [['issue_text', 6000], ['github_url', 300], ['model', 100]]) {
    const value = Object.hasOwn(data, name) ? data[name] : '';
    if (typeof value !== 'string' || [...value].length > max) {
      throw new Problem(422, `Invalid ${name}. Maximum length: ${max} characters.`);
    }
    input[name] = value.trim();
  }
  if (Boolean(input.issue_text) === Boolean(input.github_url)) {
    throw new Problem(422, 'Enter either issue text or a public GitHub issue URL.');
  }
  if (input.issue_text && [...input.issue_text].length < 20) {
    throw new Problem(422, 'Write at least 20 characters describing the issue.');
  }
  if (input.github_url) input.issueParts = parseIssueUrl(input.github_url);
  return input;
}

async function fetchIssue(parts, fetchImpl, signal) {
  const [owner, repo, number] = parts;
  const url = `https://api.github.com/repos/${owner}/${repo}/issues/${number}`;
  const response = await fetchImpl(url, {
    headers: {'Accept': 'application/vnd.github+json', 'User-Agent': 'MaintainerMate'},
    redirect: 'manual', signal: AbortSignal.any([signal, AbortSignal.timeout(8000)]),
  });
  if (response.status === 404) throw new Problem(404, 'Issue not found or repository is private.');
  if ([403, 429].includes(response.status)) {
    throw new Problem(429, 'GitHub usage limit reached. Paste the issue text instead.');
  }
  if (!response.ok) throw new Problem(502, 'GitHub could not retrieve that issue. Paste its text instead.');
  let issue;
  try { issue = await response.json(); } catch {
    throw new Problem(502, 'GitHub returned an invalid response.');
  }
  if (!issue || typeof issue !== 'object' || Array.isArray(issue)) {
    throw new Problem(502, 'GitHub returned an invalid response.');
  }
  if ('pull_request' in issue) throw new Problem(422, 'That link is a pull request. Choose a GitHub issue.');
  const labels = (Array.isArray(issue.labels) ? issue.labels : [])
    .filter(value => value && typeof value === 'object')
    .map(value => String(value.name ?? '')).join(', ').slice(0, 250);
  return `Repository: ${owner}/${repo}\nTitle: ${String(issue.title ?? '').slice(0, 500)}\nLabels: ${labels}\nBody:\n${String(issue.body || '(No issue description)').slice(0, 5300)}`;
}

function retryAfter(value) {
  return /^\d{1,6}$/.test(value ?? '') ? String(Math.min(Math.max(Number(value), 1), 3600)) : '60';
}

// Only known codes and controlled messages may leave the server. Provider error
// messages can contain private data and must never be echoed or logged wholesale.
const PROVIDER_ERRORS = {
  model_decommissioned: 'The configured AI model has been retired. The app owner needs to select an active Groq model.',
  model_not_found: 'The configured AI model is unavailable to this account. The app owner needs to check the Groq model setting.',
  model_permission_blocked: 'This model is blocked by the Groq project permissions. The app owner needs to enable access in Groq.',
  organization_restricted: 'The Groq account is restricted. The app owner needs to check the account settings in Groq.',
  invalid_api_key: 'The Groq API key was rejected. The app owner needs to update the server credential.',
  insufficient_quota: 'The Groq account has reached a usage limit. Please try again later.',
  rate_limit_exceeded: 'The AI service usage limit has been reached. Please try again later.',
  invalid_request_error: 'Groq rejected the AI request. The app owner needs to check the request settings.',
};

async function providerFailure(response) {
  let body;
  try { body = await response.json(); } catch { body = null; }
  const rawCode = body?.error?.code;
  const rawType = body?.error?.type;
  const code = typeof rawCode === 'string' && Object.hasOwn(PROVIDER_ERRORS, rawCode) ? rawCode
    : typeof rawType === 'string' && Object.hasOwn(PROVIDER_ERRORS, rawType) ? rawType : 'unclassified';
  const defaults = response.status === 429
    ? 'The AI service usage limit has been reached. Please try again later.'
    : [401, 403].includes(response.status)
      ? 'The AI service credentials or account permissions need attention from the app owner.'
      : response.status === 402 ? 'The Groq account cannot serve this request. The app owner needs to check account access.'
        : response.status === 400 ? 'Groq rejected the AI request. The app owner needs to check the request settings.'
          : response.status === 404 ? 'The configured AI model is unavailable. The app owner needs to check the model setting.'
            : 'The AI service is temporarily unavailable. Please try again later.';
  const status = response.status === 429 ? 429 : [400, 401, 402, 403, 404].includes(response.status) ? 503 : 502;
  const headers = response.status === 429 ? {'Retry-After': retryAfter(response.headers.get('Retry-After'))} : {};
  const diagnostics = {provider: 'groq', provider_status: response.status, provider_error: code};
  // Parameter names are also restricted to a fixed allowlist, never arbitrary text.
  if (['model', 'max_completion_tokens', 'temperature', 'messages', 'stream'].includes(body?.error?.param)) {
    diagnostics.provider_parameter = body.error.param;
  }
  console.warn('Groq request rejected:', JSON.stringify(diagnostics));
  return new Problem(status, PROVIDER_ERRORS[code] || defaults, headers, diagnostics);
}

async function inspectProvider(model, key, fetchImpl) {
  const response = await fetchImpl(GROQ_MODELS_URL, {
    headers: {'Authorization': `Bearer ${key}`}, redirect: 'manual', signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw await providerFailure(response);
  let body;
  try { body = await response.json(); } catch { body = null; }
  if (!Array.isArray(body?.data)) throw new Problem(502, 'Groq returned an invalid model list.');
  const ids = new Set(body.data.filter(item => item && item.active !== false).map(item => item.id));
  const available = ids.has(model);
  const candidates = SUPPORTED_MODELS.filter(id => id !== model && ids.has(id));
  return {provider: 'groq', provider_status: response.status, model,
    status: available ? 'model_listed' : 'model_not_listed',
    model_available: available, alternative_models_listed: candidates,
    models: [...new Set([model, ...SUPPORTED_MODELS])].filter(id => ids.has(id)),
    detail: available
      ? 'Groq accepts this key for the model list, and the configured model is listed. Generation permissions and quota still require a successful plan request.'
      : 'The configured model is not in the active Groq model list. Check an available model in the Groq console before updating GROQ_MODEL as a non-secret setting.'};
}

export function createApi({env = process.env, fetchImpl = globalThis.fetch} = {}) {
  return async function handle(request, endpoint) {
    try {
      const model = (env.GROQ_MODEL || DEFAULT_MODEL).trim() || DEFAULT_MODEL;
      const key = (env.GROQ_API_KEY || '').trim();
      if (!/^[A-Za-z0-9._:/-]{1,100}$/.test(model)) {
        throw new Problem(503, 'The AI model setting needs attention from the app owner.');
      }
      const method = endpoint === 'analyze' ? 'POST' : 'GET';
      if (request.method !== method) throw new Problem(405, 'Method not allowed.', {'Allow': method});
      if (endpoint === 'health') {
        return json({status: key ? 'api_configured' : 'api_key_missing', default_model: model,
          models: [model], ollama: 'not_required', public_mode: true, provider: 'groq'});
      }
      if (!key) throw new Problem(503, 'AI is not configured yet. The app owner needs to add the server API key.');
      if (endpoint === 'provider-status') return json(await inspectProvider(model, key, fetchImpl));
      if (endpoint === 'models') {
        const catalog = await inspectProvider(model, key, fetchImpl);
        return json({provider: 'groq', default_model: model, models: catalog.models});
      }
      if (endpoint === 'ready') return json({status: 'configured', provider: 'groq'});
      const input = await readInput(request);
      const selectedModel = input.model || model;
      if (![model, ...SUPPORTED_MODELS].includes(selectedModel)) {
        throw new Problem(422, 'Choose one of the supported models hosted through Groq.');
      }
      const signal = AbortSignal.timeout(25000);
      const issue = input.issueParts ? await fetchIssue(input.issueParts, fetchImpl, signal) : input.issue_text;
      const response = await fetchImpl(GROQ_URL, {
        method: 'POST', redirect: 'manual', signal,
        headers: {'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json'},
        body: JSON.stringify({model: selectedModel, messages: [
          {role: 'system', content: prompt.system_prompt},
          {role: 'user', content: `Analyze the following issue:\n<issue>\n${issue}\n</issue>`},
        ], temperature: 0.3, max_completion_tokens: 750, stream: false}),
      });
      if (!response.ok) throw await providerFailure(response);
      let result;
      try { result = await response.json(); } catch {
        throw new Problem(502, 'The AI service returned an invalid response.');
      }
      const analysis = result?.choices?.[0]?.message?.content;
      if (typeof analysis !== 'string' || !analysis.trim()) {
        throw new Problem(502, 'The AI service returned an invalid response.');
      }
      return json({analysis: analysis.trim().slice(0, 12000), model: selectedModel, provider: 'groq',
        issue_source: input.issueParts ? 'Public GitHub issue' : 'Pasted issue text'});
    } catch (error) {
      if (error instanceof Problem) return json({detail: error.message, ...error.diagnostics}, error.status, error.headers);
      if (['AbortError', 'TimeoutError'].includes(error?.name)) {
        return json({detail: 'The AI request timed out. Please try again later.'}, 504);
      }
      // Never return upstream exception messages, provider bodies, or credentials.
      return json({detail: 'The service could not complete this request. Please try again later.'}, 502);
    }
  };
}
