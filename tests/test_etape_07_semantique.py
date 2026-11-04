"""Étape 7 : l'analyse sémantique.

Le parser n'existe pas encore : les arbres sont construits à la main. Quand `parse` sera
prêt, les tests sur les exemples (en bas du fichier) s'activeront tout seuls.
"""

from functools import singledispatchmethod
from pathlib import Path

import pytest

from alto.erreurs import ErreurSemantique, ErreursMultiples, Position
from alto.noeuds import (
    Affectation,
    Appel,
    Binaire,
    Bloc,
    Booleen,
    Branche,
    Declaration,
    Ecris,
    Entier,
    ExprInstr,
    Fonction,
    Index,
    Instr,
    Liste,
    Pour,
    Programme,
    Rends,
    Si,
    TantQue,
    Variable,
)
from alto.semantique import Analyseur, analyser
from alto.symboles import Genre, Symbole, TableSymboles

EXEMPLES = Path(__file__).parent.parent / "exemples"


# --- Petits raccourcis pour écrire les arbres -------------------------------------


def prog(*instructions: Instr) -> Programme:
    return Programme(instructions)


def bloc(*instructions: Instr) -> Bloc:
    return Bloc(instructions)


def var(nom: str, valeur: int = 1) -> Declaration:
    """`var nom = valeur;`"""
    return Declaration(nom, Entier(valeur))


def ecris(nom: str) -> Ecris:
    """`ecris nom;`"""
    return Ecris((Variable(nom),))


def appel(nom: str, *arguments: int) -> Appel:
    """`nom(1, 2, ...)`"""
    return Appel(Variable(nom), tuple(Entier(a) for a in arguments))


def si_vrai(*instructions: Instr) -> Si:
    """`si vrai { ... }`"""
    return Si((Branche(Booleen(True), bloc(*instructions)),), None)


def messages(programme: Programme) -> list[str]:
    with pytest.raises(ErreursMultiples) as erreur:
        analyser(programme)
    return [e.message for e in erreur.value.erreurs]


# --- Les programmes corrects --------------------------------------------------------


@pytest.mark.parametrize(
    ("nom", "programme"),
    [
        ("programme vide", prog()),
        ("déclaration puis lecture", prog(var("x"), ecris("x"))),
        ("affectation", prog(var("x"), Affectation(Variable("x"), Entier(2)))),
        (
            # si vrai { var x = 1; } si vrai { var x = 2; }
            "deux blocs frères réutilisent un nom",
            prog(si_vrai(var("x")), si_vrai(var("x"))),
        ),
        (
            # pour i de 1 jusqua 3 { } pour i de 1 jusqua 3 { }
            "deux boucles pour i à la suite",
            prog(
                Pour("i", Entier(1), Entier(3), bloc()),
                Pour("i", Entier(1), Entier(3), bloc()),
            ),
        ),
        (
            # fonction f(n) { rends f(n - 1); }
            "fonction récursive",
            prog(
                Fonction(
                    "f",
                    ("n",),
                    bloc(Rends(Appel(Variable("f"), (Binaire("-", Variable("n"), Entier(1)),)))),
                )
            ),
        ),
        ("fonction sans paramètre", prog(Fonction("f", (), bloc()), ExprInstr(appel("f")))),
        ("rends sans valeur", prog(Fonction("f", (), bloc(Rends(None))))),
        (
            # var l = [1]; l[0] = 5; ajoute(l, 2); ecris taille(l), texte(1);
            "listes et prédéfinies",
            prog(
                Declaration("l", Liste((Entier(1),))),
                Affectation(Index(Variable("l"), Entier(0)), Entier(5)),
                ExprInstr(Appel(Variable("ajoute"), (Variable("l"), Entier(2)))),
                Ecris((Appel(Variable("taille"), (Variable("l"),)), appel("texte", 1))),
            ),
        ),
        (
            # tantque faux { } si vrai { } sinon { }
            "blocs vides",
            prog(TantQue(Booleen(False), bloc()), Si((Branche(Booleen(True), bloc()),), bloc())),
        ),
        ("expression seule", prog(ExprInstr(Binaire("+", Entier(1), Entier(2))))),
    ],
)
def test_programmes_corrects(nom: str, programme: Programme) -> None:
    analyser(programme)  # ne lève rien


