"""Tira a extensão do seletor nativo de contatos do pyproject.toml.

Usado pelos jobs de Windows e Linux antes de compilar. A extensão
``flet-contatos`` embrulha o pacote Flutter ``flutter_contacts``, que só tem
implementação para Android/iOS — deixá-la no build de desktop pediria um
pacote que não existe para aquela plataforma.

No computador o app importa a extensão de forma protegida (try/except) e usa o
arquivo .vcf, então nada quebra por ela não estar lá.

Uso: python .github/scripts/sem_extensao_contatos.py
"""

from __future__ import annotations

import pathlib
import re
import sys

SECOES = ("[tool.flet.dev_packages]", "[tool.uv.sources]")


def limpar(texto: str) -> str:
    """Remove a dependência e as seções que apontam para a extensão local."""
    # A linha da dependência, com o comentário que a explica logo acima.
    texto = re.sub(r'\n *"flet-contatos",', "", texto)

    # As seções inteiras: da linha do cabeçalho até a próxima seção (ou o fim).
    for seCao in SECOES:
        padrao = re.escape(seCao) + r"\n(?:(?!\n\[).)*"
        texto = re.sub(padrao, "", texto, flags=re.DOTALL)

    # Comentário órfão que introduzia as seções removidas.
    texto = texto.replace(
        "# Extensão local com o seletor nativo (lado Python + lado Flutter). Só entra no\n"
        "# build do Android; Windows e Linux removem esta seção no CI.\n",
        "",
    )
    return re.sub(r"\n{3,}", "\n\n", texto)


def main() -> int:
    caminho = pathlib.Path("pyproject.toml")
    original = caminho.read_text(encoding="utf-8")
    novo = limpar(original)
    caminho.write_text(novo, encoding="utf-8")

    restou = [alvo for alvo in ("flet-contatos", *SECOES) if alvo in novo]
    if restou:
        print(f"ERRO: ainda há referência à extensão: {restou}", file=sys.stderr)
        return 1
    print("Extensão de contatos removida do pyproject.toml (build de desktop).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
