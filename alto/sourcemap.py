"""Les source maps (extension 13) : ligne du code produit -> ligne du source Alto."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, TypedDict

from alto.erreurs import ErreurSourceMap

VERSION: Literal[1] = 1


class SourceMapJson(TypedDict):
    """La forme du fichier `.map.json`."""

    version: Literal[1]
    source: str
    lignes: dict[str, int]  # les clés JSON sont toujours des chaînes


@dataclass(frozen=True, slots=True)
class SourceMap:
    #: ligne du code produit (à partir de 1) -> ligne du source Alto
    lignes: dict[int, int] = field(default_factory=dict)
    #: le fichier Alto d'origine
    source: str = "<source>"

    def ligne_source(self, ligne: int) -> int | None:
        """La ligne Alto d'où vient `ligne`, ou None si elle n'en vient pas (le prélude)."""
        return self.lignes.get(ligne)

    def decalee(self, n: int) -> SourceMap:
        """La même correspondance, si on ajoute `n` lignes avant le code (le prélude)."""
        return replace(self, lignes={ligne + n: alto for ligne, alto in self.lignes.items()})

    # --- JSON ---------------------------------------------------------------------

    def vers_json(self) -> SourceMapJson:
        return {
            "version": VERSION,
            "source": self.source,
            "lignes": {str(ligne): self.lignes[ligne] for ligne in sorted(self.lignes)},
        }

    @classmethod
    def depuis_json(cls, donnees: object) -> SourceMap:
        """Relit un objet JSON ; refuse tout ce qui n'a pas la forme attendue."""
        if not isinstance(donnees, dict):
            raise ErreurSourceMap("une source map doit être un objet JSON")
        version = donnees.get("version")
        if version != VERSION:
            raise ErreurSourceMap(
                f"version {version!r} inconnue (seule la version {VERSION} est prise en charge)"
            )
        source = donnees.get("source")
        lignes = donnees.get("lignes")
        if not isinstance(source, str):
            raise ErreurSourceMap("le champ 'source' doit être un texte")
        if not isinstance(lignes, dict):
            raise ErreurSourceMap("le champ 'lignes' doit être un objet")
        resultat: dict[int, int] = {}
        for cle, valeur in lignes.items():
            if not (isinstance(cle, str) and cle.isdigit()) or type(valeur) is not int:
                raise ErreurSourceMap(f"ligne invalide : {cle!r} -> {valeur!r}")
            resultat[int(cle)] = valeur
        return cls(resultat, source)

    def ecrire(self, chemin: Path) -> None:
        chemin.write_text(
            json.dumps(self.vers_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    @classmethod
    def lire(cls, chemin: Path) -> SourceMap:
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ErreurSourceMap(f"JSON invalide : {exc.msg}") from exc
        return cls.depuis_json(donnees)


def chemin_de_la_map(sortie: Path) -> Path:
    """`bonjour.py` -> `bonjour.py.map.json`, à côté du fichier produit."""
    return sortie.with_name(sortie.name + ".map.json")
