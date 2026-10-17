// Server-only API for Netlify. The browser never receives the Groq credential.
import prompt from '../../app/prompt.json' with { type: 'json' };

const DEFAULT_MODEL = 'llama-3.1-8b-instant';
const GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions';
const MAX_BYTES = 32 * 1024;

class Problem extends Error {
  constructor(status, message, headers = {}) {
    super(message);
    this.status = status;
    this.headers = headers;
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
      if (endpoint === 'ready') return json({status: 'configured', provider: 'groq'});
      const input = await readInput(request);
      if (input.model && input.model !== model) {
        throw new Problem(422, 'This shared server only supports its configured model.');
      }
      const signal = AbortSignal.timeout(25000);
      const issue = input.issueParts ? await fetchIssue(input.issueParts, fetchImpl, signal) : input.issue_text;
      const response = await fetchImpl(GROQ_URL, {
        method: 'POST', redirect: 'manual', signal,
        headers: {'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json'},
        body: JSON.stringify({model, messages: [
          {role: 'system', content: prompt.system_prompt},
          {role: 'user', content: `Analyze the following issue:\n<issue>\n${issue}\n</issue>`},
        ], temperature: 0.3, max_completion_tokens: 750, stream: false}),
      });
      if (response.status === 429) {
        throw new Problem(429, 'The AI service usage limit has been reached. Please try again later.',
          {'Retry-After': retryAfter(response.headers.get('Retry-After'))});
      }
      if ([401, 403].includes(response.status)) {
        throw new Problem(503, 'The AI service credentials need attention from the app owner.');
      }
      if ([400, 402, 404].includes(response.status)) {
        throw new Problem(503, 'The AI model or account is unavailable. Please contact the app owner.');
      }
      if (!response.ok) throw new Problem(502, 'The AI service is temporarily unavailable. Please try again later.');
      let result;
      try { result = await response.json(); } catch {
        throw new Problem(502, 'The AI service returned an invalid response.');
      }
      const analysis = result?.choices?.[0]?.message?.content;
      if (typeof analysis !== 'string' || !analysis.trim()) {
        throw new Problem(502, 'The AI service returned an invalid response.');
      }
      return json({analysis: analysis.trim().slice(0, 12000), model, provider: 'groq',
        issue_source: input.issueParts ? 'Public GitHub issue' : 'Pasted issue text'});
    } catch (error) {
      if (error instanceof Problem) return json({detail: error.message}, error.status, error.headers);
      if (['AbortError', 'TimeoutError'].includes(error?.name)) {
        return json({detail: 'The AI request timed out. Please try again later.'}, 504);
      }
      // Never return upstream exception messages, provider bodies, or credentials.
      return json({detail: 'The service could not complete this request. Please try again later.'}, 502);
    }
  };
}
