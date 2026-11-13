// Painel do HeyCode (ADR 0046). Sem dependencias e sem montar HTML com dados: tudo entra por textContent.
const ROOT = document.getElementById("app");
const TOAST = document.getElementById("toast");
const ACCENTS = { Verde: "#0e9f8e", Azul: "#2563eb", Roxo: "#7c3aed", Rosa: "#db2777", Laranja: "#ea580c", Amarelo: "#ca8a04" };
const state = { session: null, installations: [], pairTimer: null };

// ---------- utilidades ----------
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
function toast(msg) {
  TOAST.textContent = msg;
  TOAST.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => TOAST.classList.remove("show"), 3200);
}
class ApiError extends Error {
  constructor(status, detail) { super(detail); this.status = status; this.detail = detail; }
}
async function api(method, path, body) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && state.session) headers["X-CSRF-Token"] = state.session.csrf;
  const res = await fetch(path, { method, headers, credentials: "same-origin", body: body === undefined ? undefined : JSON.stringify(body) });
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* corpo vazio */ }
  if (!res.ok) throw new ApiError(res.status, (data && (typeof data.detail === "string" ? data.detail : "invalido")) || "erro");
  return data;
}
const when = (t) => new Date(t * 1000).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "medium" });
const short = (id) => (id ? "…" + String(id).slice(-8) : "—");
const MSG = {
  credenciais: "E-mail ou senha incorretos.", "credenciais invalidas": "E-mail ou senha incorretos.",
  email_taken: "Esse e-mail já tem conta.", weak_password: "A senha precisa de pelo menos 10 caracteres.",
  invalid_email: "E-mail inválido.", "muitas tentativas": "Muitas tentativas. Aguarde um minuto.",
  name_taken: "Já existe um comando com esse nome ou apelido.", quota_commands: "Limite de 30 comandos atingido.",
  quota_installations: "Limite de 2 computadores por conta.", offline: "O computador está offline.",
};
const say = (e) => MSG[e.detail] || (e.status === 422 ? "Confira os campos: algum valor é inválido." : "Algo deu errado (" + e.detail + ").");

// ---------- aparencia (unica coisa guardada no navegador) ----------
function applyLook() {
  const theme = localStorage.getItem("hc_theme") || "auto";
  const accent = localStorage.getItem("hc_accent") || ACCENTS.Verde;
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.setProperty("--accent", accent);
}

// ---------- rotulos legiveis do rastro ----------
const KIND = {
  LaunchRequest: "Abriu o HeyCode", StatusIntent: "Pediu o status", PendingIntent: "Perguntou o que está pendente",
  ResultIntent: "Pediu o resultado", ApproveIntent: "Aprovou um pedido", DenyIntent: "Negou um pedido",
  SetModeIntent: "Mudou o modo", ReportOnEndIntent: "Aviso de fim de ciclo", AskAgentIntent: "Pediu algo a um agente",
  SendInstructionIntent: "Avisou o agente aberto", AnswerQuestionIntent: "Respondeu uma pergunta",
  ConfirmIntent: "Confirmou", CancelDictationIntent: "Cancelou o ditado", CancelRunIntent: "Cancelou a execução",
  CreateProjectIntent: "Criou um projeto", ListProjectsIntent: "Listou projetos", MoreProjectsIntent: "Mais projetos",
  SelectProjectIntent: "Escolheu um projeto", RunCommandIntent: "Executou um atalho",
  "AMAZON.HelpIntent": "Pediu ajuda", "AMAZON.StopIntent": "Encerrou", "AMAZON.CancelIntent": "Encerrou",
  "painel:aprovar_dispositivo": "Painel: aprovou um dispositivo", "painel:negar_dispositivo": "Painel: negou um dispositivo",
  "painel:revogar_dispositivo": "Painel: revogou um dispositivo", "painel:instalacao_padrao": "Painel: computador padrão",
  "painel:revogar_computador": "Painel: removeu um computador", "painel:renomear_computador": "Painel: renomeou um computador",
  "painel:criar_atalho": "Painel: criou um atalho", "painel:editar_atalho": "Painel: editou um atalho",
  "painel:apagar_atalho": "Painel: apagou um atalho", "painel:desligar_comando": "Painel: desligou um comando do computador",
};
const RESULT = {
  ok: ["feito", "ok"], sem_acao: ["sem ação", ""], barrado: ["barrado", "warn"], offline: ["offline", "bad"],
  erro: ["erro", "bad"], cota: ["limite diário", "warn"], sem_computador: ["sem computador", "warn"],
};

