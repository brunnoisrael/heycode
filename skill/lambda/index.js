const Alexa = require('ask-sdk-core');

const BASE = process.env.BRIDGE_URL;      // ex.: https://agente.seudominio.com
const SECRET = process.env.BRIDGE_SECRET;

async function bridge(path, method = 'GET', body) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5000); // Alexa tem ~8s de limite
  try {
    const r = await fetch(BASE + path, {
      method,
      headers: { 'x-secret': SECRET, 'content-type': 'application/json' },
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

const simple = (intentName, path) => ({
  canHandle: h => isIntent(h, intentName),
  async handle(h) {
    const d = await bridge(path);
    const rb = h.responseBuilder.speak(d.speech);
    if (d.actionable) rb.reprompt('Diga aprovar com o seu PIN, ou negar.'); // mantém a sessão aberta
    return rb.getResponse();
  },
});

const Approve = {
  canHandle: h => isIntent(h, 'ApproveIntent'),
  async handle(h) {
    const pin = Alexa.getSlotValue(h.requestEnvelope, 'pin');
    if (!pin) {
      return h.responseBuilder.speak('Qual é o seu PIN?').reprompt('Diga o seu PIN de quatro dígitos.')
        .addElicitSlotDirective('pin').getResponse();
    }
    const d = await bridge('/decide', 'POST', { approve: true, pin });
    return h.responseBuilder.speak(d.speech).getResponse();
  },
};

const Deny = {
  canHandle: h => isIntent(h, 'DenyIntent'),
  async handle(h) {
    const d = await bridge('/decide', 'POST', { approve: false });
    return h.responseBuilder.speak(d.speech).getResponse();
  },
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
  .addRequestHandlers(Launch, simple('StatusIntent', '/status'), simple('PendingIntent', '/pending'),
    simple('ResultIntent', '/result'), Approve, Deny, Help, Stop, Fallback, SessionEnded)
  .addErrorHandlers(Errors)
  .lambda();
