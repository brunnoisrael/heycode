const Alexa = require('ask-sdk-core');

// Alexa-hosted não tem variáveis de ambiente no console: lá os valores vêm de env.json, ao lado deste
// arquivo (nunca commitado). Variável já definida no ambiente vence o arquivo. Sem o arquivo, nada muda.
function loadEnvFile(file) {
  let values;
  try {
    values = require(file);
  } catch (e) {
    if (e.code === 'MODULE_NOT_FOUND') return;
    throw e;
  }
  for (const [k, v] of Object.entries(values)) {
    if (process.env[k] === undefined && v !== null && v !== '') process.env[k] = String(v);
  }
}
loadEnvFile('./env.json');
exports.loadEnvFile = loadEnvFile;

// A Alexa-hosted roda em Node 16, que não tem fetch global. Este substituto cobre só o que bridge() usa:
// método, cabeçalhos, corpo, sinal de abort, e na resposta ok, status e json().
function httpFetch(url, { method = 'GET', headers = {}, body, signal } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const lib = u.protocol === 'http:' ? require('http') : require('https');
    const h = { ...headers };
    if (body !== undefined) h['content-length'] = Buffer.byteLength(body);
    const req = lib.request(u, { method, headers: h, signal }, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('error', reject);
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        resolve({ ok: res.statusCode >= 200 && res.statusCode < 300, status: res.statusCode, json: async () => JSON.parse(text) });
      });
    });
    req.on('error', reject);
    req.end(body);
  });
}
exports.httpFetch = httpFetch;
const doFetch = (url, opts) => (typeof fetch === 'function' ? fetch(url, opts) : httpFetch(url, opts));

// Lidas a cada chamada: BRIDGE_URL ex.: https://agente.seudominio.com
async function bridge(path, method = 'GET', body) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5000); // Alexa tem ~8s de limite
  try {
    const r = await doFetch(process.env.BRIDGE_URL + path, {
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

// Diálogo em dois turnos: a Alexa não aceita slot de frase (AMAZON.SearchQuery) junto de outro slot na
// mesma frase. O primeiro turno traz agente/projeto (ou nome/agente); a frase livre vem no turno seguinte,
// pedida com Dialog.ElicitSlot. O que já foi dito fica na sessão, caso a Alexa não devolva os slots.
const getSaved = (h, key) => (h.attributesManager.getSessionAttributes() || {})[key] || {};
function setSaved(h, key, value) {
  const attrs = h.attributesManager.getSessionAttributes() || {};
  if (value == null) delete attrs[key]; else attrs[key] = value;
  h.attributesManager.setSessionAttributes(attrs);
}

const AskAgent = {
  canHandle: h => isIntent(h, 'AskAgentIntent'),
  async handle(h) {
    const saved = getSaved(h, 'ask');
    const agent = resolveAgent(h.requestEnvelope) || saved.agent || null;
    const project = resolveProject(h.requestEnvelope) || saved.project || null;
    const text = String(Alexa.getSlotValue(h.requestEnvelope, 'instrucao') || '').trim();
    if (!agent) {
      return h.responseBuilder.speak('Diga o agente primeiro. Por exemplo: peça ao claude. Depois eu pergunto a instrução.')
        .reprompt('Para qual agente: claude, codex ou aider?').getResponse();
    }
    if (!text) {
      setSaved(h, 'ask', project ? { agent, project } : { agent });
      return h.responseBuilder.speak(`Qual é a instrução para o ${agent}?`).reprompt('Qual é a instrução?')
        .addElicitSlotDirective('instrucao').getResponse();
    }
    setSaved(h, 'ask', null);
    return dictate(h, agent, text, project);
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
    const saved = getSaved(h, 'create');
    const agent = resolveAgent(h.requestEnvelope) || saved.agent || null;
    const name = String(Alexa.getSlotValue(h.requestEnvelope, 'nome') || '').trim() || saved.name || '';
    const description = String(Alexa.getSlotValue(h.requestEnvelope, 'descricao') || '').trim();
    if (!agent || !name) {
      return h.responseBuilder
        .speak('Diga o nome e o agente. Por exemplo: crie o projeto meu app com o claude. Depois eu pergunto para que ele serve.')
        .reprompt('Qual o nome do projeto e o agente?').getResponse();
    }
    if (!description) {
      setSaved(h, 'create', { name, agent });
      return h.responseBuilder.speak(`Para que serve o projeto ${name}?`).reprompt('Para que serve o projeto?')
        .addElicitSlotDirective('descricao').getResponse();
    }
    setSaved(h, 'create', null);
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