# --- Une règle de la spécification = au moins un test --------------------------------


@pytest.mark.parametrize(
    ("programme", "fragment"),
    [
        # ecris x;
        (prog(ecris("x")), "'x' n'est pas déclaré"),
        # x = 1;
        (prog(Affectation(Variable("x"), Entier(1))), "'x' n'est pas déclaré"),
        # var x = x;
        (prog(Declaration("x", Variable("x"))), "'x' n'est pas déclaré"),
        # var x = 1; var x = 2;
        (prog(var("x"), var("x", 2)), "déjà déclaré"),
        # var x = 1; si vrai { var x = 2; }   (pas de masquage)
        (prog(var("x"), si_vrai(var("x", 2))), "déjà déclaré"),
        # si vrai { var y = 1; } ecris y;
        (prog(si_vrai(var("y")), ecris("y")), "'y' n'est pas déclaré"),
        # pour i de 1 jusqua 3 { } ecris i;
        (prog(Pour("i", Entier(1), Entier(3), bloc()), ecris("i")), "'i' n'est pas déclaré"),
        # var i = 0; pour i de 1 jusqua 3 { }
        (prog(var("i"), Pour("i", Entier(1), Entier(3), bloc())), "déjà déclaré"),
        # var taille = 3;
        (prog(var("taille", 3)), "prédéfinie"),
        # taille = 3;
        (prog(Affectation(Variable("taille"), Entier(3))), "on ne peut pas lui affecter"),
        # rends 1;
        (prog(Rends(Entier(1))), "en dehors d'une fonction"),
        # si vrai { fonction f() { } }
        (prog(si_vrai(Fonction("f", (), bloc()))), "niveau global"),
        # fonction f() { } fonction f() { }
        (prog(Fonction("f", (), bloc()), Fonction("f", (), bloc())), "déjà déclaré"),
        # fonction f(a, a) { }
        (prog(Fonction("f", ("a", "a"), bloc())), "déjà déclaré"),
        # fonction f() { } f = 1;
        (
            prog(Fonction("f", (), bloc()), Affectation(Variable("f"), Entier(1))),
            "on ne peut pas lui affecter",
        ),
        # ecris g(1);
        (prog(Ecris((appel("g", 1),))), "fonction inconnue : 'g'"),
        # g(); fonction g() { }   (appelée avant sa déclaration)
        (prog(ExprInstr(appel("g")), Fonction("g", (), bloc())), "fonction inconnue : 'g'"),
        # fonction f(a) { rends a; } ecris f(1, 2);
        (
            prog(
                Fonction("f", ("a",), bloc(Rends(Variable("a")))),
                Ecris((appel("f", 1, 2),)),
            ),
            "'f' attend 1 argument(s), en reçoit 2",
        ),
        # ecris taille();
        (prog(Ecris((appel("taille"),))), "'taille' attend 1 argument(s), en reçoit 0"),
        # var x = 1; x();
        (prog(var("x"), ExprInstr(appel("x"))), "variable, on ne peut pas l'appeler"),
        # fonction f() { } ecris f;
        (prog(Fonction("f", (), bloc()), ecris("f")), "'f' est une fonction, pas une valeur"),
        # fonction f() { } var g = f;
        (
            prog(Fonction("f", (), bloc()), Declaration("g", Variable("f"))),
            "'f' est une fonction, pas une valeur",
        ),
        # fonction f() { } f()(2);
        (
            prog(Fonction("f", (), bloc()), ExprInstr(Appel(appel("f"), (Entier(2),)))),
            "seule une fonction nommée",
        ),
        # var t = [1]; t[0](1);
        (
            prog(
                Declaration("t", Liste((Entier(1),))),
                ExprInstr(Appel(Index(Variable("t"), Entier(0)), (Entier(1),))),
            ),
            "seule une fonction nommée",
        ),
        # fonction f() { } var x = 1;   ... la fonction ne voit pas x, déclaré après elle
        (
            prog(Fonction("f", (), bloc(ecris("x"))), var("x")),
            "'x' n'est pas déclaré",
        ),
    ],
)
def test_regles_semantiques(programme: Programme, fragment: str) -> None:
    assert any(fragment in message for message in messages(programme))


# --- Toutes les erreurs, avec leur position ---------------------------------------


