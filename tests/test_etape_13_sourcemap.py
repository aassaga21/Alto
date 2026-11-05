import json
from pathlib import Path

import pytest

from alto.backend import Sortie
from alto.cli import ERREUR_EXECUTION, OK, main
from alto.compilateur import executer, executer_sortie, transpiler
from alto.erreurs import ErreurAlto, ErreurExecution, ErreurSourceMap, Position
from alto.sourcemap import SourceMap, SourceMapJson, chemin_de_la_map

SOURCE = "fonction f(l) {\n    rends l[5];\n}\necris f([1]);\n"


def ecrire(tmp_path: Path, source: str = SOURCE) -> Path:
    fichier = tmp_path / "p.alt"
    fichier.write_text(source, encoding="utf-8")
    return fichier


# --- La classe SourceMap ---


def test_ligne_source() -> None:
    sourcemap = SourceMap({5: 1, 6: 2})
    assert sourcemap.ligne_source(6) == 2
    assert sourcemap.ligne_source(1) is None  # une ligne du prélude


def test_decalee_ajoute_les_lignes_du_prelude() -> None:
    assert SourceMap({1: 1, 2: 3}, "p.alt").decalee(10) == SourceMap({11: 1, 12: 3}, "p.alt")


def test_une_source_map_est_immuable() -> None:
    sourcemap = SourceMap()
    with pytest.raises(AttributeError):
        sourcemap.source = "autre"  # type: ignore[misc]


def test_vers_json() -> None:
    attendu: SourceMapJson = {"version": 1, "source": "p.alt", "lignes": {"2": 1, "10": 3}}
    assert SourceMap({10: 3, 2: 1}, "p.alt").vers_json() == attendu


def test_les_cles_json_sont_triees_par_numero_de_ligne() -> None:
    assert list(SourceMap({10: 3, 2: 1, 9: 2}).vers_json()["lignes"]) == ["2", "9", "10"]


def test_ecrire_puis_relire_donne_la_meme(tmp_path: Path) -> None:
    sourcemap = SourceMap({30: 1, 31: 2, 32: 4}, "dossier/été.alt")
    chemin = tmp_path / "p.py.map.json"
    sourcemap.ecrire(chemin)
    assert SourceMap.lire(chemin) == sourcemap


def test_le_fichier_est_du_json_lisible(tmp_path: Path) -> None:
    chemin = tmp_path / "p.map.json"
    SourceMap({3: 1}, "p.alt").ecrire(chemin)
    assert json.loads(chemin.read_text(encoding="utf-8")) == {
        "version": 1,
        "source": "p.alt",
        "lignes": {"3": 1},
    }


def test_chemin_de_la_map() -> None:
    assert chemin_de_la_map(Path("sortie/bonjour.py")) == Path("sortie/bonjour.py.map.json")


# --- Relire : refuser ce qui n'a pas la bonne forme ---


@pytest.mark.parametrize("version", [2, 0, "1", None])
def test_une_version_inconnue_est_refusee(version: object) -> None:
    with pytest.raises(ErreurSourceMap, match="version .* inconnue"):
        SourceMap.depuis_json({"version": version, "source": "p.alt", "lignes": {}})


@pytest.mark.parametrize(
    ("donnees", "message"),
    [
        ([1, 2], "objet JSON"),
        ({"version": 1, "source": 3, "lignes": {}}, "'source'"),
        ({"version": 1, "source": "p.alt", "lignes": []}, "'lignes'"),
        ({"version": 1, "source": "p.alt", "lignes": {"a": 1}}, "ligne invalide"),
        ({"version": 1, "source": "p.alt", "lignes": {"1": "2"}}, "ligne invalide"),
        ({"version": 1, "source": "p.alt", "lignes": {"1": True}}, "ligne invalide"),
    ],
)
def test_une_forme_invalide_est_refusee(donnees: object, message: str) -> None:
    with pytest.raises(ErreurSourceMap, match=message):
        SourceMap.depuis_json(donnees)


