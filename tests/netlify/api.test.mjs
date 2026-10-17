import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createApi} from '../../netlify/lib/api.mjs';
import sharedPrompt from '../../app/prompt.json' with {type: 'json'};

const KEY = 'synthetic-server-key';
const MODEL = 'llama-3.1-8b-instant';
const ISSUE = 'Add Windows PowerShell setup instructions for new contributors.';
const env = {GROQ_API_KEY: KEY};
const request = (data = {issue_text: ISSUE}, options = {}) => new Request('https://example.test/api/analyze', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data), ...options,
});
const response = (data, status = 200, headers = {}) => new Response(JSON.stringify(data), {status, headers});
const plan = {choices: [{message: {content: 'A useful contribution plan.'}}]};


test('server calls Groq once with private authorization and shared prompt', async () => {
  const calls = [];
  const api = createApi({env, fetchImpl: async (url, options) => {
    calls.push({url, options});
    assert.equal(url, 'https://api.groq.com/openai/v1/chat/completions');
    assert.equal(options.headers.Authorization, `Bearer ${KEY}`);
    assert.equal(options.redirect, 'manual');
    const body = JSON.parse(options.body);
    assert.equal(body.model, MODEL);
    assert.equal(body.messages[0].content, sharedPrompt.system_prompt);
    assert.ok(body.messages[1].content.includes(ISSUE));
    assert.equal(body.max_completion_tokens, 750);
    return response(plan);
  }});
  const result = await api(request(), 'analyze');
  assert.equal(result.status, 200);
  const data = await result.json();
  assert.equal(data.provider, 'groq');
  assert.equal(data.model, MODEL);
  assert.equal(data.analysis, plan.choices[0].message.content);
  assert.ok(!JSON.stringify(data).includes(KEY));
  assert.equal(calls.length, 1);
});


test('health and readiness check configuration without any model calls', async () => {
  const api = createApi({env, fetchImpl: () => assert.fail('Unexpected provider call')});
  const health = await api(new Request('https://example.test/health'), 'health');
  const data = await health.json();
  assert.equal(data.status, 'api_configured');
  assert.equal(data.public_mode, true);
  assert.ok(!JSON.stringify(data).includes(KEY));
  assert.equal((await api(new Request('https://example.test/ready'), 'ready')).status, 200);
});


test('missing key is explicit and never replaced by fake output', async () => {
  const api = createApi({env: {}, fetchImpl: () => assert.fail('Unexpected call')});
  assert.equal((await (await api(new Request('https://example.test/health'), 'health')).json()).status, 'api_key_missing');
  assert.equal((await api(new Request('https://example.test/ready'), 'ready')).status, 503);
  const result = await api(request(), 'analyze');
  assert.equal(result.status, 503);
  assert.ok(!(await result.text()).includes('DEMO ONLY'));
});

for (const data of [{}, {issue_text: 'fix'}, {issue_text: ISSUE, github_url: 'https://github.com/a/b/issues/1'},
                    {issue_text: ISSUE, model: 'another-model'}, {issue_text: 42}, {issue_text: null},
                    {issue_text: 'x'.repeat(6001)}, [], null]) {
  test(`rejects invalid input ${JSON.stringify(data).slice(0, 70)}`, async () => {
    const api = createApi({env, fetchImpl: () => assert.fail('Invalid input reached provider')});
    assert.equal((await api(request(data), 'analyze')).status, 422);
  });
}

for (const url of ['http://github.com/a/b/issues/1', 'https://evil.test/a/b/issues/1',
                  'https://github.com@evil.test/a/b/issues/1', 'https://github.com:443/a/b/issues/1',
                  'https://github.com/a/b/pull/1', 'https://github.com/a/b/issues/1?q=secret',
                  'https://github.com/a/b/issues/1#comment', 'https://github.com.evil.test/a/b/issues/1']) {
  test(`rejects unsafe issue URL ${url}`, async () => {
    const api = createApi({env, fetchImpl: () => assert.fail('Unsafe URL caused a network call')});
    assert.equal((await api(request({github_url: url}), 'analyze')).status, 422);
  });
}


test('public issue fetch uses fixed GitHub host and rejects pull requests', async () => {
  const calls = [];
  const api = createApi({env, fetchImpl: async (url, options) => {
    calls.push(url);
    if (url.startsWith('https://api.github.com/')) {
      assert.equal(url, 'https://api.github.com/repos/a/b/issues/123');
      assert.equal(options.redirect, 'manual');
      assert.equal(options.headers.Authorization, undefined);
      return response({title: 'Improve docs', body: ISSUE, labels: [{name: 'docs'}]});
    }
    assert.ok(JSON.parse(options.body).messages[1].content.includes('Repository: a/b'));
    return response(plan);
  }});
  const result = await api(request({github_url: 'https://github.com/a/b/issues/123'}), 'analyze');
  assert.equal(result.status, 200);
  assert.equal((await result.json()).issue_source, 'Public GitHub issue');
  assert.equal(calls.length, 2);
  const reject = createApi({env, fetchImpl: async () => response({pull_request: {}})});
  assert.equal((await reject(request({github_url: 'https://github.com/a/b/issues/123'}), 'analyze')).status, 422);
});