def test_toutes_les_erreurs_sont_signalees() -> None:
    # ecris a; ecris b;
    assert len(messages(prog(ecris("a"), ecris("b")))) == 2


def test_les_erreurs_des_arguments_sont_aussi_signalees() -> None:
    # ecris g(a);   → g inconnue ET a non déclaré
    assert len(messages(prog(Ecris((Appel(Variable("g"), (Variable("a"),)),))))) == 2


def test_l_erreur_porte_la_position_du_noeud_fautif() -> None:
    # ligne 2 :   ecris y;
    programme = prog(var("x"), Ecris((Variable("y", Position(2, 7)),)))
    with pytest.raises(ErreursMultiples) as erreur:
        analyser(programme)
    (seule,) = erreur.value.erreurs
    assert isinstance(seule, ErreurSemantique)
    assert seule.position == Position(2, 7)


def test_l_erreur_multiple_est_chainee_a_la_premiere() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        analyser(prog(ecris("a"), ecris("b")))
    assert erreur.value.__cause__ is erreur.value.erreurs[0]


def test_la_double_declaration_rappelle_la_premiere_position() -> None:
    programme = prog(
        Declaration("x", Entier(1), Position(1, 1)), Declaration("x", Entier(2), Position(3, 1))
    )
    assert any("ligne 1, colonne 1" in m for m in messages(programme))


# --- Ce que l'analyse transmet au générateur --------------------------------------


def test_globales_modifiees() -> None:
    # var a = 0; var b = 0; fonction f() { a = 1; ecris b; }
    programme = prog(
        var("a", 0),
        var("b", 0),
        Fonction("f", (), bloc(Affectation(Variable("a"), Entier(1)), ecris("b"))),
    )
    assert analyser(programme).globales_modifiees == {"f": {"a"}}  # b est lue, pas modifiée


def test_un_parametre_ou_une_locale_ne_sont_pas_des_globales() -> None:
    # var n = 0; fonction f(p) { var l = 0; l = 1; p = 2; }
    programme = prog(
        var("n", 0),
        Fonction(
            "f",
            ("p",),
            bloc(
                var("l", 0),
                Affectation(Variable("l"), Entier(1)),
                Affectation(Variable("p"), Entier(2)),
            ),
        ),
    )
    assert analyser(programme).globales_modifiees == {"f": set()}


def test_modifier_un_element_d_une_liste_globale_n_est_pas_une_affectation() -> None:
    # var l = [1]; fonction f() { l[0] = 2; }   → pas besoin de `global l` en Python
    programme = prog(
        Declaration("l", Liste((Entier(1),))),
        Fonction("f", (), bloc(Affectation(Index(Variable("l"), Entier(0)), Entier(2)))),
    )
    assert analyser(programme).globales_modifiees == {"f": set()}


# --- La table des symboles ----------------------------------------------------------


def test_la_portee_est_refermee_meme_en_cas_d_exception() -> None:
    table = TableSymboles()
    with pytest.raises(ValueError), table.portee():
        raise ValueError
    assert table.profondeur == 0


def test_chercher_va_de_la_portee_du_haut_vers_le_bas() -> None:
    table = TableSymboles()
    with table.portee("globale"):
        table.declarer(Symbole("a", Genre.VARIABLE, Position(1, 1)))
        with table.portee():
            table.declarer(Symbole("b", Genre.VARIABLE, Position(2, 1)))
            assert table.chercher("a") is not None
            assert table.chercher("b") is not None
            assert table.est_globale("a")
            assert not table.est_globale("b")
        assert table.chercher("b") is None  # la portée du bloc est refermée


def test_l_analyseur_utilise_singledispatchmethod() -> None:
    assert isinstance(Analyseur.__dict__["instruction"], singledispatchmethod)
    assert isinstance(Analyseur.__dict__["expression"], singledispatchmethod)


# --- Les exemples (s'activent quand le parser existera) ----------------------------


@pytest.mark.parametrize("fichier", sorted(EXEMPLES.glob("*.alt")), ids=lambda f: f.name)
def test_les_exemples_passent_l_analyse(fichier: Path) -> None:
    parser = pytest.importorskip("alto.parser", reason="le parser n'est pas encore écrit")
    analyser(parser.parse(fichier.read_text(encoding="utf-8")))
