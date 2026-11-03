from collections.abc import Iterator
from pathlib import Path

import pytest

from alto.erreurs import ErreurLexicale, ErreursMultiples, ErreurSyntaxe, Position, formater
from alto.flux import Flux
from alto.lexer import tokenize
from alto.tokens import TokenKind as T

EXEMPLES = sorted((Path(__file__).parent.parent / "exemples").glob("*.alt"))


def kinds(source: str) -> list[T]:
    """Petit utilitaire : juste les types des tokens."""
    return [token.kind for token in tokenize(source)]


# --- Cas qui marchent ---


def test_une_declaration_donne_les_bons_tokens() -> None:
    assert kinds("var x = 3;") == [T.VAR, T.IDENT, T.EGAL, T.ENTIER, T.POINT_VIRGULE, T.FIN]


def test_un_source_vide_ne_donne_que_fin() -> None:
    assert kinds("") == [T.FIN]


def test_le_dernier_token_est_fin_avec_sa_position() -> None:
    tokens = list(tokenize("var x = 1.5;"))
    assert tokens[-1].kind is T.FIN
    assert tokens[-1].position == Position(1, 13)


def test_positions_apres_un_saut_de_ligne() -> None:
    tokens = list(tokenize("var x = 1;\n  ecris x;"))
    assert tokens[5].position == Position(2, 3)  # ecris
    assert tokens[6].position == Position(2, 9)  # x


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("==", T.EGAL_EGAL),
        ("=", T.EGAL),
        ("<=", T.INF_EGAL),
        ("<", T.INF),
        (">=", T.SUP_EGAL),
        (">", T.SUP),
        ("!=", T.DIFFERENT),
    ],
)
def test_symboles(source: str, attendu: T) -> None:
    assert kinds(source) == [attendu, T.FIN]


def test_deux_egal_colles_forment_un_seul_token() -> None:
    assert kinds("x==1") == [T.IDENT, T.EGAL_EGAL, T.ENTIER, T.FIN]


def test_tous_les_mots_cles_sont_reconnus() -> None:
    source = "var fonction rends si sinon tantque pour de jusqua ecris vrai faux rien et ou non"
    assert T.IDENT not in kinds(source)


def test_un_decimal_et_un_entier() -> None:
    assert kinds("1.5 2") == [T.DECIMAL, T.ENTIER, T.FIN]


def test_le_lexeme_d_un_nombre_est_son_texte() -> None:
    tokens = list(tokenize("007 3.14"))
    assert [t.lexeme for t in tokens[:2]] == ["007", "3.14"]


def test_un_moins_devant_un_nombre_est_un_token_separe() -> None:
    assert kinds("-3") == [T.MOINS, T.ENTIER, T.FIN]


def test_un_point_final_n_est_pas_un_decimal() -> None:
    # `1.` : l'entier 1, puis un `.` qui n'est pas un symbole d'Alto.
    with pytest.raises(ErreurLexicale) as erreur:
        list(tokenize("1."))
    assert erreur.value.position == Position(1, 2)


def test_deux_points_de_suite() -> None:
    # `1..2` : l'entier 1, puis le premier `.` est refusé.
    with pytest.raises(ErreurLexicale) as erreur:
        list(tokenize("1..2"))
    assert erreur.value.position == Position(1, 2)


def test_un_texte_est_decode() -> None:
    token = next(tokenize(r'"a\nb\"c"'))
    assert token.kind is T.TEXTE
    assert token.lexeme == 'a\nb"c'


def test_tous_les_echappements() -> None:
    token = next(tokenize(r'"\n\t\"\\"'))
    assert token.lexeme == '\n\t"\\'


def test_un_texte_vide() -> None:
    token = next(tokenize('""'))
    assert token.kind is T.TEXTE
    assert token.lexeme == ""


def test_un_diese_dans_un_texte_n_est_pas_un_commentaire() -> None:
    token = next(tokenize('"#1"'))
    assert token.lexeme == "#1"


def test_les_commentaires_sont_ignores() -> None:
    assert kinds("# rien à voir\nvar") == [T.VAR, T.FIN]


def test_un_commentaire_en_fin_de_ligne() -> None:
    assert kinds("var x = 1; # un commentaire") == [
        T.VAR,
        T.IDENT,
        T.EGAL,
        T.ENTIER,
        T.POINT_VIRGULE,
        T.FIN,
    ]


def test_un_mot_cle_n_est_pas_un_prefixe_d_identifiant() -> None:
    assert kinds("sinon_si variable") == [T.IDENT, T.IDENT, T.FIN]


def test_la_casse_compte() -> None:
    assert kinds("Si VAR") == [T.IDENT, T.IDENT, T.FIN]


def test_un_identifiant_accentue_ne_decale_pas_les_colonnes() -> None:
    tokens = list(tokenize("déjà = 1;"))
    assert tokens[0].kind is T.IDENT
    assert tokens[0].lexeme == "déjà"
    assert tokens[1].position == Position(1, 6)


