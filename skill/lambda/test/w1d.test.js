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
const speech = r => r.response.outputSpeech.ssml;

let calls;
function setup(reply) {
  process.env.BRIDGE_URL = 'http://bridge.test';
  process.env.BRIDGE_CONTROL_SECRET = 'controle';
  process.env.BRIDGE_SECRET = 'agente';
  process.env.ALLOWED_USER_ID = OWNER;
  process.env.ALLOWED_DEVICE_ID = DEVICE;
  calls = [];
  global.fetch = async (url, opts) => {
    calls.push({ url, opts });
    return { ok: true, json: async () => reply };
  };
}

test('a Lambda usa BRIDGE_CONTROL_SECRET no x-secret, nunca o segredo de agente', async () => {
  setup({ speech: 'x' });
  await handler(envelope(intent('StatusIntent')), {});
  assert.strictEqual(calls[0].opts.headers['x-secret'], 'controle');
});

test('PendingIntent guarda approval_id na sessao', async () => {
  setup({ speech: 'Quer rodar npm test?', actionable: true, approval_id: 42 });
  const r = await handler(envelope(intent('PendingIntent')), {});
  assert.strictEqual(r.sessionAttributes.approval_id, 42);
  assert.ok(r.response.reprompt);
});

test('PendingIntent sem pendencia (approval_id null) limpa o id da sessao', async () => {
  setup({ speech: 'Nada pendente.', actionable: false, approval_id: null });
  const r = await handler(envelope(intent('PendingIntent'), { approval_id: 7 }), {});
  assert.ok(!r.sessionAttributes || r.sessionAttributes.approval_id == null);
});

test('ApproveIntent envia approval_id da sessao em /decide', async () => {
  setup({ speech: 'Aprovado.' });
  const r = await handler(envelope(intent('ApproveIntent', { pin: '1234' }), { approval_id: 42 }), {});
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { approve: true, pin: '1234', approval_id: 42 });
  assert.match(speech(r), /Aprovado/);
});

test('DenyIntent envia approval_id da sessao em /decide', async () => {
  setup({ speech: 'Negado.' });
  await handler(envelope(intent('DenyIntent'), { approval_id: 42 }), {});
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { approve: false, approval_id: 42 });
});

test('Aprovar sem approval_id na sessao pede para perguntar primeiro e nao envia nada', async () => {
  setup({ speech: 'x' });
  const r = await handler(envelope(intent('ApproveIntent', { pin: '1234' })), {});
  assert.strictEqual(calls.length, 0);
  assert.match(speech(r), /Pergunte primeiro o que está pendente\./);
});

test('Negar sem approval_id na sessao pede para perguntar primeiro e nao envia nada', async () => {
  setup({ speech: 'x' });
  const r = await handler(envelope(intent('DenyIntent')), {});
  assert.strictEqual(calls.length, 0);
  assert.match(speech(r), /Pergunte primeiro o que está pendente\./);
});

test('Aprovar sem PIN mantem o approval_id na sessao ao pedir o PIN', async () => {
  setup({ speech: 'x' });
  const r = await handler(envelope(intent('ApproveIntent'), { approval_id: 9 }), {});
  assert.strictEqual(calls.length, 0);
  assert.match(speech(r), /PIN/);
  assert.strictEqual(r.sessionAttributes.approval_id, 9);
});

test('SetModeIntent fala a speech real da ponte', async () => {
  setup({ mode: 'auto', report_on_end: true, speech: 'Modo automático ativado para todos os agentes.' });
  const r = await handler(envelope(intent('SetModeIntent', { modo: 'automático' })), {});
  assert.match(speech(r), /Modo automático ativado para todos os agentes\./);
});

test('SetModeIntent sem speech na resposta fala frase padrao (nao fica mudo)', async () => {
  setup({ mode: 'auto', report_on_end: true });
  const r = await handler(envelope(intent('SetModeIntent', { modo: 'automático' })), {});
  assert.match(speech(r), /Modo/);
  assert.doesNotMatch(speech(r), /undefined/);
});

test('ReportOnEndIntent fala speech da ponte e, sem speech, frase padrao', async () => {
  setup({ mode: 'manual', report_on_end: false, speech: 'Aviso de fim de ciclo desligado.' });
  const r1 = await handler(envelope(intent('ReportOnEndIntent', { ligado: 'desligar' })), {});
  assert.match(speech(r1), /Aviso de fim de ciclo desligado\./);
  setup({ mode: 'manual', report_on_end: true });
  const r2 = await handler(envelope(intent('ReportOnEndIntent', { ligado: 'ligar' })), {});
  assert.match(speech(r2), /ligado/i);
  assert.doesNotMatch(speech(r2), /undefined/);
});

test('AskAgentIntent com projeto envia project (id resolvido)', async () => {
  setup({ speech: 'Entendi. Confirma?' });
  const ev = envelope(intent('AskAgentIntent', { agente: 'claude', instrucao: 'roda os testes', projeto: 'meu app' }));
  ev.request.intent.slots.projeto.resolutions = { resolutionsPerAuthority: [
    { status: { code: 'ER_SUCCESS_MATCH' }, values: [{ value: { name: 'meu app', id: 'meu-app' } }] }] };
  await handler(ev, {});
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { agent: 'claude', text: 'roda os testes', project: 'meu-app' });
});

