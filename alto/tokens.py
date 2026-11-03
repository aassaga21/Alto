"""Les types de token d'Alto et la classe Token."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from alto.erreurs import Position


class TokenKind(Enum):
    # Littéraux et identifiants : valeur entre chevrons
    ENTIER = "<entier>"
    DECIMAL = "<décimal>"
    TEXTE = "<texte>"
    IDENT = "<identifiant>"
    # Mots-clés
    VAR = "var"
    FONCTION = "fonction"
    RENDS = "rends"
    SI = "si"
    SINON = "sinon"
    TANTQUE = "tantque"
    POUR = "pour"
    DE = "de"
    JUSQUA = "jusqua"
    ECRIS = "ecris"
    VRAI = "vrai"
    FAUX = "faux"
    RIEN = "rien"
    ET = "et"
    OU = "ou"
    NON = "non"
    # Symboles
    PAR_G = "("
    PAR_D = ")"
    ACC_G = "{"
    ACC_D = "}"
    CROCHET_G = "["
    CROCHET_D = "]"
    VIRGULE = ","
    POINT_VIRGULE = ";"
    EGAL = "="
    EGAL_EGAL = "=="
    DIFFERENT = "!="
    INF = "<"
    INF_EGAL = "<="
    SUP = ">"
    SUP_EGAL = ">="
    PLUS = "+"
    MOINS = "-"
    FOIS = "*"
    DIVISE = "/"
    MODULO = "%"
    # Fin du source
    FIN = "<fin>"

    @property
    def est_fixe(self) -> bool:
        """Vrai pour un mot-clé ou un symbole."""
        v = self.value
        return not (len(v) > 2 and v.startswith("<") and v.endswith(">"))

    def __str__(self) -> str:
        return f"'{self.value}'" if self.est_fixe else self.value


#: Les mots réservés, indexés par leur orthographe : {"var": TokenKind.VAR, ...}
MOTS_CLES: dict[str, TokenKind] = {
    k.value: k for k in TokenKind if k.est_fixe and k.value.isalpha()
}

#: Les symboles, du plus long au plus court : [("==", EGAL_EGAL), ..., ("=", EGAL), ...]
SYMBOLES: list[tuple[str, TokenKind]] = sorted(
    ((k.value, k) for k in TokenKind if k.est_fixe and not k.value.isalpha()),
    key=lambda paire: -len(paire[0]),
)


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    lexeme: str
    position: Position

    def __repr__(self) -> str:
        p = self.position
        return f"Token({self.kind.name}, {self.lexeme!r}, {p.ligne}:{p.colonne})"
