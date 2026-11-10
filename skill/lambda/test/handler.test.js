const test = require('node:test');
const assert = require('node:assert');
const lambda = require('../index.js').handler;
const handler = (event, ctx) => new Promise((res, rej) => lambda(event, ctx, (e, r) => (e ? rej(e) : res(r))));

const OWNER = 'amzn1.ask.account.OWNER';
const DEVICE = 'amzn1.ask.device.OWNER';

function envelope(request, { userId = OWNER, deviceId = DEVICE } = {}) {
  return {
    version: '1.0',
    session: { new: true, sessionId: 's', application: { applicationId: 'a' }, user: { userId } },
    context: { System: { application: { applicationId: 'a' }, user: { userId }, device: { deviceId } } },
    request: { requestId: 'r', timestamp: new Date().toISOString(), locale: 'pt-BR', ...request },
  };
}
const intent = (name, slots = {}) => ({
  type: 'IntentRequest',
  intent: {
    name,
    slots: Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, { name: k, value: v }])),
  },
});
const speech = r => r.response.outputSpeech.ssml;

let calls;
function setup() {
  process.env.BRIDGE_URL = 'http://bridge.test';
  process.env.BRIDGE_SECRET = 's';
  process.env.ALLOWED_USER_ID = OWNER;
  process.env.ALLOWED_DEVICE_ID = DEVICE;
  calls = [];
  global.fetch = async (url, opts) => {
    calls.push({ url, opts });
    return { ok: true, json: async () => ({ speech: 'ok falado', actionable: false }) };
  };
}
const silenceLog = () => { const o = console.log; console.log = () => {}; const e = console.error; console.error = () => {}; return () => { console.log = o; console.error = e; }; };

test('usuario diferente recebe acesso negado e nenhum fetch', async () => {
  setup();
  const restore = silenceLog();
  const r = await handler(envelope(intent('StatusIntent'), { userId: 'outro' }), {});
  restore();
  assert.match(speech(r), /acesso/i);
  assert.strictEqual(calls.length, 0);
});

test('dispositivo diferente recebe acesso negado', async () => {
  setup();
  const restore = silenceLog();
  const r = await handler(envelope(intent('StatusIntent'), { deviceId: 'outro' }), {});
  restore();
  assert.match(speech(r), /acesso/i);
  assert.strictEqual(calls.length, 0);
});

test('ALLOWED_USER_ID ausente recusa, pede configuracao e loga os IDs', async () => {
  setup();
  delete process.env.ALLOWED_USER_ID;
  const logs = [];
  const o = console.log; console.log = (...a) => logs.push(a.join(' '));
  const r = await handler(envelope(intent('StatusIntent')), {});
  console.log = o;
  assert.match(speech(r), /configur/i);
  assert.strictEqual(calls.length, 0);
  const all = logs.join('\n');
  assert.ok(all.includes(OWNER) && all.includes(DEVICE));
});

test('ALLOWED_DEVICE_ID ausente tambem recusa e loga', async () => {
  setup();
  delete process.env.ALLOWED_DEVICE_ID;
  const logs = [];
  const o = console.log; console.log = (...a) => logs.push(a.join(' '));
  const r = await handler(envelope(intent('StatusIntent')), {});
  console.log = o;
  assert.match(speech(r), /configur/i);
  assert.strictEqual(calls.length, 0);
  assert.ok(logs.join('\n').includes(DEVICE));
});

test('allowlist e lida a cada requisicao', async () => {
  setup();
  const restore = silenceLog();
  process.env.ALLOWED_USER_ID = 'outro';
  const r1 = await handler(envelope(intent('StatusIntent')), {});
  process.env.ALLOWED_USER_ID = OWNER;
  const r2 = await handler(envelope(intent('StatusIntent')), {});
  restore();
  assert.match(speech(r1), /acesso/i);
  assert.match(speech(r2), /ok falado/);
});

test('StatusIntent continua funcionando para o dono', async () => {
  setup();
  const r = await handler(envelope(intent('StatusIntent')), {});
  assert.match(speech(r), /ok falado/);
  assert.strictEqual(calls[0].url, 'http://bridge.test/status');
  assert.strictEqual(calls[0].opts.headers['x-secret'], 's');
});

for (const [falado, esperado] of [['automático', 'auto'], ['tudo liberado', 'auto'], ['manual', 'manual'], ['decisões', 'decisoes']]) {
  test(`SetModeIntent ${falado} -> ${esperado}`, async () => {
    setup();
    const r = await handler(envelope(intent('SetModeIntent', { modo: falado })), {});
    assert.strictEqual(calls.length, 1);
    assert.strictEqual(calls[0].url, 'http://bridge.test/mode');
    assert.strictEqual(calls[0].opts.method, 'POST');
    assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { mode: esperado });
    assert.match(speech(r), /ok falado/);
  });
}

test('SetModeIntent usa o id da resolucao de entidade quando existe', async () => {
  setup();
  const env = envelope(intent('SetModeIntent', { modo: 'tudo liberado' }));
  env.request.intent.slots.modo.resolutions = { resolutionsPerAuthority: [{ status: { code: 'ER_SUCCESS_MATCH' }, values: [{ value: { name: 'auto', id: 'auto' } }] }] };
  await handler(env, {});
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { mode: 'auto' });
});

test('SetModeIntent com modo desconhecido nao chama a ponte e pergunta de novo', async () => {
  setup();
  const r = await handler(envelope(intent('SetModeIntent', { modo: 'banana' })), {});
  assert.strictEqual(calls.length, 0);
  assert.match(speech(r), /manual/);
});

test('SetModeIntent sem slot nao chama a ponte', async () => {
  setup();
  await handler(envelope(intent('SetModeIntent')), {});
  assert.strictEqual(calls.length, 0);
});

test('ReportOnEndIntent ligar -> true, desligar -> false, sem slot -> true', async () => {
  setup();
  await handler(envelope(intent('ReportOnEndIntent', { ligado: 'ligar' })), {});
  await handler(envelope(intent('ReportOnEndIntent', { ligado: 'desligar' })), {});
  await handler(envelope(intent('ReportOnEndIntent')), {});
  assert.deepStrictEqual(calls.map(c => JSON.parse(c.opts.body)),
    [{ report_on_end: true }, { report_on_end: false }, { report_on_end: true }]);
  assert.ok(calls.every(c => c.url === 'http://bridge.test/mode' && c.opts.method === 'POST'));
});

test('modelo de interacao define MODO, LIGADO, SetModeIntent e ReportOnEndIntent', () => {
  const lm = require('../../interaction-model-pt-BR.json').interactionModel.languageModel;
  const modo = lm.types.find(t => t.name === 'MODO');
  const ids = modo.values.map(v => v.id);
  assert.deepStrictEqual(ids.sort(), ['auto', 'decisoes', 'manual']);
  const auto = modo.values.find(v => v.id === 'auto').name;
  assert.ok(['automático', 'tudo liberado'].every(s => auto.value === s || auto.synonyms.includes(s)));
  assert.deepStrictEqual(lm.types.find(t => t.name === 'LIGADO').values.map(v => v.name.value).sort(), ['desligar', 'ligar']);
  const set = lm.intents.find(i => i.name === 'SetModeIntent');
  assert.strictEqual(set.slots[0].type, 'MODO');
  assert.ok(set.samples.includes('modo {modo}'));
  const rep = lm.intents.find(i => i.name === 'ReportOnEndIntent');
  assert.strictEqual(rep.slots[0].name, 'ligado');
  assert.ok(rep.samples.includes('avisar no fim do ciclo') && rep.samples.includes('{ligado} aviso de fim de ciclo'));
});
