from pathlib import Path

import pytest

from alto.backends import BACKENDS
from alto.compilateur import compiler
from alto.erreurs import ErreurAlto, ErreurSemantique, ErreursMultiples, ErreurSyntaxe, ErreurType
from alto.lexer import tokenize
from alto.noeuds import Declaration, Entier, Fonction, afficher_arbre
from alto.parser import parse
from alto.semantique import Analyse
from alto.tokens import TokenKind as T
from alto.typage import TYPES, Type, compatible, type_binaire, type_unaire

EXEMPLES = sorted((Path(__file__).parent.parent / "exemples").glob("*.alt"))

E, D, X, B, L, R, I = (
    Type.ENTIER,
    Type.DECIMAL,
    Type.TEXTE,
    Type.BOOLEEN,
    Type.LISTE,
    Type.RIEN,
    Type.INCONNU,
)


def erreurs_de(source: str) -> list[ErreurAlto]:
    """Les erreurs trouvées à la compilation (liste vide si le programme est accepté)."""
    try:
        compiler(source)
    except ErreursMultiples as erreurs:
        return erreurs.erreurs
    return []


def erreurs_de_type(source: str) -> list[str]:
    return [e.message for e in erreurs_de(source) if isinstance(e, ErreurType)]


# --- Le module typage ---


@pytest.mark.parametrize(
    ("attendu", "recu", "resultat"),
    [
        (E, E, True),
        (D, E, True),  # un entier est accepté là où on attend un décimal
        (E, D, False),
        (X, E, False),
        (E, I, True),  # typage graduel : l'inconnu est compatible avec tout
        (I, X, True),
        (R, R, True),
        (L, R, False),
    ],
)
def test_compatible(attendu: Type, recu: Type, resultat: bool) -> None:
    assert compatible(attendu, recu) is resultat


@pytest.mark.parametrize(
    ("op", "gauche", "droite", "attendu"),
    [
        ("+", E, E, E),
        ("+", E, D, D),
        ("+", D, D, D),
        ("+", X, X, X),
        ("+", L, L, L),
        ("+", E, X, None),
        ("+", B, E, None),
        ("+", L, X, None),
        ("+", E, I, I),
        ("+", X, I, I),
        ("+", B, I, None),
        ("-", E, E, E),
        ("*", E, D, D),
        ("%", E, E, E),
        ("*", X, E, None),
        ("-", I, I, I),
        ("/", E, E, D),
        ("/", I, I, D),
        ("/", X, E, None),
        ("==", X, E, B),
        ("!=", R, L, B),
        ("<", E, D, B),
        ("<", X, X, B),
        ("<", B, E, B),  # (a < b) < c, spécification 1.0
        ("<", L, L, B),
        ("<", X, E, None),
        ("<", R, E, None),
        ("<", I, X, B),
        ("<", I, R, None),
        ("et", B, B, B),
        ("ou", E, E, I),  # `1 ou 2` vaut 1 : pas d'erreur, mais pas un booléen
        ("et", B, I, I),
    ],
)
def test_type_binaire(op: str, gauche: Type, droite: Type, attendu: Type | None) -> None:
    assert type_binaire(op, gauche, droite) is attendu


@pytest.mark.parametrize(
    ("op", "operande", "attendu"),
    [("-", E, E), ("-", D, D), ("-", I, I), ("-", X, None), ("-", B, None), ("non", E, B)],
)
def test_type_unaire(op: str, operande: Type, attendu: Type | None) -> None:
    assert type_unaire(op, operande) is attendu


def test_les_types_annotables() -> None:
    assert sorted(TYPES) == ["booleen", "decimal", "entier", "liste", "rien", "texte"]
    assert str(Type.INCONNU) == "?"


# --- Lexer et parser ---


def test_deux_points_et_fleche_sont_des_tokens() -> None:
    kinds = [t.kind for t in tokenize("x: entier -> texte")]
    assert kinds == [T.IDENT, T.DEUX_POINTS, T.IDENT, T.FLECHE, T.IDENT, T.FIN]


def test_une_fleche_n_est_pas_un_moins_suivi_de_sup() -> None:
    assert [t.kind for t in tokenize("a - > b")][1:3] == [T.MOINS, T.SUP]


def test_une_declaration_annotee() -> None:
    (instr,) = parse("var x: entier = 3;").instructions
    assert instr == Declaration("x", Entier(3), annotation=Type.ENTIER)


def test_une_declaration_sans_annotation_garde_l_arbre_de_la_version_1() -> None:
    (instr,) = parse("var x = 3;").instructions
    assert instr == Declaration("x", Entier(3))
    assert afficher_arbre(instr) == "Declaration nom='x'\n└── valeur: Entier valeur=3"


def test_une_fonction_annotee() -> None:
    (instr,) = parse("fonction f(a: entier, b) -> texte { }").instructions
    assert isinstance(instr, Fonction)
    assert instr.parametres == ("a", "b")
    assert instr.types_parametres == (Type.ENTIER, None)
    assert instr.type_retour is Type.TEXTE


def test_une_fonction_sans_annotation_garde_l_arbre_de_la_version_1() -> None:
    (instr,) = parse("fonction f(a, b) { }").instructions
    assert isinstance(instr, Fonction)
    assert instr.types_parametres == ()
    assert instr.type_retour is None


def test_rien_est_un_type_de_retour() -> None:
    (instr,) = parse("fonction f() -> rien { }").instructions
    assert isinstance(instr, Fonction)
    assert instr.type_retour is Type.RIEN


def test_texte_reste_une_fonction_predefinie() -> None:
    assert erreurs_de('var t: texte = texte(3); ecris t + "!";') == []


