"""Le backend Formateur : réécrit un programme Alto proprement présenté.

Les commentaires sont perdus : ils ne sont pas dans l'arbre (voir la spécification).
"""

from __future__ import annotations

import decimal
from typing import assert_never

from alto.backend import Sortie
from alto.emetteur import Emetteur
from alto.noeuds import (
    Affectation,
    Appel,
    Binaire,
    Bloc,
    Booleen,
    Decimal,
    Declaration,
    Ecris,
    Entier,
    Expr,
    ExprInstr,
    Fonction,
    Index,
    Instr,
    Liste,
    Pour,
    Programme,
    Rends,
    Rien,
    Si,
    TantQue,
    Texte,
    Unaire,
    Variable,
)
from alto.parser import Precedence, texte_source
from alto.semantique import Analyse

#: La force de chaque opérateur binaire : la même table que celle du parser.
PRECEDENCES: dict[str, Precedence] = {
    "ou": Precedence.OU,
    "et": Precedence.ET,
    "==": Precedence.COMPARAISON,
    "!=": Precedence.COMPARAISON,
    "<": Precedence.COMPARAISON,
    "<=": Precedence.COMPARAISON,
    ">": Precedence.COMPARAISON,
    ">=": Precedence.COMPARAISON,
    "+": Precedence.SOMME,
    "-": Precedence.SOMME,
    "*": Precedence.PRODUIT,
    "/": Precedence.PRODUIT,
    "%": Precedence.PRODUIT,
}


def _precedence(expr: Expr) -> int:
    match expr:
        case Binaire(op):
            return PRECEDENCES[op]
        case Unaire(op):
            return Precedence.NON if op == "non" else Precedence.PREFIXE
        case _:
            return Precedence.APPEL + 1  # un atome n'a jamais besoin de parenthèses


def _decimal_alto(valeur: float) -> str:
    """`repr` peut écrire `1e-07`, qu'Alto refuse : on écrit toujours `0.0000001`."""
    texte = format(decimal.Decimal(repr(valeur)), "f")
    return texte if "." in texte else texte + ".0"


class Formateur:
    nom = "formateur"
    extension = ".alt"
    executable = False

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
        return Sortie(self.formater(programme))

    def formater(self, programme: Programme) -> str:
        self.e = Emetteur()
        precedente: Instr | None = None
        for instr in programme.instructions:
            # une ligne vide autour de chaque fonction, pour aérer
            if precedente is not None and Fonction in (type(precedente), type(instr)):
                self.e.ligne()
            self.instruction(instr)
            precedente = instr
        return self.e.texte()

    def corps(self, bloc: Bloc) -> None:
        with self.e.bloc(vide=None):  # un bloc Alto vide n'a pas besoin de `pass`
            for instr in bloc.instructions:
                self.instruction(instr)

    def expr(self, expr: Expr, parent: int = Precedence.AUCUNE, a_droite: bool = False) -> str:
        """L'expression, entre parenthèses seulement si elles changent le sens."""
        code = self._expr(expr)
        p = _precedence(expr)
        # à droite, même niveau : `a - (b - c)` garde ses parenthèses (associatif à gauche)
        if p < parent or (a_droite and p == parent):
            return f"({code})"
        return code

    def instruction(self, instr: Instr) -> None:
        e = self.e
        match instr:
            case Declaration(nom, valeur):
                e.ligne(f"var {nom} = {self.expr(valeur)};")
            case Affectation(cible, valeur):
                e.ligne(f"{self.expr(cible)} = {self.expr(valeur)};")
            case Ecris(valeurs):
                e.ligne(f"ecris {', '.join(self.expr(v) for v in valeurs)};")
            case Si(branches, sinon):
                e.ligne(f"si {self.expr(branches[0].condition)} {{")
                self.corps(branches[0].corps)
                for branche in branches[1:]:
                    e.ligne(f"}} sinon si {self.expr(branche.condition)} {{")
                    self.corps(branche.corps)
                if sinon is not None:
                    e.ligne("} sinon {")
                    self.corps(sinon)
                e.ligne("}")
            case TantQue(condition, corps):
                e.ligne(f"tantque {self.expr(condition)} {{")
                self.corps(corps)
                e.ligne("}")
            case Pour(variable, debut, fin, corps):
                e.ligne(f"pour {variable} de {self.expr(debut)} jusqua {self.expr(fin)} {{")
                self.corps(corps)
                e.ligne("}")
            case Fonction(nom, parametres, corps):
                e.ligne(f"fonction {nom}({', '.join(parametres)}) {{")
                self.corps(corps)
                e.ligne("}")
            case Rends(valeur):
                e.ligne("rends;" if valeur is None else f"rends {self.expr(valeur)};")
            case ExprInstr(expr):
                e.ligne(f"{self.expr(expr)};")
            case _:
                assert_never(instr)

    def _expr(self, expr: Expr) -> str:
        match expr:
            case Entier(valeur):
                return str(valeur)
            case Decimal(valeur):
                return _decimal_alto(valeur)
            case Texte(valeur):
                return texte_source(valeur)
            case Booleen(valeur):
                return "vrai" if valeur else "faux"
            case Rien():
                return "rien"
            case Variable(nom):
                return nom
            case Liste(elements):
                return "[" + ", ".join(self.expr(x) for x in elements) + "]"
            case Unaire(op, operande):
                if op == "non":
                    return f"non {self.expr(operande, Precedence.NON)}"
                # `- -x` et non `--x` : plus lisible, et ce n'est pas un symbole d'Alto
                code = self.expr(operande, Precedence.PREFIXE)
                return f"- {code}" if code.startswith("-") else f"-{code}"
            case Binaire(op, gauche, droite):
                p = PRECEDENCES[op]
                return f"{self.expr(gauche, p)} {op} {self.expr(droite, p, a_droite=True)}"
            case Appel(fonction, arguments):
                appele = self.expr(fonction, Precedence.APPEL)
                return f"{appele}({', '.join(self.expr(a) for a in arguments)})"
            case Index(cible, indice):
                return f"{self.expr(cible, Precedence.APPEL)}[{self.expr(indice)}]"
            case _:
                assert_never(expr)
