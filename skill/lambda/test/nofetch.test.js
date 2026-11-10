// A Alexa-hosted roda em Node 16, sem fetch global. Estes testes tiram o fetch e falam com um servidor HTTP real.
const test = require('node:test');
const assert = require('node:assert');
const http = require('node:http');
const lambda = require('../index.js').handler;
const { httpFetch } = require('../index.js');
const handler = (event, ctx) => new Promise((res, rej) => lambda(event, ctx, (e, r) => (e ? rej(e) : res(r))));

const OWNER = 'amzn1.ask.account.OWNER';
const DEVICE = 'amzn1.ask.device.OWNER';

function envelope(request) {
  return {
    version: '1.0',
    session: { new: false, sessionId: 's', application: { applicationId: 'a' }, user: { userId: OWNER } },
    context: { System: { application: { applicationId: 'a' }, user: { userId: OWNER }, device: { deviceId: DEVICE } } },
    request: { requestId: 'r', timestamp: new Date().toISOString(), locale: 'pt-BR', ...request },
  };
}
const intent = (name, slots = {}) => ({
  type: 'IntentRequest',
  intent: { name, slots: Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, { name: k, value: v }])) },
});

async function withServer(respond, run) {
  const seen = [];
  const server = http.createServer((req, res) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      seen.push({ method: req.method, url: req.url, headers: req.headers, body: Buffer.concat(chunks).toString('utf8') });
      respond(req, res);
    });
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const savedFetch = global.fetch;
  delete global.fetch;
  process.env.BRIDGE_URL = `http://127.0.0.1:${server.address().port}`;
  process.env.BRIDGE_CONTROL_SECRET = 'controle';
  process.env.ALLOWED_USER_ID = OWNER;
  process.env.ALLOWED_DEVICE_ID = DEVICE;
  delete process.env.ALLOWED_SKILL_ID;
  try {
    return await run(seen);
  } finally {
    global.fetch = savedFetch;
    await new Promise(r => server.close(r));
  }
}
const json = (res, status, obj) => { res.writeHead(status, { 'content-type': 'application/json' }); res.end(JSON.stringify(obj)); };

test('sem fetch global, GET /status vai pelo http nativo com o x-secret de controle', async () => {
  await withServer((req, res) => json(res, 200, { speech: 'Tudo parado, sem ação.' }), async seen => {
    const r = await handler(envelope(intent('StatusIntent')), {});
    assert.strictEqual(seen.length, 1);
    assert.strictEqual(seen[0].method, 'GET');
    assert.strictEqual(seen[0].url, '/status');
    assert.strictEqual(seen[0].headers['x-secret'], 'controle');
    assert.match(r.response.outputSpeech.ssml, /Tudo parado, sem ação\./);
  });
});

test('sem fetch global, POST /dictation envia o corpo JSON em UTF-8 com content-length correto', async () => {
  await withServer((req, res) => json(res, 200, { speech: 'Entendi. Confirma?' }), async seen => {
    await handler(envelope(intent('AskAgentIntent', { agente: 'claude', instrucao: 'corrige a função de divisão' })), {});
    assert.strictEqual(seen[0].method, 'POST');
    assert.strictEqual(seen[0].url, '/dictation');
    assert.strictEqual(seen[0].headers['content-type'], 'application/json');
    assert.strictEqual(Number(seen[0].headers['content-length']), Buffer.byteLength(seen[0].body));
    assert.deepStrictEqual(JSON.parse(seen[0].body), { agent: 'claude', text: 'corrige a função de divisão' });
  });
});

test('sem fetch global, resposta 401 da ponte vira a fala de erro, sem vazar o corpo', async () => {
  await withServer((req, res) => json(res, 401, { detail: 'segredo-invalido' }), async () => {
    const r = await handler(envelope(intent('StatusIntent')), {});
    assert.match(r.response.outputSpeech.ssml, /Não consegui falar com o seu computador/);
    assert.doesNotMatch(r.response.outputSpeech.ssml, /segredo-invalido/);
  });
});

test('httpFetch respeita o sinal de abort', async () => {
  await withServer(() => { /* nunca responde */ }, async () => {
    const ctrl = new AbortController();
    const p = httpFetch(process.env.BRIDGE_URL + '/status', { signal: ctrl.signal });
    setTimeout(() => ctrl.abort(), 50);
    await assert.rejects(p);
  });
});
