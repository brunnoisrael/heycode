const test = require('node:test');
const assert = require('node:assert');
const lambda = require('../index.js').handler;
const handler = (event, ctx) => new Promise((res, rej) => lambda(event, ctx, (e, r) => (e ? rej(e) : res(r))));

const OWNER = 'amzn1.ask.account.OWNER';
const DEVICE = 'amzn1.ask.device.OWNER';

function envelope(request, attributes) {
  return {
    version: '1.0',
    session: { new: false, sessionId: 's', application: { applicationId: 'a' }, user: { userId: OWNER }, attributes },
    context: { System: { application: { applicationId: 'a' }, user: { userId: OWNER }, device: { deviceId: DEVICE } } },
    request: { requestId: 'r', timestamp: new Date().toISOString(), locale: 'pt-BR', ...request },
  };
}
const intent = (name, slots = {}) => ({
  type: 'IntentRequest',
  intent: { name, slots: Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, { name: k, value: v }])) },
});
const elicited = r => (r.response.directives || []).find(d => d.type === 'Dialog.ElicitSlot');

let calls;
function setup(reply = { speech: 'Entendi: x. Confirma?' }) {
  process.env.BRIDGE_URL = 'http://bridge.test';
  process.env.BRIDGE_CONTROL_SECRET = 'c';
  process.env.ALLOWED_USER_ID = OWNER;
  process.env.ALLOWED_DEVICE_ID = DEVICE;
  delete process.env.ALLOWED_SKILL_ID;
  calls = [];
  global.fetch = async (url, opts) => {
    calls.push({ url, opts });
    return { ok: true, json: async () => reply };
  };
}

test('resposta livre pede texto, relê e confirma somente a pergunta ouvida', async () => {
  setup({ ok: true, token: 'abc', speech: 'Entendi: SQLite. Confirma?' });
  const attrs = { pending_kind: 'question', approval_id: 42 };
  const first = await handler(envelope(intent('AnswerQuestionIntent'), attrs), {});
  assert.strictEqual(elicited(first).slotToElicit, 'resposta');
  assert.strictEqual(calls.length, 0);
  const second = await handler(envelope(intent('AnswerQuestionIntent', { resposta: 'SQLite' }), attrs), {});
  assert.strictEqual(calls[0].url, 'http://bridge.test/answer/preview');
  assert.deepStrictEqual(second.sessionAttributes.free_answer, { approval_id: 42, token: 'abc' });
  await handler(envelope(intent('ConfirmIntent'), second.sessionAttributes), {});
  assert.strictEqual(calls[1].url, 'http://bridge.test/answer/confirm');
  assert.deepStrictEqual(JSON.parse(calls[1].opts.body), { approval_id: 42, token: 'abc' });
});

test('resposta sem pergunta e cancelamento nunca enviam resposta', async () => {
  setup();
  await handler(envelope(intent('AnswerQuestionIntent', { resposta: 'x' }), {}), {});
  assert.strictEqual(calls.length, 0);
  const r = await handler(envelope(intent('CancelDictationIntent'),
    { pending_kind: 'question', approval_id: 3, free_answer: { approval_id: 3, text: 'x' } }), {});
  assert.strictEqual(r.sessionAttributes.free_answer, undefined);
  assert.strictEqual(calls.length, 0);
});

test('AskAgentIntent so com agente pede a instrucao com ElicitSlot e guarda o agente na sessao', async () => {
  setup();
  const r = await handler(envelope(intent('AskAgentIntent', { agente: 'codex' })), {});
  assert.strictEqual(calls.length, 0);
  assert.strictEqual(elicited(r).slotToElicit, 'instrucao');
  assert.match(r.response.outputSpeech.ssml, /instrução para o codex/);
  assert.deepStrictEqual(r.sessionAttributes.ask, { agent: 'codex' });
  assert.notStrictEqual(r.response.shouldEndSession, true);
});

test('AskAgentIntent com agente e projeto guarda os dois na sessao', async () => {
  setup();
  const r = await handler(envelope(intent('AskAgentIntent', { agente: 'claude', projeto: 'painel' })), {});
  assert.strictEqual(calls.length, 0);
  assert.strictEqual(elicited(r).slotToElicit, 'instrucao');
  assert.deepStrictEqual(r.sessionAttributes.ask, { agent: 'claude', project: 'painel' });
});

