"""Contrats de generation et tests de bout en bout des deux backends."""

import ast
from pathlib import Path

import pytest

from alto.emetteur import Emetteur
from alto.erreurs import ErreursMultiples
from alto.generateur import executer, generer, transpiler
from alto.generateur_ast import generer_ast
from alto.noeuds import Ecris, Entier, Programme
from alto.parser import parse

EXEMPLES = sorted((Path(__file__).parents[1] / "exemples").glob("*.alt"))


@pytest.fixture(params=["python", "ast"])
def backend(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def lancer(source: str, backend: str) -> None:
    code = transpiler(source) if backend == "python" else generer_ast(parse(source))
    exec(compile(code, "<alto>", "exec"), {"__name__": "__main__"})  # noqa: S102 - execution du Python produit par le compilateur.


@pytest.mark.parametrize("chemin", EXEMPLES, ids=lambda p: p.stem)
def test_exemples(chemin: Path, backend: str, capsys: pytest.CaptureFixture[str]) -> None:
    lancer(chemin.read_text(encoding="utf-8"), backend)
    assert capsys.readouterr().out == chemin.with_suffix(".attendu").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("", ""),
        ("si vrai {} fonction f() {} ecris f();", "rien\n"),
        ("var class = 7; var print = 2; var list = 3; ecris class, print, list;", "7 2 3\n"),
        ("ecris 3 < 2 < 1, 7 / 2, 4 / 2, -7 % 3;", "vrai 3.5 2.0 2\n"),
        ("ecris non 1 == 1, - - 3, faux et (1 / 0), vrai ou (1 / 0);", "faux 3 faux vrai\n"),
        ("var x = 1; fonction f() { x = x + 1; } f(); ecris x;", "2\n"),
        ("pour i de 1 jusqua 2 { ecris i; } pour i de 3 jusqua 2 { ecris i; }", "1\n2\n"),
        ("var n = 2; pour i de 1 jusqua n { n = 0; ecris i; }", "1\n2\n"),
        (
            (
                "var n = 0; fonction borne() { n = n + 1; rends 2; } "
                "pour i de 1 jusqua borne() {} ecris n;"
            ),
            "1\n",
        ),
        # Deux blocs peuvent reutiliser un nom, puis une globale du meme nom apparaitre.
        ("fonction f() { var x = 2; rends x; } var x = 9; ecris f(), x;", "2 9\n"),
        ("fonction f() { si faux { var x = 1; } var x = 2; rends x; } ecris f();", "2\n"),
        ("si vrai { var x = 1; ecris x; } si vrai { var x = 2; ecris x; }", "1\n2\n"),
        (
            "var l = [1, 2]; l[-1] = 3; ajoute(l, 4); ecris l, texte(vrai), taille(l);",
            "[1, 3, 4] vrai 3\n",
        ),
        ("fonction f() { rends; } ecris f();", "rien\n"),
        ("var x = 0; si faux { x = 1; } sinon si vrai { x = 2; } sinon { x = 3; } ecris x;", "2\n"),
        ('ecris "a\\n\\"b";', 'a\n"b\n'),
    ],
)
def test_semantique_execution(
    source: str, attendu: str, backend: str, capsys: pytest.CaptureFixture[str]
) -> None:
    lancer(source, backend)
    assert capsys.readouterr().out == attendu


@pytest.mark.parametrize(
    "source",
    [
        "ecris absente;",
        "var x = 1; var x = 2;",
        "rends 1;",
        "var x = 1; si vrai { var x = 2; }",
        "fonction f(a) {} f();",
        "si faux { var x = 1; } ecris x;",
    ],
)
def test_erreurs_semantiques(source: str, backend: str) -> None:
    with pytest.raises(ErreursMultiples):
        lancer(source, backend)


@pytest.mark.parametrize(
    "source",
    [
        # une variable sans annotation : son type est inconnu, l'erreur arrive à l'exécution
        # (avec un littéral, `pour i de 1.5 …`, le typage de l'extension 12 la signale avant)
        "var d = 1.5; pour i de d jusqua 2 {}",
        "var f = 2.5; pour i de 1 jusqua f {}",
        "var d = vrai; pour i de d jusqua 2 {}",
        "var f = faux; pour i de 1 jusqua f {}",
    ],
)
def test_bornes_entieres(source: str, backend: str) -> None:
    with pytest.raises(TypeError, match="entiers"):
        lancer(source, backend)


def test_emetteur_bloc_vide_et_exception() -> None:
    e = Emetteur()
    e.ligne("if True:")
    with e.bloc():
        pass
    assert e.texte() == "if True:\n    pass\n"
    with pytest.raises(ValueError), e.bloc():
        raise ValueError("interruption")
    assert e.niveau == 0


def test_arbre_manuel_et_facade(capsys: pytest.CaptureFixture[str]) -> None:
    code = generer(Programme((Ecris((Entier(42),)),)))
    ast.parse(code)
    exec(compile(code, "<alto>", "exec"), {})  # noqa: S102 - execution du Python produit par le compilateur.
    executer("ecris 42;")
    assert capsys.readouterr().out == "42\n42\n"