test('AskAgentIntent com projeto sem resolucao envia o texto falado', async () => {
  setup({ speech: 'ok' });
  await handler(envelope(intent('AskAgentIntent', { agente: 'claude', instrucao: 'x', projeto: 'loja nova' })), {});
  assert.strictEqual(JSON.parse(calls[0].opts.body).project, 'loja nova');
});

test('AskAgentIntent sem projeto nao envia a chave project', async () => {
  setup({ speech: 'ok' });
  await handler(envelope(intent('AskAgentIntent', { agente: 'claude', instrucao: 'x' })), {});
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { agent: 'claude', text: 'x' });
});

test('AskAgentIntent: ok false (projeto inexistente) fala a speech e nao pede confirmacao', async () => {
  setup({ ok: false, speech: 'Não achei o projeto loja.' });
  const r = await handler(envelope(intent('AskAgentIntent', { agente: 'claude', instrucao: 'x', projeto: 'loja' })), {});
  assert.match(speech(r), /Não achei o projeto loja\./);
  assert.ok(!r.response.reprompt);
});

test('CancelRunIntent faz POST /runs/latest/cancel e fala a speech', async () => {
  setup({ speech: 'Nenhum agente rodando.' });
  const r = await handler(envelope(intent('CancelRunIntent')), {});
  assert.strictEqual(calls[0].url, 'http://bridge.test/runs/latest/cancel');
  assert.strictEqual(calls[0].opts.method, 'POST');
  assert.match(speech(r), /Nenhum agente rodando\./);
});

test('SendInstructionIntent vira ditado para o agente aberto, com confirmacao e sem agente fixo', async () => {
  setup({ speech: 'Entendi, para o agente aberto no projeto painel: use tabs. Confirma?', ok: true });
  const r = await handler(envelope(intent('SendInstructionIntent', { instrucao: 'use tabs' })), {});
  assert.strictEqual(calls.length, 1);
  assert.strictEqual(calls[0].url, 'http://bridge.test/dictation');
  assert.strictEqual(calls[0].opts.method, 'POST');
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { target: 'aberto', text: 'use tabs' });
  assert.strictEqual(calls[0].opts.headers['x-secret'], 'controle'); // segredo de controle, nunca o de agente
  assert.match(speech(r), /agente aberto no projeto painel/);
  assert.match(r.response.reprompt.outputSpeech.ssml, /Confirma\?/);
  assert.notStrictEqual(r.response.shouldEndSession, true);
});

test('SendInstructionIntent sem agente aberto fala a recusa e nao pede confirmacao', async () => {
  setup({ speech: 'Não achei nenhum agente aberto com atividade recente. Nada foi enviado.', ok: false });
  const r = await handler(envelope(intent('SendInstructionIntent', { instrucao: 'use tabs' })), {});
  assert.match(speech(r), /Nada foi enviado/);
  assert.strictEqual(r.response.reprompt, undefined);
});

test('SendInstructionIntent e depois ConfirmIntent: a fila e da ponte, a Lambda nao chama /instruction', async () => {
  setup({ speech: 'Entendi. Confirma?', ok: true });
  await handler(envelope(intent('SendInstructionIntent', { instrucao: 'use tabs' })), {});
  setup({ speech: 'Instrução na fila do agente aberto no projeto painel. Ele recebe ao terminar o turno atual.', instruction_id: 3 });
  const r = await handler(envelope(intent('ConfirmIntent')), {});
  assert.deepStrictEqual(calls.map(c => c.url), ['http://bridge.test/confirm']);
  assert.match(speech(r), /Instrução na fila do agente aberto/);
});

test('AskAgentIntent continua sem target: peca ao agente segue iniciando run', async () => {
  setup({ speech: 'Entendi, para o claude: x. Confirma?' });
  await handler(envelope(intent('AskAgentIntent', { agente: 'claude', instrucao: 'x' })), {});
  assert.deepStrictEqual(JSON.parse(calls[0].opts.body), { agent: 'claude', text: 'x' });
});

test('SendInstructionIntent sem instrucao nao chama a ponte', async () => {
  setup({ speech: 'x' });
  const r = await handler(envelope(intent('SendInstructionIntent')), {});
  assert.strictEqual(calls.length, 0);
  assert.ok(r.response.reprompt);
});

test('modelo: projeto opcional no AskAgent, CancelRunIntent e SendInstructionIntent', () => {
  const m = require('../../interaction-model-pt-BR.json').interactionModel.languageModel;
  const ask = m.intents.find(i => i.name === 'AskAgentIntent');
  assert.deepStrictEqual(ask.slots.find(s => s.name === 'projeto'), { name: 'projeto', type: 'NOME_PROJETO' });
  assert.ok(ask.samples.some(s => s.includes('{projeto}') && s.includes('{agente}')));
  assert.ok(!ask.samples.some(s => s.includes('{instrucao}')), 'a instrucao vem no turno seguinte');
  const cancel = m.intents.find(i => i.name === 'CancelRunIntent');
  assert.ok(cancel.samples.includes('cancela o agente') && cancel.samples.includes('para o agente'));
  const send = m.intents.find(i => i.name === 'SendInstructionIntent');
  assert.strictEqual(send.slots[0].name, 'instrucao');
  assert.ok(send.samples.includes('avise o agente aberto {instrucao}'));
});
