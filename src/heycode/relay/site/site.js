// Site publico do HeyCode (ADR 0059). So enfeita: sem este arquivo a pagina continua inteira e legivel.
// Nada de HTML montado com texto e nada guardado no navegador.
const SCENES = [
  { said: "Alexa, pergunte ao HeyCode o status", reply: "O Claude está rodando os testes do projeto loja. Nada esperando por você.",
    term: ['$ claude "rode os testes"', "● rodando pytest -q", "412 passed in 38s"] },
  { said: "Alexa, peça ao HeyCode o que está pendente", reply: "O Codex quer rodar git push no projeto loja. Para aprovar, diga aprovar e o seu PIN.",
    term: ["⏸ aguardando aprovação", "  git push origin main", "✓ aprovado por voz · enviado"] },
  { said: "Alexa, peça ao HeyCode, executar revisar pull request", reply: "Vou pedir ao Claude: revise o PR aberto e liste os riscos. Confirma?",
    term: ["▶ atalho: revisar pull request", "● lendo 14 arquivos alterados", "✓ 2 riscos encontrados · resumo pronto"] },
];
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const wait = (ms) => new Promise((done) => setTimeout(done, ms));

async function type(el, text, pace) {
  el.textContent = "";
  for (const ch of text) {
    el.textContent += ch;
    await wait(pace);
  }
}

async function demo() {
  const said = document.getElementById("demo-said");
  const reply = document.getElementById("demo-reply");
  const term = document.getElementById("demo-term");
  const stage = document.querySelector(".stage");
  if (!said || !reply || !term || !stage || still) return; // sem animacao: fica a primeira cena, ja escrita no HTML
  for (let i = 1; ; i = (i + 1) % SCENES.length) {
    await wait(4200);
    const scene = SCENES[i];
    reply.textContent = "";
    term.textContent = "";
    stage.dataset.state = "ouvindo";
    await type(said, scene.said, 34);
    stage.dataset.state = "falando";
    await wait(350);
    await type(reply, scene.reply, 16);
    stage.dataset.state = "";
    for (const line of scene.term) {
      term.textContent += (term.textContent ? "\n" : "") + line;
      await wait(520);
    }
  }
}

// Luz que segue o ponteiro nos cartoes: so duas variaveis de estilo, definidas pela API (a CSP barra atributo style).
function spotlight() {
  if (still) return;
  for (const card of document.querySelectorAll(".card")) {
    card.addEventListener("pointermove", (ev) => {
      const box = card.getBoundingClientRect();
      card.style.setProperty("--mx", ev.clientX - box.left + "px");
      card.style.setProperty("--my", ev.clientY - box.top + "px");
    });
  }
}

demo();
spotlight();