test('segundo turno do AskAgentIntent usa agente e projeto da sessao e limpa a sessao', async () => {
  setup();
  const r = await handler(envelope(intent('AskAgentIntent', { instrucao: 'roda os testes' }),
    { ask: { agent: 'codex', project: 'painel' }, approval_id: 7 }), {});
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].url, 'http://bridge.test/dictation');
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { agent: 'codex', text: 'roda os testes', project: 'painel' });
  assert.strictEqual(r.sessionAttributes.ask, undefined);
  assert.strictEqual(r.sessionAttributes.approval_id, 7);
  assert.match(r.response.reprompt.outputSpeech.ssml, /Confirma\?/);
});

test('segundo turno do AskAgentIntent com os slots devolvidos pela Alexa prefere os slots', async () => {
  setup();
  await handler(envelope(intent('AskAgentIntent', { agente: 'aider', instrucao: 'faz x' }), { ask: { agent: 'codex' } }), {});
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { agent: 'aider', text: 'faz x' });
});

test('AskAgentIntent sem agente nao pede a instrucao nem chama a ponte', async () => {
  setup();
  const r = await handler(envelope(intent('AskAgentIntent', { instrucao: 'faz x' })), {});
  assert.strictEqual(calls.length, 0);
  assert.strictEqual(elicited(r), undefined);
  assert.ok(r.response.reprompt);
});

test('CreateProjectIntent com nome e agente pede a descricao com ElicitSlot', async () => {
  setup();
  const r = await handler(envelope(intent('CreateProjectIntent', { nome: 'meu app', agente: 'claude' })), {});
  assert.strictEqual(calls.length, 0);
  assert.strictEqual(elicited(r).slotToElicit, 'descricao');
  assert.deepStrictEqual(r.sessionAttributes.create, { name: 'meu app', agent: 'claude' });
});

test('segundo turno do CreateProjectIntent usa nome e agente da sessao', async () => {
  setup();
  const r = await handler(envelope(intent('CreateProjectIntent', { descricao: 'um site de receitas' }),
    { create: { name: 'meu app', agent: 'claude' } }), {});
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].url, 'http://bridge.test/projects');
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body),
    { name: 'meu app', agent: 'claude', description: 'um site de receitas' });
  assert.strictEqual(r.sessionAttributes.create, undefined);
});

test('modelo: nenhuma frase mistura slot de frase com outro slot, e toda frase com slot de frase tem texto fixo', () => {
  const lm = require('../../interaction-model-pt-BR.json').interactionModel.languageModel;
  for (const i of lm.intents) {
    const phrase = (i.slots || []).filter(s => s.type === 'AMAZON.SearchQuery').map(s => `{${s.name}}`);
    for (const sample of i.samples || []) {
      const used = sample.match(/\{[^}]+\}/g) || [];
      const hasPhrase = used.some(u => phrase.includes(u));
      if (!hasPhrase) continue;
      assert.strictEqual(used.length, 1, `${i.name}: "${sample}"`);
      assert.ok(sample.replace(/\{[^}]+\}/g, '').trim().length > 0, `${i.name}: "${sample}" sem texto fixo`);
    }
  }
});

test('modelo: dialogo declara os slots de frase como pedidos pela skill, com prompts existentes', () => {
  const im = require('../../interaction-model-pt-BR.json').interactionModel;
  const promptIds = im.prompts.map(p => p.id);
  for (const [name, slot] of [['AskAgentIntent', 'instrucao'], ['CreateProjectIntent', 'descricao']]) {
    const lmIntent = im.languageModel.intents.find(i => i.name === name);
    const d = im.dialog.intents.find(i => i.name === name);
    assert.ok(d, name);
    assert.strictEqual(d.delegationStrategy, 'SKILL_RESPONSE');
    assert.deepStrictEqual(d.slots.map(s => [s.name, s.type]), lmIntent.slots.map(s => [s.name, s.type]));
    const s = d.slots.find(x => x.name === slot);
    assert.strictEqual(s.elicitationRequired, true);
    assert.ok(promptIds.includes(s.prompts.elicitation), s.prompts.elicitation);
    assert.ok(lmIntent.samples.length > 0 && !lmIntent.samples.some(x => x.includes(`{${slot}}`)));
  }
});
