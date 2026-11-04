"""Étape 5 : le parser des expressions (méthode de Pratt)."""

import pytest

from alto.erreurs import ErreurSyntaxe, Position
from alto.noeuds import (
    Appel,
    Binaire,
    Booleen,
    Decimal,
    Entier,
    Expr,
    Index,
    Liste,
    Rien,
    Texte,
    Unaire,
    Variable,
)
from alto.parser import REGLES_INFIXE, REGLES_PREFIXE, parse_expression
from alto.tokens import TokenKind as T

a, b, c, f = Variable("a"), Variable("b"), Variable("c"), Variable("f")


# --- Les littéraux et les expressions simples --------------------------------


@pytest.mark.parametrize(
    ("source", "arbre"),
    [
        ("42", Entier(42)),
        ("1.5", Decimal(1.5)),
        ('"salut"', Texte("salut")),
        ("vrai", Booleen(True)),
        ("faux", Booleen(False)),
        ("rien", Rien()),
        ("x", Variable("x")),
        ("[]", Liste(())),
        ("[1, 2]", Liste((Entier(1), Entier(2)))),
        ("(42)", Entier(42)),
    ],
)
def test_expressions_simples(source: str, arbre: Expr) -> None:
    assert parse_expression(source) == arbre


# --- Une ligne par niveau du tableau des priorités de la spécification -------


@pytest.mark.parametrize(
    ("source", "arbre"),
    [
        # 1 `ou` est plus faible que 2 `et`
        ("a ou b et c", Binaire("ou", a, Binaire("et", b, c))),
        ("a et b ou c", Binaire("ou", Binaire("et", a, b), c)),
        # 2 `et` est plus faible que 3 `non`
        ("non a et b", Binaire("et", Unaire("non", a), b)),
        # 3 `non` est plus faible que 4 les comparaisons
        ("non a == b", Unaire("non", Binaire("==", a, b))),
        # 4 les comparaisons sont plus faibles que 5 `+` `-`
        ("a < b + 1", Binaire("<", a, Binaire("+", b, Entier(1)))),
        # 5 `+` est plus faible que 6 `*`
        ("1 + 2 * 3", Binaire("+", Entier(1), Binaire("*", Entier(2), Entier(3)))),
        ("1 * 2 + 3", Binaire("+", Binaire("*", Entier(1), Entier(2)), Entier(3))),
        # 6 `*` est plus faible que 7 le `-` unaire
        ("-a * b", Binaire("*", Unaire("-", a), b)),
        # 7 le `-` unaire est plus faible que 8 l'appel et l'indice
        ("-f(x)", Unaire("-", Appel(f, (Variable("x"),)))),
        ("-t[0]", Unaire("-", Index(Variable("t"), Entier(0)))),
        # les parenthèses passent avant tout
        ("(1 + 2) * 3", Binaire("*", Binaire("+", Entier(1), Entier(2)), Entier(3))),
    ],
)
def test_priorites(source: str, arbre: Expr) -> None:
    assert parse_expression(source) == arbre


# --- Tous les opérateurs binaires du même niveau se valent --------------------


@pytest.mark.parametrize("op", ["==", "!=", "<", "<=", ">", ">=", "+", "-", "*", "/", "%"])
def test_chaque_operateur_binaire(op: str) -> None:
    assert parse_expression(f"a {op} b") == Binaire(op, a, b)


# --- Associativité à gauche ---------------------------------------------------


@pytest.mark.parametrize(
    ("source", "arbre"),
    [
        ("1 - 2 - 3", Binaire("-", Binaire("-", Entier(1), Entier(2)), Entier(3))),
        ("8 / 4 / 2", Binaire("/", Binaire("/", Entier(8), Entier(4)), Entier(2))),
        ("a ou b ou c", Binaire("ou", Binaire("ou", a, b), c)),
        # pas de comparaison chaînée : (a < b) < c
        ("a < b < c", Binaire("<", Binaire("<", a, b), c)),
    ],
)
def test_associativite_a_gauche(source: str, arbre: Expr) -> None:
    assert parse_expression(source) == arbre


# --- Les opérateurs unaires s'empilent ----------------------------------------


@pytest.mark.parametrize(
    ("source", "arbre"),
    [
        ("- - x", Unaire("-", Unaire("-", Variable("x")))),
        ("non non a", Unaire("non", Unaire("non", a))),
    ],
)
def test_unaires_empiles(source: str, arbre: Expr) -> None:
    assert parse_expression(source) == arbre


# --- Appels et indices ----------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "arbre"),
    [
        ("f()", Appel(f, ())),
        ("f(x)", Appel(f, (Variable("x"),))),
        ("f(1, a + b)", Appel(f, (Entier(1), Binaire("+", a, b)))),
        ("t[i + 1]", Index(Variable("t"), Binaire("+", Variable("i"), Entier(1)))),
        ("t[0][1]", Index(Index(Variable("t"), Entier(0)), Entier(1))),
        ("f(x)[0]", Index(Appel(f, (Variable("x"),)), Entier(0))),
        ('"abc"[0]', Index(Texte("abc"), Entier(0))),
        # accepté par le parser, refusé par l'analyse sémantique (spécification 1.0)
        ("f(1)(2)", Appel(Appel(f, (Entier(1),)), (Entier(2),))),
    ],
)
def test_appels_et_indices(source: str, arbre: Expr) -> None:
    assert parse_expression(source) == arbre


# --- Les tables et les positions ----------------------------------------------


def test_les_decorateurs_ont_rempli_les_tables() -> None:
    assert T.ENTIER in REGLES_PREFIXE
    assert T.PLUS in REGLES_INFIXE
    # le `-` a deux règles : préfixe (-x) et infixe (a - b)
    assert T.MOINS in REGLES_PREFIXE
    assert T.MOINS in REGLES_INFIXE


def test_un_noeud_porte_la_position_de_son_token() -> None:
    expr = parse_expression("1 +\n  2")
    assert isinstance(expr, Binaire)
    assert expr.pos == Position(1, 3)
    assert expr.droite.pos == Position(2, 3)


# --- Les erreurs de syntaxe, avec leur position ---------------------------------


@pytest.mark.parametrize(
    ("source", "position"),
    [
        ("1 +", Position(1, 4)),  # il manque l'opérande droit
        ("(1 + 2", Position(1, 7)),  # parenthèse jamais fermée
        ("* 2", Position(1, 1)),  # une expression ne commence pas par `*`
        ("t[0", Position(1, 4)),  # crochet jamais fermé
        ("[1, 2,]", Position(1, 7)),  # pas de virgule finale dans une liste
        ("f(a,)", Position(1, 5)),  # ni dans un appel
        ("1 2", Position(1, 3)),  # il reste un token après l'expression
        ("", Position(1, 1)),  # rien du tout
    ],
)
def test_erreurs_de_syntaxe(source: str, position: Position) -> None:
    with pytest.raises(ErreurSyntaxe) as erreur:
        parse_expression(source)
    assert erreur.value.position == position
