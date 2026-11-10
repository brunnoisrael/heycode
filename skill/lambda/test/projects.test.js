const test = require('node:test');
const assert = require('node:assert');
const lambda = require('../index.js').handler;
const handler = (event, ctx) => new Promise((res, rej) => lambda(event, ctx, (e, r) => (e ? rej(e) : res(r))));

const OWNER = 'amzn1.ask.account.OWNER';
const DEVICE = 'amzn1.ask.device.OWNER';
const SKILL = 'amzn1.ask.skill.MINHA';

function envelope(request, appId = 'a') {
  return {
    version: '1.0',
    session: { new: false, sessionId: 's', application: { applicationId: appId }, user: { userId: OWNER } },
    context: { System: { application: { applicationId: appId }, user: { userId: OWNER }, device: { deviceId: DEVICE } } },
    request: { requestId: 'r', timestamp: new Date().toISOString(), locale: 'pt-BR', ...request },
  };
}
const intent = (name, slots = {}) => ({
  type: 'IntentRequest',
  intent: { name, slots: Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, { name: k, value: v }])) },
});
const speech = r => r.response.outputSpeech.ssml;

let calls;
function setup(reply = { speech: 'Vou criar o projeto meu-app. Confirma?', ok: true }) {
  process.env.BRIDGE_URL = 'http://bridge.test';
  process.env.BRIDGE_CONTROL_SECRET = 'c';
  process.env.BRIDGE_SECRET = 'segredo-de-agente';
  process.env.ALLOWED_USER_ID = OWNER;
  process.env.ALLOWED_DEVICE_ID = DEVICE;
  delete process.env.ALLOWED_SKILL_ID;
  calls = [];
  global.fetch = async (url, opts) => {
    calls.push({ url, opts });
    return { ok: true, json: async () => reply };
  };
}

test('CreateProjectIntent faz POST /projects e mantem a sessao aberta', async () => {
  setup();
  const r = await handler(envelope(intent('CreateProjectIntent',
    { nome: 'meu app', agente: 'claude', descricao: 'um site de receitas' })), {});
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].url, 'http://bridge.test/projects');
  assert.strictEqual(calls[0].opts.method, 'POST');
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body),
    { name: 'meu app', agent: 'claude', description: 'um site de receitas' });
  assert.match(speech(r), /Confirma\?/);
  assert.match(r.response.reprompt.outputSpeech.ssml, /Confirma\?/);
  assert.notStrictEqual(r.response.shouldEndSession, true);
});

test('CreateProjectIntent usa o id resolvido do agente', async () => {
  setup();
  const ev = envelope(intent('CreateProjectIntent', { nome: 'x', agente: 'o codigo', descricao: 'd' }));
  ev.request.intent.slots.agente.resolutions = { resolutionsPerAuthority: [
    { status: { code: 'ER_SUCCESS_MATCH' }, values: [{ value: { name: 'codex', id: 'codex' } }] }] };
  await handler(ev, {});
  assert.strictEqual(JSON.parse(calls[0].opts.body).agent, 'codex');
});

test('CreateProjectIntent com slot faltando ou agente invalido nao chama a ponte', async () => {
  setup();
  const r1 = await handler(envelope(intent('CreateProjectIntent', { nome: 'x', agente: 'claude' })), {});
  const r2 = await handler(envelope(intent('CreateProjectIntent', { nome: 'x', agente: 'zzz', descricao: 'd' })), {});
  assert.strictEqual(calls.length, 0);
  assert.notStrictEqual(r1.response.shouldEndSession, true);
  assert.notStrictEqual(r2.response.shouldEndSession, true);
});

test('CreateProjectIntent com ok false fala a resposta e nao pede confirmacao', async () => {
  setup({ speech: 'Esse projeto já existe.', ok: false });
  const r = await handler(envelope(intent('CreateProjectIntent',
    { nome: 'x', agente: 'claude', descricao: 'd' })), {});
  assert.match(speech(r), /já existe/);
  assert.doesNotMatch(speech(r), /Confirma\?/);
});

test('ConfirmIntent chama POST /confirm', async () => {
  setup({ speech: 'Criado.' });
  const r = await handler(envelope(intent('ConfirmIntent')), {});
  assert.strictEqual(calls[0].url, 'http://bridge.test/confirm');
  assert.strictEqual(calls[0].opts.method, 'POST');
  assert.match(speech(r), /Criado/);
});

test('CancelDictationIntent chama POST /cancel', async () => {
  setup({ speech: 'Cancelado.' });
  await handler(envelope(intent('CancelDictationIntent')), {});
  assert.strictEqual(calls[0].url, 'http://bridge.test/cancel');
  assert.strictEqual(calls[0].opts.method, 'POST');
});

test('ALLOWED_SKILL_ID diferente do applicationId nega sem chamar a ponte', async () => {
  setup();
  process.env.ALLOWED_SKILL_ID = SKILL;
  const r = await handler(envelope(intent('StatusIntent'), 'amzn1.ask.skill.OUTRA'), {});
  assert.strictEqual(calls.length, 0);
  assert.match(speech(r), /Acesso negado/);
  assert.strictEqual(r.response.shouldEndSession, true);
  delete process.env.ALLOWED_SKILL_ID;
});

test('ALLOWED_SKILL_ID igual ao applicationId segue', async () => {
  setup({ speech: 'ok' });
  process.env.ALLOWED_SKILL_ID = SKILL;
  await handler(envelope(intent('StatusIntent'), SKILL), {});
  assert.strictEqual(calls.length, 1);
  delete process.env.ALLOWED_SKILL_ID;
});

test('ALLOWED_SKILL_ID ausente segue, mas userId continua obrigatorio', async () => {
  setup({ speech: 'ok' });
  await handler(envelope(intent('StatusIntent')), {});
  assert.strictEqual(calls.length, 1);
  process.env.ALLOWED_USER_ID = 'outro';
  const r = await handler(envelope(intent('StatusIntent')), {});
  assert.strictEqual(calls.length, 1);
  assert.match(speech(r), /Acesso negado/);
  process.env.ALLOWED_USER_ID = OWNER;
});

test('intents antigos intactos: AskAgentIntent ainda usa /dictation', async () => {
  setup();
  await handler(envelope(intent('AskAgentIntent', { agente: 'codex', instrucao: 'x' })), {});
  assert.strictEqual(calls[0].url, 'http://bridge.test/dictation');
});
