import dataclasses

import pytest

from alto.erreurs import Position
from alto.tokens import MOTS_CLES, SYMBOLES, Token, TokenKind

#: Les mots-clés et les symboles listés dans la section « Lexique » de specification.md.
MOTS_CLES_DE_LA_SPEC = [
    "var",
    "fonction",
    "rends",
    "si",
    "sinon",
    "tantque",
    "pour",
    "de",
    "jusqua",
    "ecris",
    "vrai",
    "faux",
    "rien",
    "et",
    "ou",
    "non",
]
SYMBOLES_DE_LA_SPEC = [
    "(",
    ")",
    "{",
    "}",
    "[",
    "]",
    ",",
    ";",
    "=",
    "==",
    "!=",
    "<",
    "<=",
    ">",
    ">=",
    "+",
    "-",
    "*",
    "/",
    "%",
]


def test_un_token_est_immuable() -> None:
    token = Token(TokenKind.VAR, "var", Position(1, 1))
    with pytest.raises(dataclasses.FrozenInstanceError):
        token.lexeme = "autre"  # type: ignore[misc]


def test_un_token_est_hachable() -> None:
    token = Token(TokenKind.VAR, "var", Position(1, 1))
    assert token in {token}


def test_deux_tokens_identiques_sont_egaux() -> None:
    assert Token(TokenKind.IDENT, "x", Position(2, 5)) == Token(
        TokenKind.IDENT, "x", Position(2, 5)
    )


def test_repr_tient_sur_une_ligne() -> None:
    assert repr(Token(TokenKind.VAR, "var", Position(1, 1))) == "Token(VAR, 'var', 1:1)"


def test_mots_cles_ne_contient_que_des_mots() -> None:
    assert MOTS_CLES["var"] is TokenKind.VAR
    assert MOTS_CLES["jusqua"] is TokenKind.JUSQUA
    assert all(mot.isalpha() for mot in MOTS_CLES)


def test_mots_cles_contient_tous_les_mots_cles_de_la_spec() -> None:
    assert sorted(MOTS_CLES) == sorted(MOTS_CLES_DE_LA_SPEC)


def test_symboles_contient_tous_les_symboles_de_la_spec() -> None:
    assert sorted(symbole for symbole, _ in SYMBOLES) == sorted(SYMBOLES_DE_LA_SPEC)


def test_symboles_ne_contient_aucun_mot_cle() -> None:
    assert not any(symbole.isalpha() for symbole, _ in SYMBOLES)


@pytest.mark.parametrize(("court", "long"), [("=", "=="), ("<", "<="), (">", ">=")])
def test_un_symbole_long_passe_avant_son_prefixe(court: str, long: str) -> None:
    ordre = [symbole for symbole, _ in SYMBOLES]
    assert ordre.index(long) < ordre.index(court)


@pytest.mark.parametrize(
    ("kind", "texte"),
    [
        (TokenKind.POINT_VIRGULE, "';'"),
        (TokenKind.IDENT, "<identifiant>"),
        (TokenKind.INF, "'<'"),
        (TokenKind.INF_EGAL, "'<='"),
        (TokenKind.FIN, "<fin>"),
    ],
)
def test_str_d_un_type_de_token(kind: TokenKind, texte: str) -> None:
    assert str(kind) == texte


@pytest.mark.parametrize(
    "kind", [TokenKind.ENTIER, TokenKind.DECIMAL, TokenKind.TEXTE, TokenKind.IDENT, TokenKind.FIN]
)
def test_les_tokens_variables_ne_sont_pas_fixes(kind: TokenKind) -> None:
    assert not kind.est_fixe


def test_str_d_une_position() -> None:
    assert str(Position(3, 7)) == "ligne 3, colonne 7"


def test_decalee_avance_de_n_colonnes_sur_la_meme_ligne() -> None:
    assert Position(2, 5).decalee(3) == Position(2, 8)
