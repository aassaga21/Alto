import inspect
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

from alto.backend import Sortie
from alto.cli import ERREUR_COMPILATION, ERREUR_EXECUTION, OK, main
from alto.compilateur import compiler, executer, executer_sortie
from alto.erreurs import ErreurExecution, ErreursMultiples, Position
from alto.repl import INVITE, SUITE, Reponse, repl

RACINE = Path(__file__).parent.parent
EXEMPLES = sorted((RACINE / "exemples").glob("*.alt"))


def ecrire(tmp_path: Path, source: str) -> str:
    """Écrit un programme dans un dossier temporaire (fourni par pytest)."""
    fichier = tmp_path / "p.alt"
    fichier.write_text(source, encoding="utf-8")
    return str(fichier)


# --- check ---


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda chemin: chemin.stem)
def test_check_accepte_chaque_exemple(exemple: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(exemple)]) == OK
    sortie = capsys.readouterr()
    assert sortie.out == ""
    assert sortie.err == ""


def test_check_signale_une_erreur_semantique(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", ecrire(tmp_path, "ecris x;")]) == ERREUR_COMPILATION
    assert "p.alt:1:7 : erreur sémantique" in capsys.readouterr().err


def test_check_signale_une_erreur_de_syntaxe_avec_le_chapeau(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", ecrire(tmp_path, "var x = 1\necris x;")]) == ERREUR_COMPILATION
    erreur = capsys.readouterr().err
    assert "p.alt:1:10 : erreur de syntaxe" in erreur
    assert "    var x = 1\n             ^" in erreur


def test_check_signale_une_erreur_lexicale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", ecrire(tmp_path, "var x = @;")]) == ERREUR_COMPILATION
    assert "p.alt:1:9 : erreur lexicale : caractère inattendu" in capsys.readouterr().err


def test_check_affiche_toutes_les_erreurs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = "var x = 1;\necris y;\nvar x = 2;\n"
    assert main(["check", ecrire(tmp_path, source)]) == ERREUR_COMPILATION
    erreur = capsys.readouterr().err
    assert "p.alt:2:7" in erreur
    assert "p.alt:3:1" in erreur


def test_les_erreurs_vont_sur_stderr_pas_sur_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["check", ecrire(tmp_path, "ecris x;")])
    assert capsys.readouterr().out == ""


def test_compiler_leve_erreurs_multiples() -> None:
    with pytest.raises(ErreursMultiples):
        compiler("ecris x;")


# --- Fichiers et arguments ---


@pytest.mark.parametrize("commande", ["run", "check", "transpile"])
def test_fichier_introuvable(commande: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([commande, "nexiste_pas.alt"]) == ERREUR_COMPILATION
    assert "alto : fichier introuvable : nexiste_pas.alt" in capsys.readouterr().err


def test_une_commande_inconnue_est_refusee_par_argparse() -> None:
    with pytest.raises(SystemExit) as sortie:
        main(["danse", "p.alt"])
    assert sortie.value.code == 2


def test_sans_commande_argparse_refuse() -> None:
    with pytest.raises(SystemExit) as sortie:
        main([])
    assert sortie.value.code == 2


def test_python_m_alto_check() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "alto", "check", "exemples/01_bonjour.alt"],
        check=False,
        cwd=RACINE,
        capture_output=True,
        text=True,
    )
    assert resultat.returncode == OK
    assert resultat.stderr == ""


# --- Erreurs d'exécution ramenées à la ligne Alto ---
# On les teste dès maintenant avec du Python écrit à la main, sans attendre le générateur.


def test_une_erreur_d_execution_pointe_la_ligne_alto() -> None:
    sortie = Sortie("x = 1\ny = x / 0\n", correspondance={1: 4, 2: 7})
    with pytest.raises(ErreurExecution) as erreur:
        executer_sortie(sortie)
    assert erreur.value.message == "division par zéro"
    assert erreur.value.position == Position(7, 0)


def test_l_erreur_d_execution_est_chainee_a_l_exception_python() -> None:
    with pytest.raises(ErreurExecution) as erreur:
        executer_sortie(Sortie("[][0]\n", correspondance={1: 1}))
    assert isinstance(erreur.value.__cause__, IndexError)
    assert erreur.value.message == "indice hors limites"


def test_l_erreur_au_fond_d_un_appel_pointe_la_ligne_la_plus_profonde() -> None:
    code = "def f(n):\n    return 1 / n\n\nf(0)\n"
    with pytest.raises(ErreurExecution) as erreur:
        executer_sortie(Sortie(code, correspondance={1: 1, 2: 2, 4: 4}))
    assert erreur.value.position == Position(2, 0)


def test_une_recursion_infinie_devient_une_erreur_d_execution() -> None:
    code = "def f(n):\n    return f(n + 1)\n\nf(0)\n"
    with pytest.raises(ErreurExecution) as erreur:
        executer_sortie(Sortie(code, correspondance={2: 3, 4: 5}))
    assert erreur.value.message == "trop d'appels récursifs"
    assert erreur.value.position == Position(3, 0)


def test_une_ligne_sans_correspondance_donne_une_erreur_sans_position() -> None:
    with pytest.raises(ErreurExecution) as erreur:
        executer_sortie(Sortie("1 + 'a'\n"))
    assert erreur.value.message == "opération impossible sur ces valeurs"
    assert erreur.value.position is None


