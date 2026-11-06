import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult, InputRequiredResult

from alto.cli import ERREUR_COMPILATION, main
from alto.serveur_mcp import (
    creer_serveur,
    executer_alto,
    executer_avec_limite,
    formater_alto,
    lire_exemple,
    noms_des_exemples,
    transpiler_alto,
    verifier_alto,
)

RACINE = Path(__file__).parent.parent


# --- Les outils, sans le protocole ---


def test_executer_renvoie_ce_que_le_programme_affiche() -> None:
    assert executer_alto("var x = 20; ecris x * 2 + 2;") == {
        "ok": True,
        "sortie": "42\n",
        "erreurs": [],
    }


@pytest.mark.parametrize("backend", ["python", "ast"])
def test_executer_avec_les_deux_backends(backend: Any) -> None:
    assert executer_alto('ecris "a", 1 + 1;', backend)["sortie"] == "a 2\n"


def test_l_affichage_ne_va_pas_sur_la_sortie_standard(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # le transport stdio de MCP utilise la sortie standard pour ses propres messages
    executer_alto('ecris "bonjour";')
    assert capsys.readouterr().out == ""


def test_une_erreur_d_execution_garde_ce_qui_a_ete_affiche_avant() -> None:
    resultat = executer_alto('ecris "avant";\nvar l = [1];\necris l[5];')
    assert resultat["ok"] is False
    assert resultat["sortie"] == "avant\n"
    (erreur,) = resultat["erreurs"]
    assert erreur["genre"] == "erreur d'exécution"
    assert erreur["message"] == "indice hors limites"
    assert (erreur["ligne"], erreur["colonne"]) == (3, None)


def test_une_erreur_de_compilation_a_sa_ligne_et_sa_colonne() -> None:
    resultat = executer_alto("ecris y;")
    assert resultat["ok"] is False
    assert resultat["sortie"] == ""
    (erreur,) = resultat["erreurs"]
    assert erreur["genre"] == "erreur sémantique"
    assert (erreur["ligne"], erreur["colonne"]) == (1, 7)
    assert erreur["texte"].startswith("<mcp>:1:7 : erreur sémantique")


def test_toutes_les_erreurs_sont_renvoyees() -> None:
    erreurs = verifier_alto('var x: entier = "a";\necris y;')["erreurs"]
    assert [e["genre"] for e in erreurs] == ["erreur de type", "erreur sémantique"]
    assert [e["ligne"] for e in erreurs] == [1, 2]


def test_une_boucle_infinie_est_arretee() -> None:
    resultat = executer_avec_limite("var n = 0;\ntantque vrai { n = n + 1; }", "python", 10_000)
    assert resultat["ok"] is False
    (erreur,) = resultat["erreurs"]
    assert "dépassé 10000 étapes" in erreur["message"]
    assert erreur["ligne"] == 2


def test_un_programme_normal_tient_dans_la_limite() -> None:
    source = (RACINE / "exemples" / "05_premiers.alt").read_text(encoding="utf-8")
    assert executer_alto(source)["ok"] is True


def test_la_limite_ne_reste_pas_active_apres_l_execution() -> None:
    avant = sys.gettrace()
    executer_avec_limite("tantque vrai { }", "python", 100)
    assert sys.gettrace() is avant


def test_verifier_un_programme_correct() -> None:
    assert verifier_alto("var x = 1; ecris x;") == {"ok": True, "erreurs": []}


def test_transpiler() -> None:
    resultat = transpiler_alto("ecris 1 + 2;")
    assert resultat["ok"] is True
    assert "_ecris(1 + 2)" in resultat["code"]


def test_transpiler_un_programme_faux() -> None:
    resultat = transpiler_alto("ecris 1 +;")
    assert resultat["ok"] is False
    assert resultat["code"] == ""
    assert resultat["erreurs"][0]["genre"] == "erreur de syntaxe"


def test_formater() -> None:
    assert formater_alto("var   x=1 ;") == {"ok": True, "code": "var x = 1;\n", "erreurs": []}


def test_les_exemples() -> None:
    assert "03_fizzbuzz" in noms_des_exemples()
    assert lire_exemple("03_fizzbuzz").startswith("#")
    with pytest.raises(ValueError, match="exemple inconnu"):
        lire_exemple("../specification")


# --- Le serveur MCP ---


def test_le_serveur_declare_ses_quatre_outils() -> None:
    outils = asyncio.run(creer_serveur().list_tools())
    assert [o.name for o in outils] == [
        "executer_alto",
        "verifier_alto",
        "transpiler_alto",
        "formater_alto",
    ]
    (executer,) = [o for o in outils if o.name == "executer_alto"]
    assert executer.input_schema["required"] == ["source"]
    assert executer.input_schema["properties"]["backend"]["enum"] == ["python", "ast"]
    # la limite d'étapes n'est pas un argument : un client ne peut pas la lever
    assert "etapes_max" not in executer.input_schema["properties"]
    assert executer.output_schema is not None


def test_appeler_un_outil_donne_un_resultat_structure() -> None:
    resultat = asyncio.run(creer_serveur().call_tool("executer_alto", {"source": "ecris 6 * 7;"}))
    assert isinstance(resultat, CallToolResult)
    assert not resultat.is_error
    assert resultat.structured_content == {"ok": True, "sortie": "42\n", "erreurs": []}


def lire(uri: str) -> str:
    contenus = asyncio.run(creer_serveur().read_resource(uri))
    assert not isinstance(contenus, InputRequiredResult)
    texte = next(iter(contenus)).content
    assert isinstance(texte, str)
    return texte


def test_la_ressource_specification() -> None:
    assert lire("alto://specification").startswith("# Spécification d'Alto")


def test_les_ressources_exemples() -> None:
    assert lire("alto://exemples").splitlines() == noms_des_exemples()
    assert "fizzbuzz" in lire("alto://exemples/03_fizzbuzz")


def test_le_prompt_ecrire_programme() -> None:
    prompts = asyncio.run(creer_serveur().list_prompts())
    assert [p.name for p in prompts] == ["ecrire_programme"]


def test_une_vraie_session_mcp_sur_stdio() -> None:
    # Le client lance `python -m alto mcp` et lui parle par le protocole, comme le ferait
    # un assistant.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def session() -> dict[str, Any]:
        parametres = StdioServerParameters(
            command=sys.executable, args=["-m", "alto", "mcp"], cwd=str(RACINE)
        )
        async with (
            stdio_client(parametres) as (lecture, ecriture),
            ClientSession(lecture, ecriture) as client,
        ):
            init = await client.initialize()
            assert init.server_info.name == "alto"
            resultat = await client.call_tool("executer_alto", {"source": 'ecris "Bonjour";'})
            assert resultat.structured_content is not None
            return dict(resultat.structured_content)

    assert asyncio.run(session()) == {"ok": True, "sortie": "Bonjour\n", "erreurs": []}


# --- La ligne de commande ---


def test_sans_la_bibliotheque_mcp_un_message_clair(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda nom: None)
    assert main(["mcp"]) == ERREUR_COMPILATION
    assert "uv sync --extra mcp" in capsys.readouterr().err
