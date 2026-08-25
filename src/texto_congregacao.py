"""Lê os dados de uma congregação a partir de um texto colado.

Serve para não redigitar o que já está escrito em algum lugar: a mensagem do
responsável no WhatsApp, um e-mail do coordenador anterior, a ficha que você
tem na tela. Você copia, cola no campo e o aplicativo separa nome, dia,
horário, endereço e telefone.

Quem copia é a pessoa. Este módulo não busca nada em lugar nenhum: recebe um
texto e devolve campos.

A leitura é tolerante de propósito, porque texto colado vem de qualquer jeito:
tudo numa linha só, em duas colunas embaralhadas, com rótulos ou sem. O que
ele não conseguir entender volta vazio, para a pessoa completar na mão.
"""

from __future__ import annotations

import re
import unicodedata

DIAS_SEMANA = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
# A reunião do fim de semana é sempre num destes dois. É o que separa o horário
# que interessa (o do discurso público) do da reunião do meio de semana, sem
# depender de o texto trazer rótulo ou de qual coluna veio primeiro.
DIAS_FIM_DE_SEMANA = ("sábado", "domingo")

_DIA_E_HORA = re.compile(
    r"(segunda|ter[çc]a|quarta|quinta|sexta)(?:-feira)?|(s[áa]bado|domingo)",
    re.IGNORECASE,
)
_HORA = re.compile(r"\b([0-2]?\d)[:h]([0-5]\d)\b")
_TELEFONE = re.compile(r"\(?\d{2}\)?[\s-]?\d{4,5}[\s-]?\d{4}")
_CEP = re.compile(r"\b\d{5}-?\d{3}\b")
# "Vila Palmira - São Paulo SP" → o sufixo de cidade e estado sai do nome.
_CIDADE_UF = re.compile(r"\s*[-–]\s*[^-–]+\s+[A-Z]{2}\s*$")
_DISTANCIA = re.compile(r"^\s*[\d.,]+\s*(km|mi)\b", re.IGNORECASE)

ROTULOS = (
    "congregação", "congregacao", "reunião do meio de semana",
    "reuniao do meio de semana", "reunião do fim de semana",
    "reuniao do fim de semana", "endereço", "endereco", "telefone",
    "coordenadas gps", "como chegar", "compartilhar", "imprimir",
    "português", "portugues", "pesquisar por localização",
    "procurar por", "nome da congregação", "idioma", "mapa",
)


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _e_rotulo(linha: str) -> bool:
    limpa = _sem_acento(linha).strip().rstrip(":")
    return any(limpa == _sem_acento(r) for r in ROTULOS)


def _dia_por_extenso(trecho: str) -> str:
    """Devolve o dia da semana no formato que o cadastro usa ("Sábado")."""
    sem_acento = _sem_acento(trecho)
    for dia in DIAS_SEMANA:
        if _sem_acento(dia).startswith(sem_acento[: len(sem_acento)]) and sem_acento:
            if _sem_acento(dia).startswith(sem_acento):
                return dia.capitalize()
    return ""


def _reunioes(texto: str) -> list[tuple[str, str]]:
    """Pares (dia, horário) na ordem em que aparecem no texto."""
    encontrados = []
    for achado in _DIA_E_HORA.finditer(texto):
        dia = _dia_por_extenso(achado.group(0))
        if not dia:
            continue
        # O horário costuma vir logo depois do dia, separado por vírgula ou
        # espaço; procura na sobra da linha, sem atravessar para a próxima.
        resto = texto[achado.end(): achado.end() + 40].split("\n")[0]
        hora = _HORA.search(resto)
        if hora:
            encontrados.append((dia, f"{int(hora.group(1)):02d}:{hora.group(2)}"))
    return encontrados


def _nome(linhas: list[str]) -> str:
    """O nome da congregação: a linha logo depois do rótulo, ou a primeira útil."""
    for i, linha in enumerate(linhas):
        if _sem_acento(linha).strip() in ("congregacao", "congregacao:"):
            for seguinte in linhas[i + 1:]:
                if seguinte and not _e_rotulo(seguinte) and not _DISTANCIA.match(seguinte):
                    return _CIDADE_UF.sub("", seguinte).strip()
            break
    for linha in linhas:
        if (
            linha
            and not _e_rotulo(linha)
            and not _DISTANCIA.match(linha)
            and not _HORA.search(linha)
            and not _TELEFONE.search(linha)
        ):
            return _CIDADE_UF.sub("", linha).strip()
    return ""


def _endereco(linhas: list[str]) -> str:
    """As linhas entre o rótulo Endereço e o próximo rótulo, numa linha só."""
    partes: list[str] = []
    coletando = False
    for linha in linhas:
        if _sem_acento(linha).strip().rstrip(":") in ("endereco",):
            coletando = True
            continue
        if not coletando:
            continue
        if _e_rotulo(linha) or not linha:
            break
        partes.append(linha)
    if not partes:
        return ""
    # O CEP fecha o endereço; o que vier depois já é outra coisa.
    final = []
    for parte in partes:
        final.append(parte)
        if _CEP.search(parte):
            break
    return ", ".join(final)


def ler_congregacao_colada(texto: str) -> dict[str, str]:
    """Separa nome, dia, horário, endereço e telefone de um texto colado.

    Campos que não aparecerem no texto voltam vazios. O dia e o horário são os
    da reunião do FIM DE SEMANA, que é a do discurso público — quando o texto
    traz as duas reuniões, a do meio de semana é descartada.
    """
    vazio = {"nome": "", "dia_semana": "", "horario": "", "endereco": "", "telefone": ""}
    if not (texto or "").strip():
        return vazio

    linhas = [linha.strip() for linha in texto.splitlines()]
    reunioes = _reunioes(texto)
    fim_de_semana = next(
        ((dia, hora) for dia, hora in reunioes if _sem_acento(dia) in
         [_sem_acento(d) for d in DIAS_FIM_DE_SEMANA]),
        ("", ""),
    )

    telefone = ""
    for i, linha in enumerate(linhas):
        if _sem_acento(linha).strip().rstrip(":") == "telefone":
            for seguinte in linhas[i + 1: i + 3]:
                achado = _TELEFONE.search(seguinte)
                if achado and not _e_rotulo(seguinte):
                    telefone = achado.group(0).strip()
                    break
            break
    if not telefone:
        for linha in linhas:
            if _sem_acento(linha).startswith("coordenadas"):
                continue
            achado = _TELEFONE.search(linha)
            if achado and not _CEP.search(linha):
                telefone = achado.group(0).strip()
                break

    return {
        "nome": _nome(linhas),
        "dia_semana": fim_de_semana[0],
        "horario": fim_de_semana[1],
        "endereco": _endereco(linhas),
        "telefone": telefone,
    }
