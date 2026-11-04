"""Étape 10 : qualité et extension (backends, formateur, mypy)."""

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from alto.backend import Backend, Sortie
from alto.backends import BACKENDS
from alto.cli import ERREUR_COMPILATION, OK, main
from alto.compilateur import executer, transpiler
from alto.erreurs import ErreurAlto
from alto.noeuds import Decimal, Ecris, Programme
from alto.parser import parse
from alto.semantique import Analyse, analyser

RACINE = Path(__file__).parent.parent
EXEMPLES = sorted((RACINE / "exemples").glob("*.alt"))


def formate(source: str) -> str:
    return transpiler(source, backend="formateur").code


class Compteur:
    """Un backend jouet : il n'hérite de rien, il a juste « la bonne forme »."""

    nom = "compteur"
    extension = ".txt"
    executable = False

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
        return Sortie(str(len(programme.instructions)))


def compiler_avec(backend: Backend, source: str) -> Sortie:
    """Ce que fera le compilateur : il ne connaît que le Protocol, pas la classe."""
    programme = parse(source)
    return backend.generer(programme, analyser(programme))


def test_un_backend_n_a_besoin_que_du_protocol() -> None:
    # mypy vérifie ici que Compteur respecte Backend, sans héritage
    assert compiler_avec(Compteur(), "ecris 1; ecris 2;").code == "2"


def test_le_backend_recoit_l_analyse() -> None:
    class Globales:
        nom = "globales"
        extension = ".txt"
        executable = False

        def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
            return Sortie(repr(analyse.globales_modifiees))

    source = "var n = 0; fonction f() { n = 1; }"
    assert compiler_avec(Globales(), source).code == "{'f': {'n'}}"


def test_une_sortie_sans_correspondance_a_un_dictionnaire_vide() -> None:
    assert Sortie("x = 1").correspondance == {}


def test_deux_sorties_ne_partagent_pas_leur_correspondance() -> None:
    a, b = Sortie("a"), Sortie("b")
    a.correspondance[1] = 1
    assert b.correspondance == {}


def test_une_sortie_est_immuable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Sortie("a").code = "b"  # type: ignore[misc]


def test_backend_n_importe_ni_le_generateur_ni_le_formateur() -> None:
    """Sinon import circulaire : ce sont eux qui importeront backend.py."""
    source = (RACINE / "alto" / "backend.py").read_text(encoding="utf-8")
    assert "alto.generateur" not in source
    assert "alto.formateur" not in source


# --- Le registre des backends --------------------------------------------------------


def test_la_liste_des_backends() -> None:
    assert set(BACKENDS) == {"python", "ast", "formateur"}


def test_un_backend_inconnu_est_refuse() -> None:
    with pytest.raises(ErreurAlto, match="backend inconnu"):
        transpiler("ecris 1;", backend="cobol")


def test_le_formateur_n_est_pas_executable() -> None:
    with pytest.raises(ErreurAlto, match="executable"):
        executer("ecris 1;", backend="formateur")


# --- Le formateur : deux propriétés vérifiées sur chaque exemple ----------------------


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda p: p.stem)
def test_le_formateur_preserve_l_arbre(exemple: Path) -> None:
    source = exemple.read_text(encoding="utf-8")
    assert parse(formate(source)) == parse(source)


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda p: p.stem)
def test_le_formateur_est_idempotent(exemple: Path) -> None:
    une_fois = formate(exemple.read_text(encoding="utf-8"))
    assert formate(une_fois) == une_fois


# --- Le formateur : la présentation ----------------------------------------------------


def test_un_programme_laid_est_remis_en_forme() -> None:
    laid = 'var   x=(1+2)*3 ;si x>2{ecris x ,"grand";}sinon{ecris((x));}'
    assert formate(laid) == (
        'var x = (1 + 2) * 3;\nsi x > 2 {\n    ecris x, "grand";\n} sinon {\n    ecris x;\n}\n'
    )


def test_toutes_les_instructions() -> None:
    source = (
        "fonction f(a, b) { rends a; } fonction g() { rends; }"
        "var l = [1, 2]; l[0] = 3; ajoute(l, 4);"
        "si vrai { } sinon si faux { ecris 1; }"
        "tantque faux { } pour i de 1 jusqua 3 { ecris i; }"
    )
    assert formate(source) == (
        "fonction f(a, b) {\n"
        "    rends a;\n"
        "}\n"
        "\n"
        "fonction g() {\n"
        "    rends;\n"
        "}\n"
        "\n"
        "var l = [1, 2];\n"
        "l[0] = 3;\n"
        "ajoute(l, 4);\n"
        "si vrai {\n"
        "} sinon si faux {\n"
        "    ecris 1;\n"
        "}\n"
        "tantque faux {\n"
        "}\n"
        "pour i de 1 jusqua 3 {\n"
        "    ecris i;\n"
        "}\n"
    )