// ---------- componentes ----------
function page(title, sub, ...content) {
  return [h("h1", { text: title }), sub ? h("p", { class: "sub", text: sub }) : null, ...content].flat(Infinity).filter(Boolean);
}
const empty = (msg) => h("div", { class: "empty", text: msg });
const nameOf = (id) => (state.installations.find((i) => i.id === id) || {}).name || short(id);
async function loadInstallations() { state.installations = await api("GET", "/v1/installations"); return state.installations; }

// ---------- telas ----------
async function viewComputers() {
  const list = await loadInstallations();
  const rename = async (i) => {
    const name = window.prompt("Novo nome do computador:", i.name);
    if (!name || !name.trim()) return;
    try { await api("PATCH", "/v1/installations/" + i.id, { name }); toast("Renomeado."); render(); } catch (e) { toast(say(e)); }
  };
  const makeDefault = async (i) => { await api("PUT", "/v1/default-installation", { installation_id: i.id }); toast("Computador padrão definido."); render(); };
  const remove = async (i) => {
    if (!window.confirm("Remover \"" + i.name + "\"? Ele deixa de receber pedidos e precisará ser pareado de novo.")) return;
    await api("DELETE", "/v1/installations/" + i.id); toast("Computador removido."); render();
  };
  return page("Computadores", "Os computadores pareados à sua conta e quais estão conectados agora.",
    list.length ? list.map((i) => h("div", { class: "card row" },
      h("div", { class: "grow" },
        h("div", { class: "name" }, h("span", { class: "dot" + (i.online ? " on" : "") }), i.name, " ",
          i.is_default ? h("span", { class: "badge ok", text: "padrão" }) : null),
        h("div", { class: "meta", text: (i.online ? "Conectado" : "Offline") + " · último contato: " + (i.last_seen ? when(i.last_seen) : "nunca") })),
      h("button", { onclick: () => rename(i), text: "Renomear" }),
      i.is_default ? null : h("button", { onclick: () => makeDefault(i), text: "Tornar padrão" }),
      h("button", { class: "danger", onclick: () => remove(i), text: "Remover" })))
      : empty("Nenhum computador pareado ainda. Abra “Parear” para conectar o primeiro."));
}

async function viewDevices() {
  const [devices] = await Promise.all([api("GET", "/v1/devices"), loadInstallations()]);
  const act = async (fn, msg) => { try { await fn(); toast(msg); render(); } catch (e) { toast(say(e)); } };
  const body = (d) => ({ installation_id: d.installation_id, device_id: d.device_id });
  const card = (d, buttons) => h("div", { class: "card row" },
    h("div", { class: "grow" }, h("div", { class: "name", text: "Dispositivo " + short(d.device_id) }),
      h("div", { class: "meta", text: "Computador: " + nameOf(d.installation_id) })), buttons);
  const pending = devices.filter((d) => d.status === "pending");
  const approved = devices.filter((d) => d.status === "approved");
  return page("Dispositivos Alexa", "Um Echo só aciona o seu computador depois que você o autorizar aqui.",
    h("h2", { text: "Aguardando sua autorização" }),
    pending.length ? pending.map((d) => card(d, [
      h("button", { class: "primary", onclick: () => act(() => api("POST", "/v1/devices/approve", body(d)), "Dispositivo autorizado."), text: "Autorizar" }),
      h("button", { onclick: () => act(() => api("POST", "/v1/devices/deny", body(d)), "Solicitação negada."), text: "Negar" })]))
      : empty("Nenhuma solicitação. Quando um Echo novo falar com o HeyCode, ele aparece aqui."),
    h("h2", { text: "Autorizados" }),
    approved.length ? approved.map((d) => card(d,
      h("button", { class: "danger", onclick: () => act(() => api("DELETE", "/v1/devices/" + d.installation_id + "/" + encodeURIComponent(d.device_id)), "Dispositivo revogado."), text: "Revogar" })))
      : empty("Nenhum dispositivo autorizado."));
}

