const test = require('node:test');
const assert = require('node:assert');
const lambda = require('../index.js').handler;
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
const speech = r => r.response.outputSpeech.ssml;

let calls;
function setup(reply = { speech: 'Entendi: x. Confirma?' }) {
  process.env.BRIDGE_URL = 'http://bridge.test';
  process.env.BRIDGE_CONTROL_SECRET = 'c';
  process.env.BRIDGE_SECRET = 'segredo-de-agente';
  process.env.ALLOWED_USER_ID = OWNER;
  process.env.ALLOWED_DEVICE_ID = DEVICE;
  calls = [];
  global.fetch = async (url, opts) => {
    calls.push({ url, opts });
    return { ok: true, json: async () => reply };
  };
}

test('AskAgentIntent faz POST /dictation com agent e text e mantem a sessao aberta', async () => {
  setup();
  const r = await handler(envelope(intent('AskAgentIntent', { agente: 'codex', instrucao: 'corrige o bug' })), {});
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].url, 'http://bridge.test/dictation');
  assert.strictEqual(calls[0].opts.method, 'POST');
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { agent: 'codex', text: 'corrige o bug' });
  assert.match(speech(r), /Confirma\?/);
  assert.match(r.response.reprompt.outputSpeech.ssml, /Confirma\?/);
  assert.notStrictEqual(r.response.shouldEndSession, true);
});

test('AskAgentIntent usa o id resolvido do slot agente', async () => {
  setup();
  const ev = envelope(intent('AskAgentIntent', { agente: 'o codigo', instrucao: 'x' }));
  ev.request.intent.slots.agente.resolutions = { resolutionsPerAuthority: [
    { status: { code: 'ER_SUCCESS_MATCH' }, values: [{ value: { name: 'codex', id: 'codex' } }] }] };
  await handler(ev, {});
  assert.strictEqual(JSON.parse(calls[0].opts.body).agent, 'codex');
});

test('AskAgentIntent sem instrucao ou agente nao chama a ponte', async () => {
  setup();
  const r = await handler(envelope(intent('AskAgentIntent', { agente: 'claude' })), {});
  assert.strictEqual(calls.length, 0);
  assert.ok(r.response.reprompt);
  const r2 = await handler(envelope(intent('AskAgentIntent', { instrucao: 'faz x' })), {});
  assert.strictEqual(calls.length, 0);
  assert.ok(r2.response.reprompt);
});

test('ConfirmIntent faz POST /confirm', async () => {
  setup({ speech: 'Enviado ao claude.', run_id: 3 });
  const r = await handler(envelope(intent('ConfirmIntent')), {});
  assert.strictEqual(calls[0].url, 'http://bridge.test/confirm');
  assert.strictEqual(calls[0].opts.method, 'POST');
  assert.match(speech(r), /Enviado/);
});

test('CancelDictationIntent faz POST /cancel', async () => {
  setup({ speech: 'Cancelado.' });
  const r = await handler(envelope(intent('CancelDictationIntent')), {});
  assert.strictEqual(calls[0].url, 'http://bridge.test/cancel');
  assert.match(speech(r), /Cancelado/);
});

test('modelo de interacao declara os intents e o tipo AGENTE', () => {
  const m = require('../../interaction-model-pt-BR.json').interactionModel.languageModel;
  const names = m.intents.map(i => i.name);
  for (const n of ['AskAgentIntent', 'ConfirmIntent', 'CancelDictationIntent', 'SetModeIntent']) assert.ok(names.includes(n), n);
  const t = m.types.find(x => x.name === 'AGENTE');
  assert.deepStrictEqual(t.values.map(v => v.id), ['claude', 'codex', 'aider']);
  const ask = m.intents.find(i => i.name === 'AskAgentIntent');
  assert.deepStrictEqual(ask.slots.map(s => [s.name, s.type]), [['agente', 'AGENTE'], ['instrucao', 'AMAZON.SearchQuery'], ['projeto', 'NOME_PROJETO']]);
});
