#!/usr/bin/env bash
#
# Publica uma nova versão: cria e envia a tag vX.Y.Z, que é o gatilho do
# workflow "Gerar instaladores" no GitHub Actions (Windows .exe, Linux e
# Android .apk) e da publicação da Release.
#
# O commit sozinho NÃO gera instaladores — é a tag que dispara a compilação.
#
# Uso:
#   ./release.sh            Usa a versão que está em mobile/pyproject.toml
#   ./release.sh 1.0.8      Grava 1.0.8 no pyproject.toml e commita antes
#
# Requer: git configurado com acesso ao repositório (o mesmo usado no push).

set -euo pipefail
cd "$(dirname "$0")"

PYPROJECT="mobile/pyproject.toml"

# 1) Descobre (ou define) a versão -----------------------------------------
if [[ $# -ge 1 ]]; then
    VERSAO="${1#v}"                       # aceita "1.0.8" ou "v1.0.8"
else
    VERSAO="$(grep -E '^version = ' "$PYPROJECT" | head -1 | sed -E 's/version = "(.*)"/\1/')"
fi
TAG="v$VERSAO"

echo ">> Versão: $VERSAO   (tag $TAG)"

# 2) Mantém a versão sincronizada: pyproject.toml e o VERSAO_APP mostrado
#    dentro de cada app (PC e mobile).
sed -i -E "s/^version = \".*\"/version = \"$VERSAO\"/" "$PYPROJECT"
sed -i -E "s/^VERSAO_APP = \".*\"/VERSAO_APP = \"$VERSAO\"/" main.py mobile/src/main.py

# 3) Não sobrescreve uma tag/versão já publicada ---------------------------
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "ERRO: a tag $TAG já existe. Suba o número da versão antes de publicar." >&2
    exit 1
fi

# 4) Se a versão mudou em algum arquivo, commita ---------------------------
if ! git diff --quiet -- "$PYPROJECT" main.py mobile/src/main.py; then
    git add "$PYPROJECT" main.py mobile/src/main.py
    git commit -m "Versão $VERSAO"
fi

# 5) Exige a árvore limpa: nada pendente vai para a release ----------------
if ! git diff-index --quiet HEAD --; then
    echo "ERRO: há alterações não commitadas. Commite tudo antes de publicar." >&2
    git status --short
    exit 1
fi

# 6) Envia o commit e a tag ------------------------------------------------
echo ">> Enviando commits..."
git push origin HEAD

echo ">> Criando e enviando a tag $TAG..."
git tag -a "$TAG" -m "$TAG"
git push origin "$TAG"

echo ""
echo "Pronto! A tag $TAG foi enviada."
echo "Acompanhe a compilação em: Actions -> Gerar instaladores"
echo "Os instaladores ficam na Release $TAG quando o workflow terminar."