async function viewAudit() {
  await loadInstallations();
  const filters = { result: "", installation_id: "" };
  const out = h("div");
  const detail = h("div");
  let rows = [];
  let more = null;
  const draw = () => {
    out.replaceChildren(rows.length ? h("div", { class: "scroll" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Quando", "Dispositivo", "Computador", "O que aconteceu", "Resultado"].map((t) => h("th", { text: t })))),
      h("tbody", {}, rows.map((r) => {
        const [label, tone] = RESULT[r.result] || [r.result, ""];
        return h("tr", {},
          h("td", { text: when(r.t) }), h("td", { text: r.device_id ? short(r.device_id) : "painel", title: r.device_id || "" }),
          h("td", { text: r.installation_id ? nameOf(r.installation_id) : "—" }),
          h("td", { text: (KIND[r.kind] || r.kind) + (r.label ? " — " + r.label : "") }),
          h("td", {}, h("span", { class: "badge " + tone, text: label })));
      })))) : empty("Nada registrado ainda. Peça algo à Alexa e volte aqui."), ...(more ? [more] : []));
  };
  const load = async (append) => {
    const q = new URLSearchParams({ limit: "25" });
    if (filters.result) q.set("result", filters.result);
    if (filters.installation_id) q.set("installation_id", filters.installation_id);
    if (append && rows.length) q.set("before", rows[rows.length - 1].id);
    const got = await api("GET", "/v1/audit?" + q);
    rows = append ? rows.concat(got) : got;
    more = got.length === 25 ? h("button", { onclick: () => load(true), text: "Carregar mais" }) : null;
    draw();
  };
  const showDetail = async (id) => {
    detail.replaceChildren(h("p", { class: "meta", text: "Pedindo ao computador…" }));
    try {
      const d = await api("GET", "/v1/audit/detail?installation_id=" + encodeURIComponent(id) + "&limit=20");
      detail.replaceChildren(
        h("h2", { text: "O que o computador registrou" }),
        h("p", { class: "meta", text: "Vem direto do seu computador, com segredos mascarados; o relay não guarda isso." }),
        h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, ["Quando", "Agente", "Projeto", "Ferramenta", "Pedido", "Decisão"].map((t) => h("th", { text: t })))),
          h("tbody", {}, d.approvals.map((a) => h("tr", {}, h("td", { text: when(a.t) }), h("td", { text: a.agent || "" }), h("td", { text: a.project || "" }),
            h("td", { text: a.tool || "" }), h("td", { text: a.command || "" }), h("td", { text: a.decision })))))),
        d.runs.length ? h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, ["Início", "Agente", "Projeto", "Estado", "Resumo"].map((t) => h("th", { text: t })))),
          h("tbody", {}, d.runs.map((r) => h("tr", {}, h("td", { text: when(r.t_start) }), h("td", { text: r.agent || "" }), h("td", { text: r.project || "" }),
            h("td", { text: r.status }), h("td", { text: r.summary || "" })))))) : null);
    } catch (e) { detail.replaceChildren(empty(e.detail === "offline" ? "O computador está offline: o detalhe só aparece com ele conectado." : say(e))); }
  };
  const resultSel = h("select", { "aria-label": "Filtrar por resultado", onchange: (e) => { filters.result = e.target.value; load(false); } },
    h("option", { value: "", text: "Todos os resultados" }), Object.entries(RESULT).map(([k, v]) => h("option", { value: k, text: v[0] })));
  const compSel = h("select", { "aria-label": "Filtrar por computador", onchange: (e) => { filters.installation_id = e.target.value; load(false); } },
    h("option", { value: "", text: "Todos os computadores" }), state.installations.map((i) => h("option", { value: i.id, text: i.name })));
  const detailBtn = h("button", { onclick: () => { const id = filters.installation_id || (state.installations[0] || {}).id; if (id) showDetail(id); else toast("Nenhum computador pareado."); }, text: "Ver o que o computador registrou" });
  await load(false);
  return page("Rastro", "O que a voz pediu, aprovou e fez. O relay guarda só o quando, o quem e o resultado, nunca o conteúdo.",
    h("div", { class: "row card" }, h("div", { class: "grow" }, resultSel), h("div", { class: "grow" }, compSel), detailBtn), out, detail);
}