def test_un_identifiant_peut_contenir_des_chiffres_et_des_tirets_bas() -> None:
    token = next(tokenize("total_2"))
    assert token.kind is T.IDENT
    assert token.lexeme == "total_2"


def test_les_retours_chariot_windows_sont_ignores() -> None:
    tokens = list(tokenize("var\r\nx"))
    assert [t.kind for t in tokens] == [T.VAR, T.IDENT, T.FIN]
    assert tokens[1].position == Position(2, 1)


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda chemin: chemin.stem)
def test_chaque_exemple_se_decoupe_sans_erreur(exemple: Path) -> None:
    tokens = list(tokenize(exemple.read_text(encoding="utf-8")))
    assert tokens[-1].kind is T.FIN


# --- Erreurs ---


@pytest.mark.parametrize(
    ("source", "message", "position"),
    [
        ("var x = 1 @ 2;", "caractère inattendu", Position(1, 11)),
        ("ecris x!;", "caractère inattendu", Position(1, 8)),
        ('ecris "abc', "texte non terminé", Position(1, 7)),
        ('ecris "abc\n";', "texte non terminé", Position(1, 7)),
        (r'ecris "a\q";', "échappement invalide", Position(1, 9)),
        ('ecris "a\\', "échappement invalide", Position(1, 9)),
        ("var _x = 1;", "ne peut pas commencer par '_'", Position(1, 5)),
        ("var x = 1;\nvar y = $;", "caractère inattendu", Position(2, 9)),
    ],
)
def test_erreurs_lexicales(source: str, message: str, position: Position) -> None:
    with pytest.raises(ErreurLexicale) as erreur:
        list(tokenize(source))
    assert message in erreur.value.message
    assert erreur.value.position == position


def test_tokenize_est_paresseux() -> None:
    tokens = tokenize("1 + 2 @")
    assert [next(tokens).kind for _ in range(3)] == [T.ENTIER, T.PLUS, T.ENTIER]
    with pytest.raises(ErreurLexicale):
        next(tokens)


# --- Flux ---


def test_flux_regarde_ne_consomme_pas() -> None:
    flux = Flux([1, 2, 3])
    assert flux.regarde() == 1
    assert flux.regarde(1) == 2
    assert flux.avance() == 1
    assert flux.regarde() == 2


def test_flux_ne_tire_que_le_necessaire() -> None:
    demandes: list[int] = []

    def source() -> Iterator[int]:
        for i in range(10):
            demandes.append(i)
            yield i

    flux = Flux(source())
    flux.regarde(1)
    assert demandes == [0, 1]


def test_flux_regarde_au_dela_de_la_fin_renvoie_none() -> None:
    flux = Flux([1])
    assert flux.regarde(1) is None


def test_flux_avance_sur_un_flux_vide_leve_index_error() -> None:
    flux: Flux[int] = Flux([])
    with pytest.raises(IndexError):
        flux.avance()


def test_flux_compte_les_elements_consommes() -> None:
    flux = Flux("abc")
    flux.avance()
    flux.regarde(1)
    flux.avance()
    assert flux.consommes == 2


def test_flux_de_tokens() -> None:
    flux = Flux(tokenize("var x"))
    assert flux.regarde(1) is not None
    assert flux.avance().kind is T.VAR
    assert flux.avance().kind is T.IDENT
    assert flux.avance().kind is T.FIN
    assert flux.regarde() is None


# --- formater ---


def test_formater_place_le_chapeau_sous_la_colonne() -> None:
    erreur = ErreurLexicale("caractère inattendu : '@'", Position(1, 9))
    assert formater(erreur, "var x = @;", "p.alt") == (
        "p.alt:1:9 : erreur lexicale : caractère inattendu : '@'\n    var x = @;\n            ^"
    )


def test_formater_montre_la_bonne_ligne() -> None:
    erreur = ErreurLexicale("texte non terminé", Position(2, 7))
    assert formater(erreur, 'var x = 1;\necris "abc', "p.alt") == (
        'p.alt:2:7 : erreur lexicale : texte non terminé\n    ecris "abc\n          ^'
    )


def test_formater_sans_position() -> None:
    erreur = ErreurLexicale("fichier vide")
    assert formater(erreur, "", "p.alt") == "p.alt : erreur lexicale : fichier vide"


def test_formater_sans_colonne_n_affiche_pas_de_chapeau() -> None:
    erreur = ErreurLexicale("division par zéro", Position(1, 0))
    assert formater(erreur, "ecris 1 / 0;", "p.alt") == (
        "p.alt:1 : erreur lexicale : division par zéro\n    ecris 1 / 0;"
    )


def test_formater_plusieurs_erreurs() -> None:
    erreurs = ErreursMultiples(
        [
            ErreurSyntaxe("';' attendu", Position(1, 2)),
            ErreurSyntaxe("';' attendu", Position(2, 2)),
        ]
    )
    texte = formater(erreurs, "a\nb", "p.alt")
    assert texte.count("erreur de syntaxe") == 2
    assert texte.startswith("p.alt:1:2 :")
