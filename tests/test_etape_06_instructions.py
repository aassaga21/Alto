"""Étape 6 : le parser des instructions et la reprise sur erreur."""

from pathlib import Path

import pytest

from alto.erreurs import ErreurLexicale, ErreursMultiples, ErreurSyntaxe, Position
from alto.noeuds import (
    Affectation,
    Appel,
    Binaire,
    Bloc,
    Branche,
    Declaration,
    Ecris,
    Entier,
    ExprInstr,
    Fonction,
    Index,
    Instr,
    Pour,
    Programme,
    Rends,
    Si,
    TantQue,
    Texte,
    Variable,
)
from alto.parser import parse

EXEMPLES = sorted((Path(__file__).parent.parent / "exemples").glob("*.alt"))

a, b, n, x = Variable("a"), Variable("b"), Variable("n"), Variable("x")


def bloc(*instructions: Instr) -> Bloc:
    return Bloc(instructions)


def ecris(valeur: int) -> Ecris:
    """`ecris valeur;`"""
    return Ecris((Entier(valeur),))


def erreurs_de(source: str) -> list[ErreurSyntaxe]:
    with pytest.raises(ErreursMultiples) as erreur:
        parse(source)
    resultat = []
    for e in erreur.value.erreurs:
        assert isinstance(e, ErreurSyntaxe)
        resultat.append(e)
    return resultat


# --- Chaque instruction, avec et sans ses parties facultatives ----------------------


@pytest.mark.parametrize(
    ("source", "instruction"),
    [
        ("var x = 1;", Declaration("x", Entier(1))),
        ("x = 2;", Affectation(x, Entier(2))),
        ("t[0] = 5;", Affectation(Index(Variable("t"), Entier(0)), Entier(5))),
        ("ecris 1;", ecris(1)),
        ('ecris "a", x, 1 + 2;', Ecris((Texte("a"), x, Binaire("+", Entier(1), Entier(2))))),
        ("ajoute(l, 3);", ExprInstr(Appel(Variable("ajoute"), (Variable("l"), Entier(3))))),
        ("1 + 2;", ExprInstr(Binaire("+", Entier(1), Entier(2)))),
        ("rends;", Rends(None)),
        ("rends n * 2;", Rends(Binaire("*", n, Entier(2)))),
        ("tantque a { ecris 1; }", TantQue(a, bloc(ecris(1)))),
        ("tantque a { }", TantQue(a, bloc())),
        (
            "pour i de 1 jusqua n { ecris 1; }",
            Pour("i", Entier(1), n, bloc(ecris(1))),
        ),
        ("fonction f() { }", Fonction("f", (), bloc())),
        ("fonction f(n) { rends n; }", Fonction("f", ("n",), bloc(Rends(n)))),
        ("fonction f(a, b) { }", Fonction("f", ("a", "b"), bloc())),
    ],
)
def test_chaque_instruction(source: str, instruction: Instr) -> None:
    assert parse(source) == Programme((instruction,))


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("si a { ecris 1; }", Si((Branche(a, bloc(ecris(1))),), None)),
        (
            "si a { ecris 1; } sinon { ecris 2; }",
            Si((Branche(a, bloc(ecris(1))),), bloc(ecris(2))),
        ),
        (
            "si a { ecris 1; } sinon si b { ecris 2; } sinon si x { ecris 3; }",
            Si(
                (
                    Branche(a, bloc(ecris(1))),
                    Branche(b, bloc(ecris(2))),
                    Branche(x, bloc(ecris(3))),
                ),
                None,
            ),
        ),
        (
            "si a { ecris 1; } sinon si b { ecris 2; } sinon { ecris 3; }",
            Si((Branche(a, bloc(ecris(1))), Branche(b, bloc(ecris(2)))), bloc(ecris(3))),
        ),
        ("si vrai { }", None),  # bloc vide permis
    ],
)
def test_si(source: str, attendu: Si | None) -> None:
    (instruction,) = parse(source).instructions
    assert isinstance(instruction, Si)
    if attendu is not None:
        assert instruction == attendu


def test_blocs_imbriques() -> None:
    source = "fonction f(n) { si n > 0 { pour i de 1 jusqua n { ecris 1; } } }"
    attendu = Fonction(
        "f",
        ("n",),
        bloc(
            Si(
                (
                    Branche(
                        Binaire(">", n, Entier(0)), bloc(Pour("i", Entier(1), n, bloc(ecris(1))))
                    ),
                ),
                None,
            )
        ),
    )
    assert parse(source) == Programme((attendu,))


@pytest.mark.parametrize("source", ["", "   \n\n", "# rien que des commentaires\n# fin"])
def test_un_programme_vide_est_valide(source: str) -> None:
    assert parse(source) == Programme(())


