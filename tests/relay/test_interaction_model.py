import json
from pathlib import Path

MODEL = Path(__file__).resolve().parents[2] / "skill" / "interaction-model-pt-BR.json"


def load():
    # o arquivo e gravado em cp1252 (acentos em um byte): ler como utf-8 corromperia os textos
    return json.loads(MODEL.read_bytes().decode("cp1252"))["interactionModel"]


def test_run_command_intent_esta_no_modelo_com_slot_livre_e_frases_de_ativacao():
    intent = next(i for i in load()["languageModel"]["intents"] if i["name"] == "RunCommandIntent")
    assert [(s["name"], s["type"]) for s in intent["slots"]] == [("comando", "AMAZON.SearchQuery")]
    assert intent["samples"] and all(
        "{comando}" in s and s != "{comando}" for s in intent["samples"]
    )  # SearchQuery exige frase-guia


def test_elicitacao_do_slot_comando_tem_o_prompt_declarado():
    model = load()
    dialog = next(i for i in model["dialog"]["intents"] if i["name"] == "RunCommandIntent")
    slot = dialog["slots"][0]
    assert slot["elicitationRequired"] is True
    prompt_id = slot["prompts"]["elicitation"]
    assert any(p["id"] == prompt_id for p in model["prompts"])


def test_todas_as_intents_do_dialogo_existem_no_modelo_e_ids_de_prompt_sao_unicos():
    model = load()
    names = {i["name"] for i in model["languageModel"]["intents"]}
    assert {i["name"] for i in model["dialog"]["intents"]} <= names
    ids = [p["id"] for p in model["prompts"]]
    assert len(ids) == len(set(ids))


def test_intents_antigas_continuam_la():
    names = {i["name"] for i in load()["languageModel"]["intents"]}
    assert {"StatusIntent", "ApproveIntent", "AskAgentIntent", "SendInstructionIntent", "ConfirmIntent"} <= names


def test_acentos_do_modelo_antigo_ficaram_intactos():
    raw = MODEL.read_bytes()
    assert b"\xef\xbf\xbd" not in raw  # nenhum caractere de substituicao introduzido