async function viewCommands() {
  await loadInstallations();
  const list = await api("GET", "/v1/commands");
  const f = { id: null };
  const inp = (id, props) => h("input", { id, ...props });
  const form = h("form", { class: "card", novalidate: true });
  const err = h("p", { class: "error", role: "alert" });
  const fill = (c) => {
    f.id = c ? c.id : null;
    const v = c || { name: "", aliases: [], agent: "claude", project: "", instruction: "", description: "", enabled: true };
    form.querySelector("#c-name").value = v.name; form.querySelector("#c-aliases").value = v.aliases.join(", ");
    form.querySelector("#c-agent").value = v.agent; form.querySelector("#c-project").value = v.project || "";
    form.querySelector("#c-instruction").value = v.instruction; form.querySelector("#c-description").value = v.description || "";
    form.querySelector("#c-enabled").checked = v.enabled;
    form.querySelector("h2").textContent = c ? "Editar “" + c.name + "”" : "Novo comando";
    err.textContent = "";
  };
  form.append(h("h2", { text: "Novo comando" }),
    h("div", { class: "grid2" },
      h("div", {}, h("label", { for: "c-name" }, "Nome falado ", h("span", { class: "hint", text: "(2 a 40 letras)" })), inp("c-name", { maxlength: "40" })),
      h("div", {}, h("label", { for: "c-aliases" }, "Apelidos ", h("span", { class: "hint", text: "(separados por vírgula, até 5)" })), inp("c-aliases"))),
    h("div", { class: "grid2" },
      h("div", {}, h("label", { for: "c-agent", text: "Agente" }), h("select", { id: "c-agent" }, ["claude", "codex", "aider"].map((a) => h("option", { value: a, text: a })))),
      h("div", {}, h("label", { for: "c-project" }, "Projeto ", h("span", { class: "hint", text: "(opcional)" })), inp("c-project", { maxlength: "80" }))),
    h("label", { for: "c-instruction" }, "O que pedir ao agente"), h("textarea", { id: "c-instruction", maxlength: "500" }),
    h("label", { for: "c-description" }, "Descrição ", h("span", { class: "hint", text: "(opcional)" })), inp("c-description", { maxlength: "200" }),
    h("label", {}, inp("c-enabled", { type: "checkbox", checked: true, style: undefined }), " Ligado"),
    err, h("div", { class: "row" }, h("button", { class: "primary", type: "submit", text: "Salvar" }), h("button", { type: "button", onclick: () => fill(null), text: "Limpar" })),
    h("p", { class: "meta", text: "Ao dizer o comando, a Alexa monta o pedido e pergunta “Confirma?” — nada roda sem a sua confirmação por voz." }));
  form.querySelector("#c-enabled").style.width = "auto";
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const val = (id) => form.querySelector(id).value.trim();
    const body = {
      name: val("#c-name"), aliases: val("#c-aliases").split(",").map((s) => s.trim()).filter(Boolean), agent: val("#c-agent"),
      project: val("#c-project") || null, instruction: val("#c-instruction"), description: val("#c-description") || null,
      enabled: form.querySelector("#c-enabled").checked,
    };
    try {
      await api(f.id ? "PUT" : "POST", "/v1/commands" + (f.id ? "/" + f.id : ""), body);
      toast("Comando salvo."); render();
    } catch (e) { err.textContent = say(e); }
  });
  const toggle = async (c) => { await api("PUT", "/v1/commands/" + c.id, { ...c, enabled: !c.enabled }); render(); };
  const del = async (c) => { if (window.confirm("Apagar “" + c.name + "”?")) { await api("DELETE", "/v1/commands/" + c.id); toast("Comando apagado."); render(); } };
  const cards = list.length ? list.map((c) => h("div", { class: "card row" },
    h("div", { class: "grow" }, h("div", { class: "name" }, c.name, " ", h("span", { class: "badge" + (c.enabled ? " ok" : ""), text: c.enabled ? "ligado" : "desligado" })),
      h("div", { class: "meta", text: "Diga: “Alexa, peça ao HeyCode, executar " + c.name + "” → " + c.agent + (c.project ? " em " + c.project : "") }),
      h("div", { class: "meta", text: c.instruction })),
    h("button", { onclick: () => { fill(c); form.scrollIntoView({ behavior: "smooth" }); }, text: "Editar" }),
    h("button", { onclick: () => toggle(c), text: c.enabled ? "Desligar" : "Ligar" }),
    h("button", { class: "danger", onclick: () => del(c), text: "Apagar" })))
    : empty("Nenhum comando ainda. Crie o primeiro abaixo, por exemplo “rodar testes”.");
  return page("Comandos", "Atalhos que a Alexa dispara por voz. Cada um vira um pedido a um agente, sempre com confirmação.", cards, form,
    h("h2", { text: "Comandos do computador" }), computerCommandsSection());
}

