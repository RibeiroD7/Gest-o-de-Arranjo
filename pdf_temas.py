"""Leitura dos formulários oficiais de temas em PDF.

Suporta os dois formulários usados pelas congregações:
- S-99  — "Títulos dos discursos públicos": lista numerada dos títulos.
- S-99a — "Lista por assunto": os mesmos títulos agrupados por categoria.

O tipo de formulário é detectado automaticamente pelo conteúdo do PDF.
"""

import re
import unicodedata

RE_ENTRADA = re.compile(r"^(\d{1,3})\.\s+(.*)$")
# Na extração do PDF, entradas de colunas vizinhas podem vir grudadas na mesma
# linha ("...casamento?27. Como construir..."); separa antes de "NN. " quando
# colado a um caractere que não é espaço nem dígito.
RE_QUEBRA_COLUNA = re.compile(r"(?<=[^\s\d])(?=\d{1,3}\.\s)")

# Nomes de exibição das categorias do S-99a (o cabeçalho vem em maiúsculas).
CATEGORIAS_EXIBICAO = {
    "biblia/deus": "Bíblia/Deus",
    "evangelizacao/ministerio": "Evangelização/ministério",
    "familia/jovens": "Família/jovens",
    "fe/espiritualidade": "Fé/espiritualidade",
    "mundo, nao fazer parte do": "Mundo, não fazer parte do",
    "provacoes/problemas": "Provações/problemas",
    "qualidades/padroes cristaos": "Qualidades/padrões cristãos",
    "qualidades e padroes cristaos": "Qualidades/padrões cristãos",
    "reino/paraiso": "Reino/paraíso",
    "religiao/adoracao": "Religião/adoração",
    "ultimos dias/julgamento de deus": "Últimos dias/julgamento de Deus",
}


def _normalizar(texto: str) -> str:
    """Minúsculas sem acentos, para comparações tolerantes."""
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acentos).strip().lower()


def _extrair_texto(caminho: str) -> str:
    from pypdf import PdfReader

    try:
        leitor = PdfReader(caminho)
        return "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    except Exception as exc:
        raise ValueError("Não foi possível ler o arquivo como PDF.") from exc


def _detectar_formulario(texto: str) -> str:
    inicio = _normalizar(texto[:600])
    if "lista por assunto" in inicio:
        return "S-99a"
    if "titulos dos discursos publicos" in inicio:
        return "S-99"
    raise ValueError(
        "O PDF selecionado não parece ser um formulário S-99 ou S-99a "
        "(Títulos dos discursos públicos)."
    )


def _e_cabecalho_categoria(linha: str) -> bool:
    """Linhas de categoria do S-99a vêm em maiúsculas, sem numeração."""
    return (
        linha == linha.upper()
        and linha != linha.lower()  # tem ao menos uma letra
        and not linha.startswith("S-99")
        and RE_ENTRADA.match(linha) is None
    )


def _formatar_categoria(cabecalho: str) -> str:
    nome = CATEGORIAS_EXIBICAO.get(_normalizar(cabecalho))
    if nome:
        return nome
    minusculas = cabecalho.strip().lower()
    return minusculas[:1].upper() + minusculas[1:]


def _linhas_uteis(texto: str):
    """Linhas limpas do PDF, ignorando cabeçalhos e rodapés de página."""
    for bruta in texto.splitlines():
        linha = re.sub(r"\s+", " ", bruta.replace("\xa0", " ")).strip()
        if not linha:
            continue
        if linha.startswith("S-99") or linha.startswith("Ano:"):
            continue
        for pedaco in RE_QUEBRA_COLUNA.split(linha):
            pedaco = pedaco.strip()
            if pedaco:
                yield pedaco


def ler_formulario_temas(caminho: str) -> tuple[str, list[dict]]:
    """Lê um PDF S-99 ou S-99a.

    Retorna (formulario, temas), em que cada tema é
    {"nr": int, "titulo": str, "categoria": str | None}.
    """
    texto = _extrair_texto(caminho)
    formulario = _detectar_formulario(texto)

    temas: dict[int, dict] = {}
    categoria_atual: str | None = None
    entrada_atual: dict | None = None

    def finalizar_entrada():
        nonlocal entrada_atual
        if entrada_atual is None:
            return
        titulo = re.sub(r"\s+", " ", entrada_atual["titulo"]).strip()
        nr = entrada_atual["nr"]
        entrada_atual = None
        if not titulo:
            return
        existente = temas.get(nr)
        if existente is None:
            temas[nr] = {"nr": nr, "titulo": titulo, "categoria": categoria_atual}
        elif categoria_atual and not existente["categoria"]:
            existente["categoria"] = categoria_atual

    for linha in _linhas_uteis(texto):
        if formulario == "S-99a" and _e_cabecalho_categoria(linha):
            finalizar_entrada()
            categoria_atual = _formatar_categoria(linha)
            continue

        match = RE_ENTRADA.match(linha)
        if match:
            finalizar_entrada()
            if formulario == "S-99a" and categoria_atual is None:
                continue  # ainda no texto introdutório
            entrada_atual = {"nr": int(match.group(1)), "titulo": match.group(2)}
            continue

        if entrada_atual is not None:
            # Continuação de título quebrado em duas linhas
            if entrada_atual["titulo"].endswith("-"):
                entrada_atual["titulo"] += linha
            else:
                entrada_atual["titulo"] += " " + linha

    finalizar_entrada()

    if len(temas) < 10:
        raise ValueError(
            "Não foi possível reconhecer a lista de temas neste PDF. "
            "Verifique se é o formulário oficial S-99 ou S-99a."
        )

    lista = sorted(temas.values(), key=lambda t: t["nr"])
    return formulario, lista
