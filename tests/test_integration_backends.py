"""Contrat Backend, facade et CLI : regression de l'integration apres pull."""

from pathlib import Path

import pytest

from alto.backends import BACKENDS
from alto.cli import ERREUR_EXECUTION, OK, main
from alto.compilateur import executer, transpiler
from alto.erreurs import ErreurAlto, ErreurExecution, Position

EXEMPLES = sorted((Path(__file__).parents[1] / "exemples").glob("*.alt"))


@pytest.mark.parametrize("backend", ["python", "ast"])
@pytest.mark.parametrize("chemin", EXEMPLES, ids=lambda p: p.stem)
def test_run_exemples(backend: str, chemin: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", str(chemin), "--backend", backend]) == OK
    assert capsys.readouterr().out == chemin.with_suffix(".attendu").read_text(encoding="utf-8")


@pytest.mark.parametrize("backend", ["python", "ast"])
@pytest.mark.parametrize(
    ("source", "ligne"),
    [
        ("var x = 1;\necris x / 0;", 2),
        ("fonction f(l) {\n rends l[5];\n}\necris f([1]);", 2),
        ("si faux {} sinon si vrai {\n ecris 1 / 0;\n}", 2),
        ("pour i de 1 jusqua 2 {\n ecris 1 / 0;\n}", 2),
        ("ecris taille(1);", 1),
        ("pour i de 1 jusqua 2.5 {}", 1),
    ],
)
def test_erreur_ligne_source(backend: str, source: str, ligne: int) -> None:
    with pytest.raises(ErreurExecution) as erreur:
        executer(source, backend=backend)
    assert erreur.value.position == Position(ligne, 0)


@pytest.mark.parametrize("backend", ["python", "ast"])
def test_transpile_cli_sortie_executable(
    backend: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "p.alt"
    destination = tmp_path / "p.py"
    source.write_text("ecris 42;", encoding="utf-8")
    assert main(["transpile", str(source), "--backend", backend, "-o", str(destination)]) == OK
    assert capsys.readouterr().out == ""
    exec(compile(destination.read_text(encoding="utf-8"), str(destination), "exec"), {})  # noqa: S102 - test du code genere.
    assert capsys.readouterr().out == "42\n"


@pytest.mark.parametrize("backend", ["python", "ast"])
def test_erreur_cli_sans_traceback(
    backend: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "p.alt"
    source.write_text("var x = 1;\necris x / 0;", encoding="utf-8")
    assert main(["run", str(source), "--backend", backend]) == ERREUR_EXECUTION
    message = capsys.readouterr().err
    assert "p.alt:2" in message
    assert "Traceback" not in message


def test_backend_inconnu() -> None:
    with pytest.raises(ErreurAlto, match="backend inconnu"):
        transpiler("ecris 1;", backend="absent")


def test_registre_extensible_et_backend_non_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    from alto.backend import Sortie
    from alto.noeuds import Programme
    from alto.semantique import Analyse

    class Compteur:
        nom = "compteur"
        extension = ".txt"
        executable = False

        def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
            return Sortie(str(len(programme.instructions)))

    monkeypatch.setitem(BACKENDS, "compteur", Compteur())
    assert transpiler("ecris 1;", backend="compteur").code == "1"
    with pytest.raises(ErreurAlto, match="executable"):
        executer("ecris 1;", backend="compteur")
