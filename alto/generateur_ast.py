"""Backend AST : construction directe de noeuds Python, sans reparsing du programme."""

from __future__ import annotations

import ast
from typing import assert_never

from alto.backend import Sortie
from alto.generateur import PRELUDE, Liaisons
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
from alto.parser import parse
from alto.semantique import Analyse, analyser

ARITHMETIQUE: dict[str, type[ast.operator]] = {
    "+": ast.Add,
    "-": ast.Sub,
    "*": ast.Mult,
    "/": ast.Div,
    "%": ast.Mod,
}
COMPARAISONS: dict[str, type[ast.cmpop]] = {
    "==": ast.Eq,
    "!=": ast.NotEq,
    "<": ast.Lt,
    "<=": ast.LtE,
    ">": ast.Gt,
    ">=": ast.GtE,
}


def positionner[N: ast.expr | ast.stmt](python: N, alto: Expr | Instr) -> N:
    python.lineno = max(1, alto.pos.ligne)
    # Les colonnes de l'AST Python sont des offsets UTF-8. On conserve ici
    # la ligne source et utilise la colonne 0 plutot qu'une conversion inexacte.
    python.col_offset = 0
    python.end_lineno = python.lineno
    python.end_col_offset = 0
    return python


def appel(nom: str, args: list[ast.expr]) -> ast.Call:
    return ast.Call(func=ast.Name(id=nom, ctx=ast.Load()), args=args, keywords=[])


