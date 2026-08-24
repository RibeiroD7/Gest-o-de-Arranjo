"""Embute as credenciais do Google no build, a partir dos secrets do repositório.

Roda nos três jobs antes de compilar. Sem os secrets, o arquivo continua vazio
e o app pede as credenciais do próprio usuário em Ajustes.

O valor vai para o código como literal Python gerado por ``json.dumps``: se um
secret tiver aspas, barra ou quebra de linha, ele é escapado em vez de quebrar
o arquivo. Uma vez isso aconteceu de verdade — um Client ID recadastrado com
aspas em volta gerou ``CLIENT_ID = ""123-abc..."" `` e o build morreu quatro
passos adiante, num erro que não citava nem o arquivo nem o secret.

Uso: python .github/scripts/injetar_credenciais.py
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys

ARQUIVO = pathlib.Path("src/credenciais_app.py")

# (constante no arquivo, variável de ambiente vinda do secret)
CHAVES = (
    ("CLIENT_ID_DESKTOP", "ID_DESKTOP"),
    ("CLIENT_SECRET_DESKTOP", "SECRET_DESKTOP"),
    ("CLIENT_ID_DISPOSITIVO", "ID_DISPOSITIVO"),
    ("CLIENT_SECRET_DISPOSITIVO", "SECRET_DISPOSITIVO"),
)

# Como o Google emite um Client ID de aplicativo. Serve para pegar cedo o
# secret colado com aspas, com espaço no meio ou pela metade.
FORMATO_CLIENT_ID = re.compile(r"^[0-9]+-[A-Za-z0-9_]+\.apps\.googleusercontent\.com$")


def limpar(valor: str) -> str:
    """Tira espaços e um par de aspas em volta, se quem cadastrou colou junto."""
    valor = (valor or "").strip()
    for aspas in ('"', "'"):
        if len(valor) >= 2 and valor.startswith(aspas) and valor.endswith(aspas):
            valor = valor[1:-1].strip()
    return valor


def main() -> int:
    texto = ARQUIVO.read_text(encoding="utf-8")
    embutidas = []
    for chave, variavel in CHAVES:
        valor = limpar(os.environ.get(variavel, ""))
        if not valor:
            continue
        if "ID_" in variavel and not FORMATO_CLIENT_ID.match(valor):
            # Nunca imprime o valor: o log da Action é público.
            print(
                f"ERRO: o secret de {variavel} não tem cara de Client ID "
                "(esperado algo como 123456-abc.apps.googleusercontent.com). "
                "Recadastre sem aspas e sem espaços.",
                file=sys.stderr,
            )
            return 1
        texto = texto.replace(f'{chave} = ""', f"{chave} = {json.dumps(valor)}")
        embutidas.append(chave)

    ARQUIVO.write_text(texto, encoding="utf-8")

    # Falha aqui, com o arquivo na mão, em vez de num passo adiante.
    try:
        compile(texto, str(ARQUIVO), "exec")
    except SyntaxError as erro:
        print(
            f"ERRO: {ARQUIVO} ficou inválido na linha {erro.lineno} depois da "
            "injeção. Confira o formato dos secrets.",
            file=sys.stderr,
        )
        return 1

    print("Credenciais embutidas:", embutidas or "nenhuma (build sem secrets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
