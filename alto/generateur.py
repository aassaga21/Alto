"""Traduction exhaustive de l'AST Alto en Python."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
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
from alto.semantique import Analyse, analyser
from alto.sourcemap import SourceMap

PRELUDE = """def _texte(valeur):
    if valeur is True:
        return "vrai"
    if valeur is False:
        return "faux"
    if valeur is None:
        return "rien"
    if isinstance(valeur, list):
        return "[" + ", ".join(_texte(v) for v in valeur) + "]"
    return str(valeur)


def _ecris(*valeurs):
    print(" ".join(_texte(v) for v in valeurs))


def _taille(valeur):
    return len(valeur)


def _ajoute(liste, valeur):
    liste.append(valeur)


def _intervalle(debut, fin):
    if type(debut) is not int or type(fin) is not int:
        raise TypeError("les bornes de pour doivent etre des entiers")
    return range(debut, fin + 1)

"""
PREDEFINIES_PYTHON = {"taille": "_taille", "ajoute": "_ajoute", "texte": "_texte"}
OPERATEURS = {"et": "and", "ou": "or"}


def nom_python(nom: str) -> str:
    """Préfixer tous les noms évite mots-cles, builtins et normalisation Unicode."""
    return "_v_" + nom.encode("utf-8").hex()


class Liaisons:
    """Résout les noms lexicaux ; deux déclarations distinctes ont des noms distincts."""

    def __init__(self, analyse: Analyse) -> None:
        self.analyse = analyse
        self.portees: list[dict[str, str]] = [dict(PREDEFINIES_PYTHON)]
        self.compteur = 0

    @contextmanager
    def portee(self) -> Iterator[None]:
        self.portees.append({})
        try:
            yield
        finally:
            self.portees.pop()

    def declarer(self, nom: str) -> str:
        self.compteur += 1
        python = f"{nom_python(nom)}_{self.compteur}"
        self.portees[-1][nom] = python
        return python

    def chercher(self, nom: str) -> str:
        for portee in reversed(self.portees):
            if nom in portee:
                return portee[nom]
        raise ValueError(f"nom non résolu : {nom}")


class GenerateurPython(Liaisons):
    def __init__(self, analyse: Analyse) -> None:
        super().__init__(analyse)
        self.e = Emetteur()

    def expr(self, expr: Expr) -> str:
        match expr:
            case Entier(valeur) | Decimal(valeur) | Texte(valeur) | Booleen(valeur):
                return repr(valeur)
            case Rien():
                return "None"
            case Variable(nom):
                return self.chercher(nom)
            case Liste(elements):
                return "[" + ", ".join(self.expr(e) for e in elements) + "]"
            case Unaire(op, operande):
                mot = "not " if op == "non" else "-"
                return f"({mot}{self.expr(operande)})"
            case Binaire(op, gauche, droite):
                return f"({self.expr(gauche)} {OPERATEURS.get(op, op)} {self.expr(droite)})"
            case Appel(fonction, arguments):
                return f"{self.expr(fonction)}({', '.join(self.expr(a) for a in arguments)})"
            case Index(cible, indice):
                return f"({self.expr(cible)})[{self.expr(indice)}]"
            case _:
                assert_never(expr)

    def expression_affichee(self, expr: Expr) -> str:
        code = self.expr(expr)
        return code[1:-1] if isinstance(expr, (Binaire, Unaire)) else code

    def bloc(self, bloc: Bloc) -> None:
        with self.portee(), self.e.bloc():
            for instr in bloc.instructions:
                self.instruction(instr)

    def instruction(self, instr: Instr) -> None:
        e = self.e
        e.source = instr.pos.ligne
        match instr:
            case Declaration(nom, valeur):
                code = self.expr(valeur)
                e.ligne(f"{self.declarer(nom)} = {code}")
            case Affectation(cible, valeur):
                e.ligne(f"{self.expr(cible)} = {self.expr(valeur)}")
            case Ecris(valeurs):
                e.ligne(f"_ecris({', '.join(self.expression_affichee(v) for v in valeurs)})")
            case Si(branches, sinon):
                for i, branche in enumerate(branches):
                    e.source = branche.pos.ligne or instr.pos.ligne
                    e.ligne(f"{'if' if i == 0 else 'elif'} {self.expr(branche.condition)}:")
                    self.bloc(branche.corps)
                if sinon is not None:
                    e.ligne("else:")
                    self.bloc(sinon)
            case TantQue(condition, corps):
                e.ligne(f"while {self.expr(condition)}:")
                self.bloc(corps)
            case Pour(variable, debut, fin, corps):
                bornes = f"_intervalle({self.expr(debut)}, {self.expr(fin)})"
                with self.portee():
                    e.ligne(f"for {self.declarer(variable)} in {bornes}:")
                    self.bloc(corps)
            case Fonction(nom, parametres, corps):
                fonction = self.declarer(nom)
                globales = [
                    self.chercher(g)
                    for g in sorted(self.analyse.globales_modifiees.get(nom, set()))
                ]
                with self.portee():
                    params = ", ".join(self.declarer(p) for p in parametres)
                    e.ligne(f"def {fonction}({params}):")
                    with self.e.bloc():
                        if globales:
                            e.ligne("global " + ", ".join(globales))
                        with self.portee():
                            for sous_instr in corps.instructions:
                                self.instruction(sous_instr)
            case Rends(valeur):
                e.ligne("return" if valeur is None else f"return {self.expr(valeur)}")
            case ExprInstr(expr):
                e.ligne(self.expr(expr))
            case _:
                assert_never(instr)

    def programme(self, programme: Programme) -> str:
        for instr in programme.instructions:
            self.instruction(instr)
        return self.e.texte()


def generer(programme: Programme) -> str:
    """Vérifie l'arbre et produit un module Python autonome avec son prélude."""
    return PRELUDE + GenerateurPython(analyser(programme)).programme(programme)


def transpiler(source: str) -> str:
    from alto.parser import parse

    return generer(parse(source))


def executer(source: str) -> None:
    """Exécute du source Alto, comme la future façade CLI."""
    exec(compile(transpiler(source), "<alto>", "exec"), {"__name__": "__main__"})  # noqa: S102 - execution du Python produit par le compilateur.


class BackendPython:
    nom = "python"
    extension = ".py"
    executable = True

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
        generateur = GenerateurPython(analyse)
        corps = generateur.programme(programme)
        # les lignes du prélude passent avant celles du programme
        sourcemap = SourceMap(generateur.e.correspondance).decalee(len(PRELUDE.splitlines()))
        return Sortie(PRELUDE + corps, sourcemap)