class GenerateurAst(Liaisons):
    nom = "ast"
    executable = True

    def expr(self, expr: Expr) -> ast.expr:
        resultat: ast.expr
        match expr:
            case Entier(valeur) | Decimal(valeur) | Texte(valeur) | Booleen(valeur):
                resultat = ast.Constant(value=valeur)
            case Rien():
                resultat = ast.Constant(value=None)
            case Variable(nom):
                resultat = ast.Name(id=self.chercher(nom), ctx=ast.Load())
            case Liste(elements):
                resultat = ast.List(elts=[self.expr(e) for e in elements], ctx=ast.Load())
            case Unaire(op, operande):
                resultat = ast.UnaryOp(
                    op=ast.Not() if op == "non" else ast.USub(), operand=self.expr(operande)
                )
            case Binaire(op, gauche, droite):
                g, d = self.expr(gauche), self.expr(droite)
                if op in ARITHMETIQUE:
                    resultat = ast.BinOp(left=g, op=ARITHMETIQUE[op](), right=d)
                elif op in COMPARAISONS:
                    resultat = ast.Compare(left=g, ops=[COMPARAISONS[op]()], comparators=[d])
                elif op in ("et", "ou"):
                    resultat = ast.BoolOp(op=ast.And() if op == "et" else ast.Or(), values=[g, d])
                else:
                    raise ValueError(f"operateur inconnu : {op}")
            case Appel(fonction, arguments):
                resultat = ast.Call(
                    func=self.expr(fonction), args=[self.expr(a) for a in arguments], keywords=[]
                )
            case Index(cible, indice):
                resultat = ast.Subscript(
                    value=self.expr(cible), slice=self.expr(indice), ctx=ast.Load()
                )
            case _:
                assert_never(expr)
        return positionner(resultat, expr)

    def cible(self, cible: Variable | Index) -> ast.expr:
        resultat = self.expr(cible)
        if isinstance(resultat, (ast.Name, ast.Subscript)):
            resultat.ctx = ast.Store()
        return resultat

    def bloc(self, bloc: Bloc) -> list[ast.stmt]:
        with self.portee():
            return [self.instruction(i) for i in bloc.instructions] or [ast.Pass()]

    def instruction(self, instr: Instr) -> ast.stmt:
        resultat: ast.stmt
        match instr:
            case Declaration(nom, valeur):
                valeur_py = self.expr(valeur)
                resultat = ast.Assign(
                    targets=[ast.Name(id=self.declarer(nom), ctx=ast.Store())], value=valeur_py
                )
            case Affectation(cible, valeur):
                resultat = ast.Assign(targets=[self.cible(cible)], value=self.expr(valeur))
            case Ecris(valeurs):
                resultat = ast.Expr(value=appel("_ecris", [self.expr(v) for v in valeurs]))
            case Si(branches, sinon):
                # Construire dans l'ordre source pour respecter la resolution des noms.
                racine: ast.If | None = None
                derniere: ast.If | None = None
                for branche in branches:
                    condition = self.expr(branche.condition)
                    courant = ast.If(test=condition, body=self.bloc(branche.corps), orelse=[])
                    positionner(courant, branche.condition)
                    if derniere is None:
                        racine = courant
                    else:
                        derniere.orelse = [courant]
                    derniere = courant
                if racine is None or derniere is None:
                    raise ValueError("un si doit avoir une branche")
                if sinon is not None:
                    derniere.orelse = self.bloc(sinon)
                resultat = racine
            case TantQue(condition, corps):
                test = self.expr(condition)
                resultat = ast.While(test=test, body=self.bloc(corps), orelse=[])
            case Pour(variable, debut, fin, corps):
                bornes = appel("_intervalle", [self.expr(debut), self.expr(fin)])
                with self.portee():
                    cible_py = ast.Name(id=self.declarer(variable), ctx=ast.Store())
                    resultat = ast.For(
                        target=cible_py, iter=bornes, body=self.bloc(corps), orelse=[]
                    )
            case Fonction(nom, parametres, corps):
                fonction = self.declarer(nom)
                globales = [
                    self.chercher(g)
                    for g in sorted(self.analyse.globales_modifiees.get(nom, set()))
                ]
                with self.portee():
                    args = [ast.arg(arg=self.declarer(p)) for p in parametres]
                    body = self.bloc(corps)
                    if globales:
                        body.insert(0, ast.Global(names=globales))
                    resultat = ast.FunctionDef(
                        name=fonction,
                        args=ast.arguments(
                            posonlyargs=[],
                            args=args,
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=body,
                        decorator_list=[],
                        returns=None,
                        type_params=[],
                    )
            case Rends(valeur):
                resultat = ast.Return(value=None if valeur is None else self.expr(valeur))
            case ExprInstr(expr):
                resultat = ast.Expr(value=self.expr(expr))
            case _:
                assert_never(instr)
        return positionner(resultat, instr)

    def programme(self, programme: Programme) -> ast.Module:
        # Seul le prelude fixe est parse ; tous les noeuds utilisateur sont construits.
        prelude = ast.parse(PRELUDE).body
        corps = [self.instruction(i) for i in programme.instructions]
        return ast.fix_missing_locations(ast.Module(body=prelude + corps, type_ignores=[]))


def generer_ast(programme: Programme) -> ast.Module:
    return GenerateurAst(analyser(programme)).programme(programme)


def transpiler_ast(source: str) -> str:
    return ast.unparse(generer_ast(parse(source))) + "\n"


class BackendAst:
    nom = "ast"
    extension = ".py"
    executable = True

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
        arbre = GenerateurAst(analyse).programme(programme)
        code = ast.unparse(arbre) + "\n"
        # unparse reindente et compacte : realigner les instructions du module
        # produit sur l'AST original conserve les lignes Alto dans Sortie.
        produit = ast.parse(code)
        originaux = [n for n in ast.walk(arbre) if isinstance(n, ast.stmt)]
        generes = [n for n in ast.walk(produit) if isinstance(n, ast.stmt)]
        utilisateurs = {
            id(n)
            for racine in arbre.body[len(ast.parse(PRELUDE).body) :]
            for n in ast.walk(racine)
            if isinstance(n, ast.stmt)
        }
        correspondance: dict[int, int] = {}
        for original, genere in zip(originaux, generes, strict=True):
            if id(original) in utilisateurs:
                for ligne in range(genere.lineno, (genere.end_lineno or genere.lineno) + 1):
                    correspondance[ligne] = original.lineno
        return Sortie(code, correspondance)