def test_un_programme_vide_reste_vide() -> None:
    assert formate("# juste un commentaire\n") == ""


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("ecris ((x));", "ecris x;"),
        ("ecris (1 + 2) * 3;", "ecris (1 + 2) * 3;"),
        ("ecris 1 + (2 * 3);", "ecris 1 + 2 * 3;"),
        ("ecris (a - b) - c;", "ecris a - b - c;"),
        ("ecris a - (b - c);", "ecris a - (b - c);"),
        ("ecris a / (b * c);", "ecris a / (b * c);"),
        ("ecris (non a) == b;", "ecris (non a) == b;"),
        ("ecris non (a == b);", "ecris non a == b;"),
        ("ecris (a ou b) et c;", "ecris (a ou b) et c;"),
        ("ecris a ou (b et c);", "ecris a ou b et c;"),
        ("ecris (a < b) < c;", "ecris a < b < c;"),
        ("ecris a < (b < c);", "ecris a < (b < c);"),
        ("ecris -(a * b);", "ecris -(a * b);"),
        ("ecris (-a) * b;", "ecris -a * b;"),
        ("ecris - - a;", "ecris - -a;"),
        ("ecris (a + b)[0];", "ecris (a + b)[0];"),
        # `texte` rend un texte, qu'on peut indexer (indexer `taille(…)`, un entier, est
        # refusé par le typage de l'extension 12)
        ("ecris texte([a])[0];", "ecris texte([a])[0];"),
    ],
)
def test_parentheses_minimales(source: str, attendu: str) -> None:
    prefixe = "var x = 1; var a = 1; var b = 2; var c = 3;\n"
    assert formate(prefixe + source).splitlines()[-1] == attendu


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ('ecris "Elle a dit \\"oui\\".";', 'ecris "Elle a dit \\"oui\\".";'),
        ('ecris "a\\nb\\tc\\\\d";', 'ecris "a\\nb\\tc\\\\d";'),
        ('ecris "";', 'ecris "";'),
        ("ecris 1.0, 3.14, 0.0000001;", "ecris 1.0, 3.14, 0.0000001;"),
        ("ecris 10000000000000000.0;", "ecris 10000000000000000.0;"),
        ("ecris vrai, faux, rien, [];", "ecris vrai, faux, rien, [];"),
    ],
)
def test_les_litteraux_sont_reecrits_tels_qu_alto_les_relit(source: str, attendu: str) -> None:
    assert formate(source) == attendu + "\n"
    assert parse(formate(source)) == parse(source)


def test_un_petit_decimal_n_est_pas_ecrit_en_notation_scientifique() -> None:
    # repr(1e-07) donne '1e-07', qu'Alto ne sait pas lire
    programme = Programme((Ecris((Decimal(1e-07),)),))
    assert BACKENDS["formateur"].generer(programme, Analyse()).code == "ecris 0.0000001;\n"


# --- La commande fmt --------------------------------------------------------------


def test_fmt_affiche_le_programme_remis_en_forme(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fichier = tmp_path / "laid.alt"
    fichier.write_text("ecris   1+2 ;", encoding="utf-8")
    assert main(["fmt", str(fichier)]) == OK
    assert capsys.readouterr().out == "ecris 1 + 2;\n"
    assert fichier.read_text(encoding="utf-8") == "ecris   1+2 ;"  # inchangé


def test_fmt_ecrire_reecrit_le_fichier(tmp_path: Path) -> None:
    fichier = tmp_path / "laid.alt"
    fichier.write_text("ecris   1+2 ;", encoding="utf-8")
    assert main(["fmt", str(fichier), "--ecrire"]) == OK
    assert fichier.read_text(encoding="utf-8") == "ecris 1 + 2;\n"


def test_fmt_refuse_un_programme_faux(tmp_path: Path) -> None:
    fichier = tmp_path / "faux.alt"
    fichier.write_text("ecris x;", encoding="utf-8")
    assert main(["fmt", str(fichier), "--ecrire"]) == ERREUR_COMPILATION
    assert fichier.read_text(encoding="utf-8") == "ecris x;"  # pas écrasé


def test_run_avec_le_formateur_est_refuse(tmp_path: Path) -> None:
    fichier = tmp_path / "p.alt"
    fichier.write_text("ecris 1;", encoding="utf-8")
    assert main(["run", str(fichier), "--backend", "formateur"]) == ERREUR_COMPILATION


def test_transpile_avec_le_formateur(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fichier = tmp_path / "p.alt"
    fichier.write_text("ecris(1);", encoding="utf-8")
    assert main(["transpile", str(fichier), "--backend", "formateur"]) == OK
    assert capsys.readouterr().out == "ecris 1;\n"


# --- mypy ----------------------------------------------------------------------------


def test_mypy_strict_passe() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(RACINE / "alto")],
        check=False,  # on lit nous-mêmes le code de retour, pour afficher les erreurs de mypy
        capture_output=True,
        text=True,
    )
    assert resultat.returncode == 0, resultat.stdout
