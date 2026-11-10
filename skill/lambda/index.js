const Alexa = require('ask-sdk-core');

// Lidas a cada chamada: BRIDGE_URL ex.: https://agente.seudominio.com
async function bridge(path, method = 'GET', body) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5000); // Alexa tem ~8s de limite
  try {
    const r = await fetch(process.env.BRIDGE_URL + path, {
      method,
      headers: { 'x-secret': process.env.BRIDGE_CONTROL_SECRET, 'content-type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } finally {
    clearTimeout(timer);
  }
}

const isIntent = (h, name) =>
  Alexa.getRequestType(h.requestEnvelope) === 'IntentRequest' &&
  Alexa.getIntentName(h.requestEnvelope) === name;

const Launch = {
  canHandle: h => Alexa.getRequestType(h.requestEnvelope) === 'LaunchRequest',
  handle: h => h.responseBuilder
    .speak('Pronto. Pergunte o status, se tem algo pendente, ou peça o resumo.')
    .reprompt('Quer saber o status do agente?').getResponse(),
};

const getApprovalId = h => {
  const a = h.attributesManager.getSessionAttributes() || {};
  return a.approval_id == null ? null : a.approval_id;
};
const NEED_PENDING = 'Pergunte primeiro o que está pendente.';

const simple = (intentName, path) => ({
  canHandle: h => isIntent(h, intentName),
  async handle(h) {
    const d = await bridge(path);
    if (intentName === 'PendingIntent') {
      // amarra a decisão ao pedido que foi lido em voz alta
      const attrs = h.attributesManager.getSessionAttributes() || {};
      if (d.approval_id == null) delete attrs.approval_id; else attrs.approval_id = d.approval_id;
      h.attributesManager.setSessionAttributes(attrs);
    }
    const rb = h.responseBuilder.speak(d.speech);
    if (d.actionable) rb.reprompt('Diga aprovar com o seu PIN, ou negar.'); // mantém a sessão aberta
    return rb.getResponse();
  },
});

const Approve = {
  canHandle: h => isIntent(h, 'ApproveIntent'),
  async handle(h) {
    const approvalId = getApprovalId(h);
    if (approvalId == null) {
      return h.responseBuilder.speak(NEED_PENDING).reprompt('O que você quer saber?').getResponse();
    }
    const pin = Alexa.getSlotValue(h.requestEnvelope, 'pin');
    if (!pin) {
      return h.responseBuilder.speak('Qual é o seu PIN?').reprompt('Diga o seu PIN de quatro dígitos.')
        .addElicitSlotDirective('pin').getResponse();
    }
    const d = await bridge('/decide', 'POST', { approve: true, pin, approval_id: approvalId });
    return h.responseBuilder.speak(d.speech).getResponse();
  },
};

const Deny = {
  canHandle: h => isIntent(h, 'DenyIntent'),
  async handle(h) {
    const approvalId = getApprovalId(h);
    if (approvalId == null) {
      return h.responseBuilder.speak(NEED_PENDING).reprompt('O que você quer saber?').getResponse();
    }
    const d = await bridge('/decide', 'POST', { approve: false, approval_id: approvalId });
    return h.responseBuilder.speak(d.speech).getResponse();
  },
};

const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

const MODE_BY_TEXT = { manual: 'manual', auto: 'auto', automatico: 'auto', 'tudo liberado': 'auto', decisoes: 'decisoes', decisao: 'decisoes' };

function resolveMode(envelope) {
  const slot = Alexa.getSlot(envelope, 'modo');
  if (!slot || !slot.value) return null;
  const auth = ((slot.resolutions || {}).resolutionsPerAuthority || [])
    .find(a => a.status && a.status.code === 'ER_SUCCESS_MATCH');
  const id = auth && auth.values && auth.values[0] && auth.values[0].value && auth.values[0].value.id;
  if (id && ['manual', 'auto', 'decisoes'].includes(id)) return id;
  return MODE_BY_TEXT[norm(slot.value)] || null;
}

const SetMode = {
  canHandle: h => isIntent(h, 'SetModeIntent'),
  async handle(h) {
    const mode = resolveMode(h.requestEnvelope);
    if (!mode) {
      return h.responseBuilder.speak('Não entendi o modo. Diga manual, automático ou decisões.')
        .reprompt('Qual modo: manual, automático ou decisões?').getResponse();
    }
    const d = await bridge('/mode', 'POST', { mode });
    const name = { manual: 'manual', auto: 'automático', decisoes: 'decisões' }[d.mode || mode];
    return h.responseBuilder.speak(d.speech || `Modo ${name} ativado.`).getResponse();
  },
};

const OFF_WORDS = ['desligar', 'desligado', 'desliga', 'desligue', 'desativar', 'desativa'];
const ReportOnEnd = {
  canHandle: h => isIntent(h, 'ReportOnEndIntent'),
  async handle(h) {
    const v = norm(Alexa.getSlotValue(h.requestEnvelope, 'ligado'));
    const on = !OFF_WORDS.includes(v);
    const d = await bridge('/mode', 'POST', { report_on_end: on });
    const ligado = d.report_on_end === undefined ? on : d.report_on_end;
    return h.responseBuilder.speak(d.speech || `Aviso de fim de ciclo ${ligado ? 'ligado' : 'desligado'}.`).getResponse();
  },
};

const AGENTS = ['claude', 'codex', 'aider'];
function resolveAgent(envelope) {
  const slot = Alexa.getSlot(envelope, 'agente');
  if (!slot || !slot.value) return null;
  const auth = ((slot.resolutions || {}).resolutionsPerAuthority || [])
    .find(a => a.status && a.status.code === 'ER_SUCCESS_MATCH');
  const id = auth && auth.values && auth.values[0] && auth.values[0].value && auth.values[0].value.id;
  if (AGENTS.includes(id)) return id;
  const v = norm(slot.value);
  return AGENTS.includes(v) ? v : null;
}

function resolveProject(envelope) {
  const slot = Alexa.getSlot(envelope, 'projeto');
  if (!slot || !slot.value) return null;
  const auth = ((slot.resolutions || {}).resolutionsPerAuthority || [])
    .find(a => a.status && a.status.code === 'ER_SUCCESS_MATCH');
  const id = auth && auth.values && auth.values[0] && auth.values[0].value && auth.values[0].value.id;
  return id || String(slot.value).trim() || null;
}

async function dictate(h, agent, text, project) {
  const body = { agent, text };
  if (project) body.project = project;
  const d = await bridge('/dictation', 'POST', body);
  const rb = h.responseBuilder.speak(d.speech);
  if (d.ok !== false) rb.reprompt('Confirma?');
  return rb.getResponse();
}

const AskAgent = {
  canHandle: h => isIntent(h, 'AskAgentIntent'),
  async handle(h) {
    const agent = resolveAgent(h.requestEnvelope);
    const text = String(Alexa.getSlotValue(h.requestEnvelope, 'instrucao') || '').trim();
    if (!agent || !text) {
      return h.responseBuilder.speak('Diga o agente e a instrução. Por exemplo: peça ao claude para rodar os testes.')
        .reprompt('Para qual agente, e qual instrução?').getResponse();
    }
    return dictate(h, agent, text, resolveProject(h.requestEnvelope));
  },
};

const SendInstruction = {
  canHandle: h => isIntent(h, 'SendInstructionIntent'),
  async handle(h) {
    const text = String(Alexa.getSlotValue(h.requestEnvelope, 'instrucao') || '').trim();
    if (!text) {
      return h.responseBuilder.speak('Qual é a instrução para o agente aberto?')
        .reprompt('O que devo avisar ao agente?').getResponse();
    }
    return dictate(h, 'claude', text);
  },
};

const CreateProject = {
  canHandle: h => isIntent(h, 'CreateProjectIntent'),
  async handle(h) {
    const agent = resolveAgent(h.requestEnvelope);
    const name = String(Alexa.getSlotValue(h.requestEnvelope, 'nome') || '').trim();
    const description = String(Alexa.getSlotValue(h.requestEnvelope, 'descricao') || '').trim();
    if (!agent || !name || !description) {
      return h.responseBuilder
        .speak('Diga o nome, o agente e a descrição. Por exemplo: crie o projeto meu app com o claude para um site de receitas.')
        .reprompt('Qual o nome do projeto, o agente e a descrição?').getResponse();
    }
    const d = await bridge('/projects', 'POST', { name, agent, description });
    const rb = h.responseBuilder.speak(d.speech);
    if (d.ok !== false) rb.reprompt('Confirma?');
    return rb.getResponse();
  },
};

const simplePost = (intentName, path) => ({
  canHandle: h => isIntent(h, intentName),
  async handle(h) {
    const d = await bridge(path, 'POST');
    return h.responseBuilder.speak(d.speech).getResponse();
  },
});

// Allowlist: só o dono (userId + deviceId). Lida do env a cada requisição.
class AccessDenied extends Error {
  constructor(kind) { super('access denied: ' + kind); this.kind = kind; }
}
const AllowlistInterceptor = {
  process(h) {
    const env = h.requestEnvelope;
    const sys = (env.context && env.context.System) || {};
    const userId = (sys.user && sys.user.userId) || (env.session && env.session.user && env.session.user.userId);
    const deviceId = sys.device && sys.device.deviceId;
    const allowedSkill = process.env.ALLOWED_SKILL_ID;
    if (allowedSkill) {
      const appId = (sys.application && sys.application.applicationId)
        || (env.session && env.session.application && env.session.application.applicationId);
      if (appId !== allowedSkill) {
        console.log(`SKILL NEGADA. applicationId=${appId}`);
        throw new AccessDenied('denied');
      }
    }
    const allowedUser = process.env.ALLOWED_USER_ID;
    const allowedDevice = process.env.ALLOWED_DEVICE_ID;
    if (!allowedUser || !allowedDevice) {
      console.log(`ALLOWLIST NAO CONFIGURADA. userId=${userId} deviceId=${deviceId}`);
      throw new AccessDenied('unconfigured');
    }
    if (userId !== allowedUser || deviceId !== allowedDevice) {
      console.log(`ACESSO NEGADO. userId=${userId} deviceId=${deviceId}`);
      throw new AccessDenied('denied');
    }
  },
};

const DeniedErrors = {
  canHandle: (h, err) => err instanceof AccessDenied,
  handle: (h, err) => h.responseBuilder.speak(err.kind === 'unconfigured'
    ? 'A skill ainda não está configurada. Defina o usuário e o dispositivo permitidos nas variáveis de ambiente.'
    : 'Acesso negado.').withShouldEndSession(true).getResponse(),
};

const Help = {
  canHandle: h => isIntent(h, 'AMAZON.HelpIntent'),
  handle: h => h.responseBuilder
    .speak('Você pode perguntar o status, se há algo pendente, pedir o resumo, ou aprovar e negar comandos.')
    .reprompt('O que deseja saber?').getResponse(),
};

const Stop = {
  canHandle: h => isIntent(h, 'AMAZON.StopIntent') || isIntent(h, 'AMAZON.CancelIntent'),
  handle: h => h.responseBuilder.speak('Até já.').getResponse(),
};

const Fallback = {
  canHandle: h => isIntent(h, 'AMAZON.FallbackIntent'),
  handle: h => h.responseBuilder.speak('Não entendi. Tente: qual o status?').reprompt('Qual o status?').getResponse(),
};

const SessionEnded = {
  canHandle: h => Alexa.getRequestType(h.requestEnvelope) === 'SessionEndedRequest',
  handle: h => h.responseBuilder.getResponse(),
};

const Errors = {
  canHandle: () => true,
  handle(h, err) {
    console.error(err);
    return h.responseBuilder.speak('Não consegui falar com o seu computador. Verifique se a ponte está rodando.').getResponse();
  },
};

exports.handler = Alexa.SkillBuilders.custom()
  .addRequestInterceptors(AllowlistInterceptor)
  .addRequestHandlers(Launch, simple('StatusIntent', '/status'), simple('PendingIntent', '/pending'),
    simple('ResultIntent', '/result'), Approve, Deny, SetMode, ReportOnEnd,
    AskAgent, SendInstruction, simplePost('CancelRunIntent', '/runs/latest/cancel'), CreateProject, simplePost('ConfirmIntent', '/confirm'), simplePost('CancelDictationIntent', '/cancel'), Help, Stop, Fallback, SessionEnded)
  .addErrorHandlers(DeniedErrors, Errors)
  .lambda();