// Scripts e webhooks vivem no proprio computador (ADR 0051): aqui so se ve o resumo que ele anuncia e se desliga.
function computerCommandsSection() {
  const RISK = { leitura: ["roda direto", "warn"], confirmar: ["pede confirmação", "ok"], pin: ["exige PIN", "ok"] };
  const list = h("div");
  const card = (id, c) => h("div", { class: "card row" },
    h("div", { class: "grow" },
      h("div", { class: "name" }, c.name, " ",
        h("span", { class: "badge", text: c.type === "script" ? "script" : "webhook" }), " ",
        h("span", { class: "badge " + (RISK[c.risk] || ["", ""])[1], text: (RISK[c.risk] || [c.risk])[0] }), " ",
        h("span", { class: "badge" + (c.enabled ? " ok" : ""), text: c.enabled ? "ligado" : "desligado" })),
      c.description ? h("div", { class: "meta", text: c.description }) : null,
      h("div", { class: "meta", text: "Diga: “executar " + c.name + "”" })),
    c.enabled ? h("button", { onclick: async () => {
      try { await api("POST", "/v1/computers/" + encodeURIComponent(id) + "/commands/disable", { name: c.name }); toast("Comando desligado."); load(id); } catch (e) { toast(say(e)); }
    }, text: "Desligar" }) : null);
  const load = async (id) => {
    if (!id) { list.replaceChildren(empty("Nenhum computador pareado.")); return; }
    list.replaceChildren(h("p", { class: "meta", text: "Perguntando ao computador…" }));
    try {
      const d = await api("GET", "/v1/computers/" + encodeURIComponent(id) + "/commands");
      if (d.error) { list.replaceChildren(empty("O registro de comandos deste computador tem um erro. Rode “heycode command list” nele.")); return; }
      list.replaceChildren(...(d.commands.length ? d.commands.map((c) => card(id, c)) : [empty("Nenhum comando cadastrado neste computador.")]));
    } catch (e) { list.replaceChildren(empty(e.detail === "offline" ? "O computador está offline: os comandos dele só aparecem com ele conectado." : say(e))); }
  };
  const select = h("select", { "aria-label": "Computador", onchange: (e) => load(e.target.value) },
    state.installations.map((i) => h("option", { value: i.id, text: i.name })));
  load(select.value);
  return h("div", {},
    h("p", { class: "meta", text: "Scripts e webhooks são definidos no próprio computador. Criar, editar e ligar só pelo terminal; aqui você vê o que ele anuncia e pode desligar." }),
    h("div", { class: "card" }, h("label", { for: "pc-sel", text: "Computador" }), Object.assign(select, { id: "pc-sel" }),
      h("pre", { class: "cmd", text: "heycode command add 'reiniciar app' --risk confirmar --script -- systemctl --user restart app\nheycode command add 'acender luz' --risk confirmar --webhook https://casa.exemplo.com/luz --method POST" })),
    list);
}

