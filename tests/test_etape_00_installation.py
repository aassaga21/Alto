"""Vérifie que l'installation fonctionne. Si ce test passe, tu peux commencer à coder."""

from pathlib import Path

import alto

EXEMPLES = Path(__file__).parent.parent / "exemples"


def test_le_paquet_alto_est_importable() -> None:
    assert alto.__name__ == "alto"


def test_chaque_exemple_a_sa_sortie_attendue() -> None:
    exemples = sorted(EXEMPLES.glob("*.alt"))
    assert len(exemples) >= 5
    for exemple in exemples:
        assert exemple.with_suffix(".attendu").exists(), f"il manque {exemple.stem}.attendu"