def test_un_json_illisible_est_refuse(tmp_path: Path) -> None:
    chemin = tmp_path / "p.map.json"
    chemin.write_text("{pas du json", encoding="utf-8")
    with pytest.raises(ErreurSourceMap, match="JSON invalide"):
        SourceMap.lire(chemin)


def test_une_erreur_de_source_map_est_une_erreur_alto() -> None:
    erreur = ErreurSourceMap("version 2 inconnue")
    assert isinstance(erreur, ErreurAlto)
    assert str(erreur) == "erreur de source map : version 2 inconnue"


# --- Les backends et l'exécution ---


@pytest.mark.parametrize("backend", ["python", "ast"])
def test_chaque_ligne_alto_a_sa_ligne_python(backend: str) -> None:
    sortie = transpiler(SOURCE, backend)
    lignes = sortie.code.splitlines()
    for ligne_python, ligne_alto in sortie.sourcemap.lignes.items():
        assert 1 <= ligne_python <= len(lignes)
        assert 1 <= ligne_alto <= SOURCE.count("\n")
    assert set(sortie.sourcemap.lignes.values()) == {1, 2, 4}


@pytest.mark.parametrize("backend", ["python", "ast"])
def test_la_ligne_python_de_rends_pointe_la_ligne_alto_2(backend: str) -> None:
    sortie = transpiler(SOURCE, backend)
    lignes = sortie.code.splitlines()
    (ligne_python,) = [n for n, alto in sortie.sourcemap.lignes.items() if alto == 2]
    assert "return" in lignes[ligne_python - 1]


@pytest.mark.parametrize("backend", ["python", "ast"])
def test_une_erreur_au_fond_d_une_fonction_pointe_la_bonne_ligne(backend: str) -> None:
    with pytest.raises(ErreurExecution) as erreur:
        executer(SOURCE, backend)
    assert erreur.value.position == Position(2, 0)


def test_executer_sortie_se_sert_de_la_source_map() -> None:
    with pytest.raises(ErreurExecution) as erreur:
        executer_sortie(Sortie("x = 1\ny = x / 0\n", SourceMap({2: 9})))
    assert erreur.value.position == Position(9, 0)


# --- La ligne de commande ---


def test_transpile_sourcemap_ecrit_la_map_a_cote(tmp_path: Path) -> None:
    fichier = ecrire(tmp_path)
    sortie = tmp_path / "p.py"
    assert main(["transpile", str(fichier), "-o", str(sortie), "--sourcemap"]) == OK
    sourcemap = SourceMap.lire(tmp_path / "p.py.map.json")
    assert sourcemap.source == str(fichier)
    assert sourcemap.lignes == transpiler(SOURCE).sourcemap.lignes


def test_la_map_relue_explique_l_erreur_du_python_produit(tmp_path: Path) -> None:
    # On exécute le .py produit, puis on se sert de la .map.json pour retrouver la ligne Alto.
    fichier = ecrire(tmp_path)
    sortie = tmp_path / "p.py"
    main(["transpile", str(fichier), "-o", str(sortie), "--sourcemap"])
    sourcemap = SourceMap.lire(chemin_de_la_map(sortie))
    with pytest.raises(ErreurExecution) as erreur:
        executer_sortie(Sortie(sortie.read_text(encoding="utf-8"), sourcemap))
    assert erreur.value.position == Position(2, 0)


def test_sans_sourcemap_pas_de_fichier_map(tmp_path: Path) -> None:
    fichier = ecrire(tmp_path)
    assert main(["transpile", str(fichier), "-o", str(tmp_path / "p.py")]) == OK
    assert not (tmp_path / "p.py.map.json").exists()


def test_sourcemap_sans_o_est_refuse(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as sortie:
        main(["transpile", str(ecrire(tmp_path)), "--sourcemap"])
    assert sortie.value.code == 2
    assert "--sourcemap s'utilise avec -o" in capsys.readouterr().err


def test_run_pointe_toujours_la_ligne_alto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", str(ecrire(tmp_path))]) == ERREUR_EXECUTION
    assert "p.alt:2 : erreur d'exécution : indice hors limites" in capsys.readouterr().err