async function viewPair() {
  const out = h("div");
  const pend = h("div");
  const gen = async () => {
    try {
      const { code } = await api("POST", "/v1/pair/codes");
      const cmd = "heycode pair " + code + " --relay " + location.origin;
      out.replaceChildren(h("div", { class: "card" }, h("div", { class: "meta", text: "Código (vale 5 minutos, uso único)" }), h("div", { class: "code", text: code }),
        h("p", { class: "meta", text: "No computador que você quer conectar, rode:" }), h("pre", { class: "cmd", text: cmd }),
        h("button", { onclick: async () => { try { await navigator.clipboard.writeText(cmd); toast("Comando copiado."); } catch { toast("Copie o comando manualmente."); } }, text: "Copiar comando" })));
    } catch (e) { toast(say(e)); }
  };
  const refresh = async () => {
    try {
      const list = await api("GET", "/v1/pair/pending");
      pend.replaceChildren(...[list.length ? list.map((p) => h("div", { class: "card" },
        h("div", { class: "name", text: "“" + p.name + "” quer parear" }),
        h("p", { class: "meta", text: "Confira que este código é o mesmo que apareceu no terminal do computador:" }),
        h("div", { class: "verify", text: p.verification }),
        h("div", { class: "row" }, h("button", { class: "primary", onclick: async () => {
          try { const r = await api("POST", "/v1/pair/confirm", { pending_id: p.pending_id }); toast(r && r.installation_id ? "Computador pareado." : "Aguardando a confirmação no computador."); refresh(); } catch (e) { toast(say(e)); }
        }, text: "O código confere: parear" })))) : empty("Nenhum pareamento esperando confirmação.")].flat());
    } catch { /* sessao expirada: o proximo render leva ao login */ }
  };
  state.pairTimer = setInterval(refresh, 3000);
  await refresh();
  return page("Parear um computador", "Gere um código, rode o comando no computador e confirme aqui que o código de verificação é o mesmo.",
    h("button", { class: "primary", onclick: gen, text: "Gerar código de pareamento" }), out, h("h2", { text: "Esperando confirmação" }), pend);
}

async function viewAccount() {
  const theme = localStorage.getItem("hc_theme") || "auto";
  const accent = localStorage.getItem("hc_accent") || ACCENTS.Verde;
  const pw = h("input", { type: "password", id: "del-pw", autocomplete: "current-password" });
  const err = h("p", { class: "error", role: "alert" });
  return page("Conta", state.session.email,
    h("h2", { text: "Aparência" }),
    h("div", { class: "card" },
      h("label", { for: "theme", text: "Tema" }),
      h("select", { id: "theme", onchange: (e) => { localStorage.setItem("hc_theme", e.target.value); applyLook(); } },
        [["auto", "Automático"], ["light", "Claro"], ["dark", "Escuro"]].map(([v, t]) => h("option", { value: v, text: t, selected: v === theme }))),
      h("label", { text: "Cor de destaque" }),
      h("div", { class: "swatches" }, Object.entries(ACCENTS).map(([n, c]) => h("button", { class: "swatch", title: n, "aria-label": n, "aria-pressed": String(c === accent),
        onclick: (e) => { localStorage.setItem("hc_accent", c); applyLook(); e.currentTarget.parentElement.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === e.currentTarget))); } }))),
      ),
    h("h2", { text: "Sessão" }),
    h("div", { class: "card" }, h("button", { onclick: async () => { await api("POST", "/v1/panel/logout"); state.session = null; render(); }, text: "Sair" })),
    h("h2", { text: "Excluir a conta" }),
    h("div", { class: "card" },
      h("p", { class: "meta", text: "Apaga a conta, computadores, dispositivos, comandos e o rastro, e encerra a vinculação com a Alexa. Não dá para desfazer." }),
      h("label", { for: "del-pw", text: "Confirme com a sua senha" }), pw, err,
      h("p", {}, h("button", { class: "danger", onclick: async () => {
        if (!pw.value) { err.textContent = "Digite a senha."; return; }
        if (!window.confirm("Excluir a conta definitivamente?")) return;
        try { await api("DELETE", "/v1/account", { password: pw.value }); state.session = null; toast("Conta excluída."); render(); } catch (e) { err.textContent = e.status === 403 ? "Senha incorreta." : say(e); }
      }, text: "Excluir minha conta" }))));
}

