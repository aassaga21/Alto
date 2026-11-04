"""Construction directe de l'AST et localisation des erreurs utilisateur."""

import ast

import pytest

from alto.generateur_ast import generer_ast, transpiler_ast
from alto.parser import parse


def test_arbre_python_executable(capsys: pytest.CaptureFixture[str]) -> None:
    arbre = generer_ast(parse("ecris 42;"))
    assert isinstance(arbre, ast.Module)
    exec(compile(arbre, "<alto>", "exec"), {})  # noqa: S102 - execution du Python produit par le compilateur.
    assert capsys.readouterr().out == "42\n"
    assert "_ecris(42)" in transpiler_ast("ecris 42;")


def test_ligne_erreur_dans_fonction() -> None:
    source = "fonction f() {\n  rends 1 / 0;\n}\nf();"
    arbre = generer_ast(parse(source))
    with pytest.raises(ZeroDivisionError) as erreur:
        exec(compile(arbre, "<alto>", "exec"), {})  # noqa: S102 - execution du Python produit par le compilateur.
    trace = erreur.value.__traceback__
    lignes = []
    while trace is not None:
        if trace.tb_frame.f_code.co_filename == "<alto>":
            lignes.append(trace.tb_lineno)
        trace = trace.tb_next
    assert lignes == [4, 2]


def test_ast_utilisateur_construit_sans_parser_python(monkeypatch: pytest.MonkeyPatch) -> None:
    original = ast.parse

    def verifier(source: str) -> ast.Module:
        from alto.generateur import PRELUDE

        assert source == PRELUDE
        return original(source)

    monkeypatch.setattr(ast, "parse", verifier)
    arbre = generer_ast(parse("var x = 2; ecris x + 1;"))
    assert isinstance(arbre.body[-1], ast.Expr)