def test_executer_sortie_affiche_sur_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    executer_sortie(Sortie("print('bonjour')\n"))
    assert capsys.readouterr().out == "bonjour\n"


# --- run et transpile ---


def test_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", ecrire(tmp_path, "ecris 1 + 1;")]) == OK
    assert capsys.readouterr().out == "2\n"


def test_run_erreur_d_execution_ramenee_a_la_ligne_alto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = "fonction f(l) {\n    rends l[5];\n}\necris f([1]);\n"
    assert main(["run", ecrire(tmp_path, source)]) == ERREUR_EXECUTION
    assert "p.alt:2 : erreur d'exécution : indice hors limites" in capsys.readouterr().err


def test_executer_une_division_par_zero() -> None:
    with pytest.raises(ErreurExecution) as erreur:
        executer("ecris 1 / 0;")
    assert isinstance(erreur.value.__cause__, ZeroDivisionError)


def test_transpile_a_l_ecran(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["transpile", ecrire(tmp_path, "ecris 1 + 1;")]) == OK
    assert "_ecris(1 + 1)" in capsys.readouterr().out


def test_transpile_dans_un_fichier(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sortie = tmp_path / "p.py"
    assert main(["transpile", ecrire(tmp_path, "ecris 1 + 1;"), "-o", str(sortie)]) == OK
    assert capsys.readouterr().out == ""
    assert "_ecris(1 + 1)" in sortie.read_text(encoding="utf-8")


def test_python_m_alto_run() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "alto", "run", "exemples/01_bonjour.alt"],
        check=False,
        cwd=RACINE,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert resultat.returncode == OK
    assert resultat.stdout.startswith("Bonjour, Alto !")


# --- REPL ---


def session() -> Generator[Reponse, str, None]:
    """Une session de REPL déjà démarrée."""
    s = repl()
    next(s)
    return s


def test_le_repl_est_un_generateur() -> None:
    s = repl()
    assert inspect.isgenerator(s)
    assert next(s) == Reponse("", INVITE)


def test_le_repl_garde_l_etat_et_survit_aux_erreurs() -> None:
    s = session()
    s.send("var x = 20;")
    assert "n'est pas déclaré" in s.send("ecris y;").sortie
    assert s.send("x * 2 + 2").sortie == "42\n"


def test_le_repl_attend_la_fin_du_bloc() -> None:
    s = session()
    assert s.send("si vrai {").invite == SUITE
    assert s.send('ecris "oui";').sortie == ""
    reponse = s.send("}")
    assert reponse.sortie == "oui\n"
    assert reponse.invite == INVITE


def test_une_accolade_dans_un_texte_ne_compte_pas() -> None:
    s = session()
    assert s.send('ecris "{";') == Reponse("{\n", INVITE)


def test_le_repl_n_affiche_pas_deux_fois_les_anciens_ecris() -> None:
    s = session()
    assert s.send('ecris "a";').sortie == "a\n"
    assert s.send('ecris "b";').sortie == "b\n"


def test_une_ligne_vide_ne_fait_rien() -> None:
    s = session()
    assert s.send("") == Reponse("", INVITE)


def test_une_instruction_avec_point_virgule_n_affiche_rien() -> None:
    s = session()
    assert s.send("var x = 1;").sortie == ""
    assert s.send("x = x + 1;").sortie == ""
    assert s.send("x").sortie == "2\n"


def test_une_fonction_definie_puis_appelee_plus_tard() -> None:
    s = session()
    s.send("fonction double(n) {")
    s.send("rends n * 2;")
    s.send("}")
    assert s.send("double(21)").sortie == "42\n"


def test_une_fonction_qui_modifie_une_globale() -> None:
    s = session()
    s.send("var compteur = 0;")
    s.send("fonction incr() { compteur = compteur + 1; }")
    s.send("incr();")
    s.send("incr();")
    assert s.send("compteur").sortie == "2\n"


def test_une_saisie_refusee_ne_change_pas_l_etat() -> None:
    s = session()
    s.send("var x = 1;")
    assert "déjà déclaré" in s.send("var x = 2;").sortie
    assert s.send("x").sortie == "1\n"


def test_une_erreur_d_execution_ne_casse_pas_la_session() -> None:
    s = session()
    assert s.send("ecris 1 / 0;").sortie == "erreur d'exécution : division par zéro\n"
    assert s.send("1 + 1").sortie == "2\n"


def test_une_declaration_qui_echoue_peut_etre_refaite() -> None:
    s = session()
    assert "division par zéro" in s.send("var z = 1 / 0;").sortie
    s.send("var z = 5;")
    assert s.send("z").sortie == "5\n"


def test_ce_qui_est_affiche_avant_l_erreur_est_garde() -> None:
    s = session()
    sortie = s.send('ecris "avant"; ecris 1 / 0;').sortie
    assert sortie.startswith("avant\n")
    assert "division par zéro" in sortie


def test_l_affichage_suit_les_regles_d_alto() -> None:
    s = session()
    assert s.send("[1, vrai, rien]").sortie == "[1, vrai, rien]\n"


def test_python_m_alto_repl() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "alto", "repl"],
        check=False,
        cwd=RACINE,
        input="var x = 20;\nx * 2 + 2\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        # sous Windows, un tube utilise cp1252 par défaut : on force l'UTF-8 (accents, « — »)
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert resultat.returncode == OK
    assert "42" in resultat.stdout