// ---------- entrada ----------
function viewAuth() {
  let mode = "login";
  const email = h("input", { type: "email", id: "email", autocomplete: "email", required: true });
  const pass = h("input", { type: "password", id: "pass", autocomplete: "current-password", required: true });
  const err = h("p", { class: "error", role: "alert" });
  const submit = h("button", { class: "primary", type: "submit", text: "Entrar" });
  const tabs = ["login", "signup"].map((m) => h("button", { type: "button", "aria-pressed": String(m === mode), text: m === "login" ? "Entrar" : "Criar conta",
    onclick: () => { mode = m; tabs.forEach((t, i) => t.setAttribute("aria-pressed", String(["login", "signup"][i] === m))); submit.textContent = m === "login" ? "Entrar" : "Criar conta"; pass.autocomplete = m === "login" ? "current-password" : "new-password"; err.textContent = ""; } }));
  const form = h("form", { class: "card", novalidate: true }, h("label", { for: "email", text: "E-mail" }), email, h("label", { for: "pass", text: "Senha" }), pass,
    mode === "signup" ? null : null, err, h("p", {}, submit));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault(); err.textContent = ""; submit.disabled = true;
    try {
      const creds = { email: email.value.trim(), password: pass.value };
      if (mode === "signup") await api("POST", "/v1/register", creds);
      await api("POST", "/v1/panel/login", creds);
      await boot();
    } catch (e) { err.textContent = say(e); } finally { submit.disabled = false; }
  });
  return h("div", { class: "auth", id: "main" }, h("div", { class: "brand", text: "HeyCode" }), h("div", { class: "tabs" }, tabs), form,
    h("p", { class: "meta", text: "Sua conta só guarda e-mail, o resumo do que a voz fez e as configurações do painel." }));
}

const ROUTES = {
  "#/computadores": ["Computadores", viewComputers], "#/dispositivos": ["Dispositivos", viewDevices], "#/rastro": ["Rastro", viewAudit],
  "#/comandos": ["Comandos", viewCommands], "#/parear": ["Parear", viewPair], "#/conta": ["Conta", viewAccount],
};

async function render() {
  clearInterval(state.pairTimer);
  if (!state.session) { ROOT.replaceChildren(viewAuth()); return; }
  const key = ROUTES[location.hash] ? location.hash : "#/computadores";
  const nav = h("nav", { class: "nav", "aria-label": "Principal" }, h("div", { class: "brand", text: "HeyCode" }),
    Object.entries(ROUTES).map(([hash, [label]]) => h("a", { href: hash, text: label, "aria-current": hash === key ? "page" : undefined })),
    h("div", { class: "who", text: state.session.email }));
  const main = h("main", { id: "main" }, h("p", { class: "meta", text: "Carregando…" }));
  ROOT.replaceChildren(h("div", { class: "shell" }, nav, main));
  try {
    main.replaceChildren(...(await ROUTES[key][1]()));
  } catch (e) {
    if (e.status === 401) { state.session = null; render(); return; }
    main.replaceChildren(empty("Não consegui carregar: " + say(e)));
  }
}

async function boot() {
  applyLook();
  try { state.session = await api("GET", "/v1/panel/session"); } catch { state.session = null; }
  render();
}
window.addEventListener("hashchange", render);
boot();
