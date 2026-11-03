# Étape 0 : installer les outils et récupérer le projet

**Qui :** tout le monde, chacun sur sa machine. **Durée :** 30 minutes.

À la fin, la commande `uv run pytest` doit afficher `2 passed`.

## 1. Installer les outils

Il faut trois choses : **Git** (pour partager le code), **uv** (qui installe Python et les outils du projet) et un éditeur (VS Code, par exemple).

### Git

```bash
git --version
```

Si la commande affiche un numéro de version, c'est bon. Sinon, sur Mac, elle propose d'installer les outils de développement : accepte.

### uv

Sur Mac ou Linux :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Ferme puis rouvre le terminal, et vérifie :

```bash
uv --version
```

Sur Windows, dans PowerShell : `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.

> **Windows : « uv n'est pas reconnu » alors que l'installation a réussi ?** L'installateur ajoute uv au PATH, mais les terminaux déjà ouverts (et ceux de VS Code) gardent l'ancien PATH. Fermer seulement le terminal ne suffit pas : ferme **toutes** les fenêtres VS Code, vérifie dans le Gestionnaire des tâches qu'il ne reste aucun `Code.exe`, puis rouvre VS Code. Si ça ne marche toujours pas, **redémarre le PC**.
>
> Pour dépanner tout de suite, dans le terminal ouvert (valable seulement pour ce terminal) :
>
> ```powershell
> $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
> ```

> **Pourquoi uv ?** Le projet utilise Python **3.12** (pour la syntaxe `type Expr = ...` et `class Flux[T]`). uv télécharge tout seul la bonne version de Python, et installe pytest, mypy et ruff, sans toucher au Python de ton ordinateur.

## 2. Récupérer le dépôt

```bash
cd ~/Desktop
git clone https://github.com/aassaga21/Alto.git
cd Alto
```

Si tu as déjà le dossier, mets-le simplement à jour :

```bash
git pull
```

## 3. Lancer les tests une première fois

Depuis le dossier `Alto` :

```bash
uv run pytest
```

La première fois, uv crée un dossier `.venv` et installe tout : c'est un peu long. Tu dois voir à la fin :

```
2 passed
```

Si c'est le cas, **ton installation est bonne**. 🎉

### Les commandes que tu utiliseras tous les jours

```bash
uv run pytest                     # tous les tests
uv run pytest -k etape_03         # seulement les tests de l'étape 3
uv run pytest -x                  # s'arrête au premier test qui échoue
uv run pytest -k etape_03 -vv     # affiche le détail de chaque test
uv run mypy alto                  # vérifie les types (obligatoire à partir de l'étape 10)
uv run ruff check .               # vérifie le style
uv run ruff format .              # remet le code en forme automatiquement
uv run python -m alto run exemples/01_bonjour.alt    # (à partir de l'étape 9)
```

## 4. Comprendre l'arborescence

```
Alto/
├── README.md
├── ORGANISATION.md            # qui fait quoi, et comment on travaille avec Git
├── specification.md           # la définition du langage Alto (étape 1)
├── pyproject.toml             # la configuration des outils
├── guide/                     # ce guide
├── exemples/                  # les programmes Alto et leur sortie attendue
│   ├── 01_bonjour.alt
│   ├── 01_bonjour.attendu
│   └── ...
├── alto/                      # LE PAQUET PYTHON : notre compilateur
│   ├── __init__.py
│   ├── erreurs.py             # étapes 2-3   (Alexandra)
│   ├── tokens.py              # étape 2      (Alexandra)
│   ├── flux.py                # étape 3      (Alexandra)
│   ├── lexer.py               # étape 3      (Alexandra)
│   ├── noeuds.py              # étape 4      (Luca)
│   ├── parser.py              # étapes 5-6   (Fatoumata)
│   ├── symboles.py            # étape 7      (Luca)
│   ├── semantique.py          # étape 7      (Luca)
│   ├── emetteur.py            # étape 8      (Arthur)
│   ├── generateur.py          # étape 8      (Arthur)
│   ├── compilateur.py         # étapes 8-9   (Arthur puis Alexandra)
│   ├── cli.py                 # étape 9      (Alexandra)
│   ├── repl.py                # étape 9      (Alexandra)
│   ├── __main__.py            # étape 9      (Alexandra)
│   ├── backend.py             # étape 10     (Fatoumata)
│   └── formateur.py           # étape 10     (Fatoumata)
└── tests/
    ├── conftest.py
    ├── test_etape_00_installation.py
    ├── test_etape_02_tokens.py
    └── ...
```

> Dans les énoncés du cours, `monlangage` désigne le paquet Python : **chez nous, c'est `alto`**. Et `projet/` désigne la racine de notre dépôt.
>
> Ne crée jamais de fichier nommé `ast.py`, `token.py`, `types.py` ou `tokenize.py` : ces noms existent déjà dans Python, et le tien prendrait leur place.

## 5. Comment un test pytest fonctionne (rappel rapide)

Un test est une fonction dont le nom commence par `test_`, dans un fichier dont le nom commence par `test_`. Elle contient des `assert` :

```python
def test_une_addition() -> None:
    assert 1 + 1 == 2
```

Pour vérifier qu'une erreur est bien levée :

```python
import pytest

def test_division_par_zero() -> None:
    with pytest.raises(ZeroDivisionError):
        1 / 0
```

Pour tester plusieurs cas avec la même fonction (très utile pour un lexer ou un parser) :

```python
@pytest.mark.parametrize(("source", "attendu"), [
    ("1", 1),
    ("42", 42),
])
def test_conversion(source: str, attendu: int) -> None:
    assert int(source) == attendu
```

Pour capturer ce qu'un programme affiche avec `print` :

```python
def test_affichage(capsys: pytest.CaptureFixture[str]) -> None:
    print("bonjour")
    assert capsys.readouterr().out == "bonjour\n"
```

## 6. Ta journée type

```bash
git switch main && git pull                 # 1. récupérer le travail des autres
git switch -c prenom/ma-tache               # 2. une branche pour ta tâche (ou git switch ta-branche)
# 3. écrire un test, le voir échouer, écrire le code, le voir passer… recommencer
uv run pytest                               # 4. tout est vert ?
uv run ruff format . && uv run ruff check . # 5. le style est bon ?
git add alto/lexer.py tests/test_etape_03_lexer.py
git commit -m "Lexer : nombres et identifiants"
git push -u origin prenom/ma-tache          # 6. puis ouvrir une Pull Request sur GitHub
```

Le détail du travail en équipe sur GitHub est dans [`../ORGANISATION.md`](../ORGANISATION.md), section 6.

## Ça ne marche pas ?

| Problème | Solution |
|---|---|
| `uv: command not found` | ferme et rouvre le terminal ; sinon relance l'installation de uv |
| Windows : `uv : Le terme «uv» n'est pas reconnu…` | ferme complètement VS Code (aucun `Code.exe` dans le Gestionnaire des tâches) ou redémarre le PC : voir l'encadré de la section 1 |
| `ModuleNotFoundError: No module named 'alto'` | lance les commandes **depuis le dossier `Alto`**, et vérifie que `tests/conftest.py` existe |
| `SyntaxError` sur `type Expr = ...` ou `class Flux[T]` | tu n'utilises pas Python 3.12 : passe par `uv run` |
| `git push` refusé | fais `git pull` d'abord ; vérifie que tu es bien collaborateur du dépôt sur GitHub |