for (const [status, expected] of [[400, 503], [401, 503], [402, 503], [403, 503], [404, 503],
                                 [429, 429], [500, 502], [302, 502]]) {
  test(`provider status ${status} is sanitized and never retried`, async () => {
    let calls = 0;
    const api = createApi({env, fetchImpl: async () => {
      calls++;
      return response({error: KEY}, status, {'Retry-After': '12', Location: 'https://evil.test/'});
    }});
    const result = await api(request(), 'analyze');
    assert.equal(result.status, expected);
    assert.ok(!(await result.text()).includes(KEY));
    assert.equal(calls, 1);
    if (status === 429) assert.equal(result.headers.get('Retry-After'), '12');
  });
}

for (const data of [{}, {choices: []}, {choices: [null]}, {choices: [{message: {content: ''}}]},
                    {choices: [{message: {content: 42}}]}]) {
  test(`malformed model response ${JSON.stringify(data)}`, async () => {
    const api = createApi({env, fetchImpl: async () => response(data)});
    assert.equal((await api(request(), 'analyze')).status, 502);
  });
}


test('streamed request bodies are bounded without Content-Length', async () => {
  const api = createApi({env, fetchImpl: () => assert.fail('Oversized body reached provider')});
  const body = new ReadableStream({start(controller) {
    controller.enqueue(new Uint8Array(33000));
    controller.close();
  }});
  const result = await api(request(undefined, {body, duplex: 'half'}), 'analyze');
  assert.equal(result.status, 413);
});


test('malformed JSON and unsupported content type have clear errors', async () => {
  const api = createApi({env});
  assert.equal((await api(request(undefined, {body: '{broken'}), 'analyze')).status, 422);
  assert.equal((await api(request(undefined, {headers: {'Content-Type': 'text/plain'}}), 'analyze')).status, 415);
});


test('network exceptions and timeouts do not expose their messages', async () => {
  for (const [name, status] of [['TypeError', 502], ['TimeoutError', 504]]) {
    const api = createApi({env, fetchImpl: async () => {throw new DOMException(KEY, name);}});
    const result = await api(request(), 'analyze');
    assert.equal(result.status, status);
    assert.ok(!(await result.text()).includes(KEY));
  }
});


test('wrong method is rejected', async () => {
  const result = await createApi({env})(new Request('https://example.test/api/analyze'), 'analyze');
  assert.equal(result.status, 405);
  assert.equal(result.headers.get('Allow'), 'POST');
});


test('provider status checks the model list without generating or returning credentials', async () => {
  const api = createApi({env, fetchImpl: async (url, options) => {
    assert.equal(url, 'https://api.groq.com/openai/v1/models');
    assert.equal(options.headers.Authorization, `Bearer ${KEY}`);
    assert.equal(options.method, undefined);
    return response({data: [{id: MODEL, active: true}, {id: 'llama-3.3-70b-versatile', active: true}]});
  }});
  const result = await api(new Request('https://example.test/api/provider-status'), 'provider-status');
  assert.equal(result.status, 200);
  const data = await result.json();
  assert.equal(data.status, 'model_listed');
  assert.equal(data.model_available, true);
  assert.equal(data.provider_status, 200);
  assert.ok(!JSON.stringify(data).includes(KEY));
});


test('provider status reports missing model and only listed alternatives', async () => {
  const api = createApi({env, fetchImpl: async () => response({data: [
    {id: MODEL, active: false}, {id: 'llama-3.3-70b-versatile', active: true},
    {id: KEY, active: true},
  ]})});
  const result = await api(new Request('https://example.test/api/provider-status'), 'provider-status');
  const data = await result.json();
  assert.equal(data.status, 'model_not_listed');
  assert.equal(data.model_available, false);
  assert.deepEqual(data.alternative_models_listed, ['llama-3.3-70b-versatile']);
  assert.ok(!JSON.stringify(data).includes(KEY));
});


test('provider status rejects malformed model list', async () => {
  const api = createApi({env, fetchImpl: async () => response({data: null})});
  assert.equal((await api(new Request('https://example.test/api/provider-status'), 'provider-status')).status, 502);
});

for (const code of ['model_decommissioned', 'model_not_found', 'model_permission_blocked',
                    'organization_restricted', 'invalid_request_error']) {
  test(`provider error ${code} is distinguished without exposing its message`, async () => {
    const api = createApi({env, fetchImpl: async () => response({
      error: {code, type: 'invalid_request_error', message: KEY, param: 'model'},
    }, 400)});
    const result = await api(request(), 'analyze');
    const data = await result.json();
    assert.equal(result.status, 503);
    assert.equal(data.provider_error, code);
    assert.equal(data.provider_status, 400);
    assert.equal(data.provider_parameter, 'model');
    assert.ok(!JSON.stringify(data).includes(KEY));
  });
}


test('unknown provider codes and parameters are not echoed', async () => {
  const api = createApi({env, fetchImpl: async () => response({error: {
    code: KEY, param: KEY, type: KEY, message: KEY,
  }}, 400)});
  const data = await (await api(request(), 'analyze')).json();
  assert.equal(data.provider_error, 'unclassified');
  assert.equal(data.provider_parameter, undefined);
  assert.ok(!JSON.stringify(data).includes(KEY));
});