@pytest.mark.parametrize(
    "source", ["var x: nombre = 1;", "var x: = 1;", "fonction f(a: 3) { }", "fonction f() -> { }"]
)
def test_un_type_inconnu_est_une_erreur_de_syntaxe(source: str) -> None:
    erreurs = erreurs_de_parse(source)
    assert erreurs
    assert all(isinstance(e, ErreurSyntaxe) for e in erreurs)
    assert "type attendu" in erreurs[0].message


def erreurs_de_parse(source: str) -> list[ErreurAlto]:
    with pytest.raises(ErreursMultiples) as erreurs:
        parse(source)
    return erreurs.value.erreurs


# --- Ce que le typage accepte ---


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda chemin: chemin.stem)
def test_chaque_exemple_est_bien_type(exemple: Path) -> None:
    assert erreurs_de(exemple.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "source",
    [
        "var x: decimal = 1;",  # entier -> décimal
        "var x: decimal = 1; x = 2;",
        "var x = 1; var y: texte = x;",  # graduel : x est de type inconnu
        "fonction f(n) { rends n; } var t: texte = f(1);",  # retour non annoté : inconnu
        "var l: liste = [1, 2]; var n: entier = l[0];",  # élément d'une liste : inconnu
        'var t: texte = "abc"[0];',
        "fonction f() -> rien { rends; }",
        "fonction f() -> rien { }",
        "fonction f(a: entier, b: decimal) -> decimal { rends a + b; } ecris f(1, 2);",
        "pour i de 1 jusqua 3 { var n: entier = i; }",  # la variable de pour est un entier
        "ecris 3 < 2 < 1, non 1, 1 ou 2, faux et (1 / 0);",  # programmes valides en 1.0
        "var x = 1; si x { }",  # condition de type inconnu
        "var n: entier = taille([1]); var t: texte = texte(n);",
        "var l = [1]; ajoute(l, 2);",
    ],
)
def test_programmes_acceptes(source: str) -> None:
    assert erreurs_de(source) == []


# --- Ce que le typage refuse ---


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('var x: entier = "a";', "'x' doit être de type entier, pas texte"),
        ("var x: entier = 1.5;", "'x' doit être de type entier, pas decimal"),
        ("var x: entier = rien;", "pas rien"),
        ('var x: entier = 1; x = "a";', "'x' doit être de type entier, pas texte"),
        ('fonction f(n: entier) { } f("a");', "l'argument 1 de 'f' doit être de type entier"),
        ('fonction f() -> entier { rends "a"; }', "la valeur rendue par 'f' doit être de type"),
        ("fonction f() -> entier { rends; }", "pas rien"),
        ('ecris 1 + "a";', "opération impossible : entier + texte"),
        ('ecris "a" * 2;', "opération impossible : texte * entier"),
        ('ecris - "a";', "opération impossible : - texte"),
        ('ecris "a" < 1;', "opération impossible : texte < entier"),
        ("ecris rien < 1;", "opération impossible : rien < entier"),
        ("ecris 3[0];", "on ne peut pas indexer une valeur de type entier"),
        ('ecris [1]["a"];', "un indice doit être de type entier, pas texte"),
        ('var t: texte = "abc"; t[0] = "x";', "un texte ne se modifie pas"),
        ("ecris taille(3);", "l'argument 1 de 'taille' ne peut pas être de type entier"),
        ('ajoute("a", 1);', "l'argument 1 de 'ajoute' ne peut pas être de type texte"),
        ("pour i de 1.5 jusqua 3 { }", "une borne de pour doit être de type entier"),
        ("pour i de 1 jusqua 3 { i = 1.5; }", "'i' doit être de type entier"),
        ("si 1 { }", "la condition doit être de type booleen, pas entier"),
        ('tantque "a" { }', "la condition doit être de type booleen, pas texte"),
        ("var n: entier = 1 / 1;", "pas decimal"),  # `/` donne toujours un décimal
    ],
)
def test_erreurs_de_type(source: str, message: str) -> None:
    messages = erreurs_de_type(source)
    assert any(message in m for m in messages), messages


def test_une_erreur_de_type_est_une_erreur_semantique() -> None:
    (erreur,) = erreurs_de('var x: entier = "a";')
    assert isinstance(erreur, ErreurType)
    assert isinstance(erreur, ErreurSemantique)
    assert erreur.genre == "erreur de type"


def test_les_erreurs_de_type_sont_collectees_avec_les_autres() -> None:
    erreurs = erreurs_de('var x: entier = "a";\necris y;\nvar z: texte = 1;')
    assert [type(e) for e in erreurs] == [ErreurType, ErreurSemantique, ErreurType]
    assert [e.position.ligne for e in erreurs if e.position] == [1, 2, 3]


def test_l_erreur_pointe_la_valeur_fautive() -> None:
    (erreur,) = erreurs_de('var x: entier = "a";')
    assert erreur.position is not None
    assert (erreur.position.ligne, erreur.position.colonne) == (1, 17)


# --- Les backends ---


def test_le_formateur_garde_les_annotations() -> None:
    # (le formateur met une ligne vide avant chaque fonction)
    source = "var x: entier = 1;\n\nfonction f(a: texte, b) -> booleen {\n    rends vrai;\n}\n"
    programme = parse(source)
    assert BACKENDS["formateur"].generer(programme, Analyse()).code == source


@pytest.mark.parametrize("backend", ["python", "ast"])
def test_les_annotations_ne_changent_pas_le_python(backend: str) -> None:
    def python(source: str) -> str:
        return BACKENDS[backend].generer(parse(source), Analyse()).code

    assert python("var x: entier = 1; fonction f(a: texte) -> rien { }") == python(
        "var x = 1; fonction f(a) { }"
    )
