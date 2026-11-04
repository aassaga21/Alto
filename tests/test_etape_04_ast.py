"""Étape 4 : l'arbre syntaxique (AST)."""

import dataclasses

import pytest

from alto.erreurs import SANS_POSITION, Position
from alto.noeuds import (
    Appel,
    Binaire,
    Bloc,
    Branche,
    Ecris,
    Entier,
    Programme,
    Rends,
    Si,
    Texte,
    Variable,
    afficher_arbre,
)


def test_les_noeuds_sont_immuables() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Entier(1).valeur = 2  # type: ignore[misc]


def test_un_noeud_sans_position_est_accepte() -> None:
    assert Entier(1).pos == SANS_POSITION


def test_la_position_n_intervient_pas_dans_l_egalite() -> None:
    assert Entier(1, Position(1, 1)) == Entier(1, Position(5, 9))
    assert "Position" not in repr(Entier(1, Position(1, 1)))


def test_deux_arbres_differents_ne_sont_pas_egaux() -> None:
    assert Binaire("+", Entier(1), Entier(2)) != Binaire("-", Entier(1), Entier(2))


def test_les_enfants_multiples_sont_des_tuples() -> None:
    bloc = Bloc((Ecris((Entier(1),)),))
    assert isinstance(bloc.instructions, tuple)


def test_asdict_fonctionne() -> None:
    assert dataclasses.asdict(Entier(3))["valeur"] == 3


def test_afficher_arbre() -> None:
    arbre = Binaire("+", Entier(1), Binaire("*", Variable("x"), Entier(2)))
    assert afficher_arbre(arbre) == (
        "Binaire op='+'\n"
        "├── gauche: Entier valeur=1\n"
        "└── droite: Binaire op='*'\n"
        "    ├── gauche: Variable nom='x'\n"
        "    └── droite: Entier valeur=2"
    )


def test_afficher_arbre_d_un_appel_a_plusieurs_arguments() -> None:
    arbre = Appel(Variable("f"), (Entier(1), Texte("a")))
    assert afficher_arbre(arbre) == (
        "Appel\n"
        "├── fonction: Variable nom='f'\n"
        "├── arguments[0]: Entier valeur=1\n"
        "└── arguments[1]: Texte valeur='a'"
    )


def test_afficher_arbre_d_un_si_avec_sinon() -> None:
    arbre = Si(
        (Branche(Binaire("<=", Variable("n"), Entier(1)), Bloc((Rends(Entier(1)),))),),
        Bloc((Rends(None),)),
    )
    assert afficher_arbre(arbre) == (
        "Si\n"
        "├── branches[0]: Branche\n"
        "│   ├── condition: Binaire op='<='\n"
        "│   │   ├── gauche: Variable nom='n'\n"
        "│   │   └── droite: Entier valeur=1\n"
        "│   └── corps: Bloc\n"
        "│       └── instructions[0]: Rends\n"
        "│           └── valeur: Entier valeur=1\n"
        "└── sinon: Bloc\n"
        "    └── instructions[0]: Rends valeur=None"
    )


def test_afficher_arbre_d_un_programme_vide() -> None:
    assert afficher_arbre(Programme(())) == "Programme instructions=()"
