"""Exportação do arranjo do mês para um arquivo .ics (agenda).

O coordenador já olha a agenda do celular o dia inteiro; o arranjo ficava só
dentro do app. Este módulo escreve um .ics com um evento por compromisso do
mês, que o Google Agenda, o Outlook e o calendário do iPhone importam.

Os eventos são de DIA INTEIRO. O horário da reunião existe no cadastro, mas o
das outras congregações não: um orador enviado apareceria na hora errada, e
uma hora errada na agenda é pior do que hora nenhuma.

O UID de cada evento é estável (tipo, data e chave do registro). Importar o
mesmo mês duas vezes atualiza os eventos em vez de duplicá-los.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

PRODUTO = "-//Gestao de Arranjo//PT-BR//"
DOMINIO_UID = "gestao-arranjo"

# O padrão (RFC 5545) manda quebrar linhas com mais de 75 octetos.
LIMITE_LINHA = 75


# A barra invertida é o escape do formato. Escrita como chr(92), e não como
# literal, para não se confundir com o escape do próprio Python.
BARRA = chr(92)


def _escapar(texto: str) -> str:
    """Escapa o que o formato reserva: barra, ponto e vírgula, vírgula e quebra."""
    texto = (texto or "").replace(BARRA, BARRA * 2)
    for reservado in (";", ","):
        texto = texto.replace(reservado, BARRA + reservado)
    return texto.replace(chr(10), BARRA + "n")


def _dobrar(linha: str) -> list[str]:
    """Quebra a linha no limite do padrão, continuando com um espaço."""
    bruto = linha.encode("utf-8")
    if len(bruto) <= LIMITE_LINHA:
        return [linha]
    partes, atual = [], ""
    for caractere in linha:
        limite = LIMITE_LINHA if not partes else LIMITE_LINHA - 1
        if len((atual + caractere).encode("utf-8")) > limite:
            partes.append(atual)
            atual = caractere
        else:
            atual += caractere
    if atual:
        partes.append(atual)
    return [partes[0]] + [" " + parte for parte in partes[1:]]


def _campo(nome: str, valor: str) -> list[str]:
    return _dobrar(f"{nome}:{_escapar(valor)}")


def gerar_ics(eventos: list[dict], agora: datetime | None = None) -> str:
    """Monta o texto do .ics a partir de eventos {data, titulo, descricao, uid}.

    ``data`` é um ``date``; o evento ocupa o dia inteiro.
    """
    carimbo = (agora or datetime.now()).strftime("%Y%m%dT%H%M%S")
    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODUTO}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Arranjo de discursos",
    ]
    for evento in eventos:
        dia: date = evento["data"]
        linhas += [
            "BEGIN:VEVENT",
            f"UID:{evento['uid']}@{DOMINIO_UID}",
            f"DTSTAMP:{carimbo}Z",
            f"DTSTART;VALUE=DATE:{dia:%Y%m%d}",
            f"DTEND;VALUE=DATE:{dia + timedelta(days=1):%Y%m%d}",
            *_campo("SUMMARY", evento["titulo"]),
        ]
        if evento.get("descricao"):
            linhas += _campo("DESCRIPTION", evento["descricao"])
        linhas.append("END:VEVENT")
    linhas.append("END:VCALENDAR")
    # O padrão pede CRLF entre as linhas.
    return "\r\n".join(linhas) + "\r\n"


def eventos_do_mes(
    ano: int,
    mes: int,
    recebidos: dict[str, dict],
    enviados: dict[str, list[dict]],
    presidentes: dict[str, dict] | None = None,
    especiais: dict[str, dict] | None = None,
) -> list[dict]:
    """Traduz o arranjo de um mês em eventos de agenda, em ordem de data.

    Recebe os dados já carregados (as mesmas estruturas das telas) para poder
    ser testado sem banco.
    """
    presidentes = presidentes or {}
    especiais = especiais or {}
    eventos: list[dict] = []

    def do_mes(data_txt: str) -> date | None:
        try:
            dia, mes_txt, ano_txt = data_txt.split("/")
            data = date(int(ano_txt), int(mes_txt), int(dia))
        except (ValueError, AttributeError):
            return None
        return data if (data.year, data.month) == (ano, mes) else None

    for data_txt, registro in recebidos.items():
        data = do_mes(data_txt)
        if data is None:
            continue
        origem = registro.get("congregacao") or ""
        titulo = f"Discurso: {registro.get('orador') or 'orador a definir'}"
        if origem:
            titulo += f" ({origem})"
        detalhes = []
        if registro.get("tema_nr"):
            tema = registro.get("tema") or ""
            detalhes.append(f"Tema {registro['tema_nr']}" + (f": {tema}" if tema else ""))
        presidente = (presidentes.get(data_txt) or {}).get("nome") or ""
        if presidente:
            detalhes.append(f"Presidente: {presidente}")
        eventos.append({
            "data": data,
            "titulo": titulo,
            "descricao": "\n".join(detalhes),
            "uid": f"recebido-{data:%Y%m%d}",
        })

    for data_txt, lista in enviados.items():
        data = do_mes(data_txt)
        if data is None:
            continue
        for indice, registro in enumerate(lista):
            destino = registro.get("congregacao") or "outra congregação"
            titulo = f"{registro.get('orador') or 'Orador'} discursa em {destino}"
            detalhes = []
            if registro.get("tema_nr"):
                tema = registro.get("tema") or ""
                detalhes.append(f"Tema {registro['tema_nr']}" + (f": {tema}" if tema else ""))
            if registro.get("status") == "pendente":
                detalhes.append("Ainda sem confirmação.")
            eventos.append({
                "data": data,
                "titulo": titulo,
                "descricao": "\n".join(detalhes),
                "uid": f"enviado-{data:%Y%m%d}-{indice}",
            })

    for data_txt, registro in especiais.items():
        data = do_mes(data_txt)
        if data is None:
            continue
        titulo = registro.get("tipo") or "Data especial"
        detalhes = [
            parte
            for parte in (
                registro.get("orador") or "",
                registro.get("tema") or "",
                f"Presidente: {registro['presidente_nome']}"
                if registro.get("presidente_nome")
                else "",
            )
            if parte
        ]
        eventos.append({
            "data": data,
            "titulo": titulo,
            "descricao": "\n".join(detalhes),
            "uid": f"especial-{data:%Y%m%d}",
        })

    return sorted(eventos, key=lambda e: (e["data"], e["uid"]))
