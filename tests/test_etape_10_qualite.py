"""Étape 10 : qualité et extension (backends, formateur, mypy).

Pour l'instant seul le contrat (`backend.py`) existe. Les tests du formateur et de
`BACKENDS` viendront quand l'émetteur (Arthur) et le compilateur (Alexandra) seront là.
"""

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from alto.backend import Backend, Sortie
from alto.noeuds import Programme
from alto.parser import parse
from alto.semantique import Analyse, analyser

RACINE = Path(__file__).parent.parent


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


def test_mypy_strict_passe() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(RACINE / "alto")],
        check=False,  # on lit nous-mêmes le code de retour, pour afficher les erreurs de mypy
        capture_output=True,
        text=True,
    )
    assert resultat.returncode == 0, resultat.stdout
