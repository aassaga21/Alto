"""Le lexer d'Alto : texte source -> tokens."""

from collections.abc import Iterator

from alto.erreurs import ErreurLexicale, Position
from alto.tokens import MOTS_CLES, SYMBOLES, Token
from alto.tokens import TokenKind as T

ECHAPPEMENTS = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _est_chiffre(c: str) -> bool:
    return "0" <= c <= "9"


def _continue_un_identifiant(c: str) -> bool:
    """Une lettre, un chiffre ASCII ou `_` (pas `²`, que Python refuserait dans un nom)."""
    return c.isalpha() or _est_chiffre(c) or c == "_"


def tokenize(source: str) -> Iterator[Token]:
    """Découpe `source` en tokens, le dernier étant toujours `FIN`."""
    i = 0  # l'indice du caractère courant
    ligne = 1  # la ligne courante
    debut_ligne = 0  # l'indice du premier caractère de la ligne courante
    n = len(source)

    while i < n:
        c = source[i]
        pos = Position(ligne, i - debut_ligne + 1)

        if c == "\n":
            i += 1
            ligne += 1
            debut_ligne = i
            continue

        if c in " \t\r":
            i += 1
            continue

        if c == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if _est_chiffre(c):
            debut = i
            while i < n and _est_chiffre(source[i]):
                i += 1
            # un point SUIVI d'un chiffre : c'est un décimal
            if i + 1 < n and source[i] == "." and _est_chiffre(source[i + 1]):
                i += 1
                while i < n and _est_chiffre(source[i]):
                    i += 1
                yield Token(T.DECIMAL, source[debut:i], pos)
            else:
                yield Token(T.ENTIER, source[debut:i], pos)
            continue

        if c.isalpha() or c == "_":
            debut = i
            while i < n and _continue_un_identifiant(source[i]):
                i += 1
            mot = source[debut:i]
            if mot.startswith("_"):
                raise ErreurLexicale("un identifiant ne peut pas commencer par '_'", pos)
            yield Token(MOTS_CLES.get(mot, T.IDENT), mot, pos)
            continue

        if c == '"':
            i += 1
            morceaux: list[str] = []
            while True:
                if i >= n or source[i] == "\n":
                    raise ErreurLexicale("texte non terminé", pos)
                ch = source[i]
                if ch == '"':
                    i += 1
                    break
                if ch == "\\":
                    suivant = source[i + 1] if i + 1 < n else ""
                    if suivant not in ECHAPPEMENTS:
                        raise ErreurLexicale(
                            f"échappement invalide : \\{suivant}",
                            Position(ligne, i - debut_ligne + 1),
                        )
                    morceaux.append(ECHAPPEMENTS[suivant])
                    i += 2
                    continue
                morceaux.append(ch)
                i += 1
            yield Token(T.TEXTE, "".join(morceaux), pos)
            continue

        for symbole, kind in SYMBOLES:
            if source.startswith(symbole, i):
                yield Token(kind, symbole, pos)
                i += len(symbole)
                break
        else:
            raise ErreurLexicale(f"caractère inattendu : {c!r}", pos)

    yield Token(T.FIN, "", Position(ligne, i - debut_ligne + 1))