def test_plusieurs_instructions_dans_l_ordre() -> None:
    assert parse("var x = 1;\nx = 2;\necris x;") == Programme(
        (Declaration("x", Entier(1)), Affectation(x, Entier(2)), Ecris((x,)))
    )


# --- Les positions ----------------------------------------------------------------------


def test_les_instructions_portent_la_position_de_leur_premier_token() -> None:
    programme = parse("var x = 1;\n  ecris x;")
    assert [i.pos for i in programme.instructions] == [Position(1, 1), Position(2, 3)]


# --- Les erreurs ----------------------------------------------------------------------


@pytest.mark.parametrize("source", ["1 = 2;", "f(x) = 3;", "a + b = 1;"])
def test_affectation_a_une_cible_invalide(source: str) -> None:
    assert "on ne peut affecter" in erreurs_de(source)[0].message


@pytest.mark.parametrize(
    ("source", "position"),
    [
        ("var x = 1\necris x;", Position(1, 10)),  # juste après le 1
        ("ecris x\n", Position(1, 8)),
        ("x = 2\n", Position(1, 6)),
        ("rends 1\n", Position(1, 8)),
        ('ecris "ab"\n', Position(1, 11)),  # le texte occupe 4 colonnes avec ses guillemets
        ('ecris "a\\"b"\n', Position(1, 13)),  # et 6 avec l'échappement \"
    ],
)
def test_point_virgule_oublie_signale_juste_apres_le_token_precedent(
    source: str, position: Position
) -> None:
    (erreur,) = erreurs_de(source)
    assert "';' attendu" in erreur.message
    assert erreur.position == position


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("ecris;", "expression attendue"),
        ("var 1 = 2;", "<identifiant> attendu après var"),
        ("var x 1;", "'=' attendu"),
        ("pour i 1 jusqua 3 { }", "'de' attendu"),
        ("pour i de 1 a 3 { }", "'jusqua' attendu"),
        ("si a ecris 1;", "'{' attendu pour ouvrir le bloc"),
        ("fonction (a) { }", "<identifiant> attendu après fonction"),
        ("fonction f(a,) { }", "<identifiant> attendu comme paramètre"),
        ("fonction f(1) { }", "<identifiant> attendu comme paramètre"),
        ("ecris [1, 2,];", "expression attendue"),
    ],
)
def test_erreurs_de_syntaxe(source: str, fragment: str) -> None:
    assert any(fragment in e.message for e in erreurs_de(source))


def test_plusieurs_erreurs_signalees_ensemble() -> None:
    erreurs = erreurs_de("var = 1;\necris 2;\nvar y 3;")
    assert [e.position for e in erreurs] == [Position(1, 5), Position(3, 7)]


def test_trois_fautes_donnent_trois_messages() -> None:
    assert len(erreurs_de("var = 1;\necris ;\nx = = 2;\necris 4;")) == 3


def test_une_erreur_dans_un_bloc_n_empeche_pas_d_analyser_la_suite_du_bloc() -> None:
    erreurs = erreurs_de("si vrai {\n  var = 1;\n  ecris 2\n}")
    assert [e.position for e in erreurs] == [Position(2, 7), Position(3, 10)]


def test_la_reprise_ne_boucle_pas_quand_rien_n_a_ete_consomme() -> None:
    assert len(erreurs_de("* 2;\necris 1;")) == 1


def test_accolade_fermante_orpheline() -> None:
    (erreur,) = erreurs_de("ecris 1;\n}\necris 2;")
    assert "sans '{'" in erreur.message
    assert erreur.position == Position(2, 1)


def test_bloc_jamais_ferme() -> None:
    (erreur,) = erreurs_de("si vrai {\necris 1;")
    assert "jamais fermé" in erreur.message
    assert erreur.position == Position(1, 9)


def test_l_erreur_multiple_est_chainee_a_la_premiere() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse("var = 1;\nvar = 2;")
    assert erreur.value.__cause__ is erreur.value.erreurs[0]


def test_une_erreur_lexicale_arrete_tout_et_est_chainee() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse("var x = @;")
    assert isinstance(erreur.value.__cause__, ErreurLexicale)


def test_une_erreur_lexicale_garde_les_erreurs_de_syntaxe_precedentes() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse("var = 1;\nvar y = @;")
    genres = [type(e) for e in erreur.value.erreurs]
    assert genres == [ErreurSyntaxe, ErreurLexicale]


# --- Les exemples ---------------------------------------------------------------------


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda p: p.stem)
def test_chaque_exemple_s_analyse_sans_erreur(exemple: Path) -> None:
    programme = parse(exemple.read_text(encoding="utf-8"))
    assert programme.instructions
