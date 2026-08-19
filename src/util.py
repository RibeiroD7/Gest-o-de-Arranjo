"""Funções puras de data e texto — sem dependência de Flet nem do banco.

Foram separadas de ``main.py`` para permitir testes automatizados (ver
``tests/test_util.py``). Os nomes mantêm o prefixo ``_`` usado historicamente
no ``main.py`` para que os pontos de chamada continuem inalterados após a
extração.
"""

from __future__ import annotations

import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

# Dia da semana (texto) -> weekday do Python (0=segunda … 6=domingo).
MAP_DIA_SEMANA = {
    "domingo": 6,
    "segunda-feira": 0,
    "segunda": 0,
    "terça-feira": 1,
    "terca-feira": 1,
    "terça": 1,
    "terca": 1,
    "quarta-feira": 2,
    "quarta": 2,
    "quinta-feira": 3,
    "quinta": 3,
    "sexta-feira": 4,
    "sexta": 4,
    "sábado": 5,
    "sabado": 5,
}


def _formatar_data_exibicao(data: str | None) -> str:
    """Exibe data DD/MM/AAAA ou DD/MM."""
    if not data:
        return "—"
    texto = data.strip()
    if len(texto) >= 10:
        return f"{texto[0:2]}/{texto[3:5]}/{texto[6:10]}"
    return texto


def _dia_semana_para_weekday(dia_semana: str) -> int | None:
    """Converte texto do dia da semana para weekday (0=segunda … 6=domingo)."""
    texto = (dia_semana or "").strip().lower()
    for chave, valor in MAP_DIA_SEMANA.items():
        if chave in texto:
            return valor
    return None


def _normalizar_texto_busca(texto: str) -> str:
    """Normaliza para comparação: minúsculas, sem acento e sem espaços extras."""
    base = unicodedata.normalize("NFKD", (texto or "").casefold().strip())
    return " ".join("".join(c for c in base if not unicodedata.combining(c)).split())


def _normalizar_data_arranjo(valor: str) -> str | None:
    """Normaliza data para DD/MM/AAAA."""
    texto = (valor or "").strip()
    if not texto:
        return None
    partes = texto.replace(".", "/").split("/")
    if len(partes) == 2:
        dia, mes = partes
        return f"{dia.zfill(2)}/{mes.zfill(2)}/2026"
    if len(partes) == 3:
        dia, mes, ano = partes
        return f"{dia.zfill(2)}/{mes.zfill(2)}/{ano}"
    return None


def _parse_data_arranjo(valor: str | None) -> date | None:
    """Converte DD/MM/AAAA em date."""
    norm = _normalizar_data_arranjo(valor or "")
    if not norm:
        return None
    try:
        return datetime.strptime(norm, "%d/%m/%Y").date()
    except ValueError:
        return None


def _formatar_data_arranjo(data_ref: date) -> str:
    return data_ref.strftime("%d/%m/%Y")


def _weekday_mais_usado(registros: list[dict], tipo: str) -> int | None:
    """Detecta o dia da semana mais usado nas designações do mês."""
    contagem: dict[int, int] = {}
    for registro in registros:
        if registro.get("tipo") != tipo:
            continue
        data_ref = _parse_data_arranjo(registro.get("data"))
        if not data_ref:
            continue
        contagem[data_ref.weekday()] = contagem.get(data_ref.weekday(), 0) + 1
    if not contagem:
        return None
    return max(contagem, key=contagem.get)


def _datas_por_weekday_no_mes(ano: int, mes: int, weekday: int) -> list[date]:
    ultimo_dia = monthrange(ano, mes)[1]
    datas: list[date] = []
    for dia in range(1, ultimo_dia + 1):
        data_ref = date(ano, mes, dia)
        if data_ref.weekday() == weekday:
            datas.append(data_ref)
    return datas


def _rotulo_weekday(weekday: int) -> str:
    nomes = [
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Sábado",
        "Domingo",
    ]
    return nomes[weekday]


def _versao_como_tupla(versao: str) -> tuple[int, ...]:
    """Converte '1.0.18' em (1, 0, 18) para comparação numérica."""
    partes = []
    for parte in (versao or "").split("."):
        digitos = "".join(c for c in parte if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


def ha_versao_mais_nova(remota: str, atual: str) -> bool:
    """True se ``remota`` (ex.: '1.0.19') for mais nova que ``atual`` ('1.0.18')."""
    if not remota:
        return False
    return _versao_como_tupla(remota) > _versao_como_tupla(atual)


# São Paulo está em UTC-3 o ano inteiro desde 2019 (o horário de verão
# brasileiro foi extinto). Um offset fixo evita depender do banco de fusos,
# que nem sempre existe no empacotamento para celular.
FUSO_SAO_PAULO = timezone(timedelta(hours=-3))


def formatar_data_hora_sao_paulo(iso_utc: str | None) -> str:
    """Converte data/hora ISO em UTC (ex.: do Google Drive) para o horário de
    São Paulo no formato brasileiro: "18/08/2026 09:28"."""
    texto = (iso_utc or "").strip()
    if not texto:
        return "—"
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return texto
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M")


def nome_oradores(registro) -> str:
    """Nome do orador — ou dos dois, quando o discurso é um simpósio.

    O simpósio é um compromisso só, dividido entre dois oradores da
    congregação, então o par aparece junto em toda parte: na lista do mês, no
    PNG do quadro e no relatório em PDF.
    """
    primeiro = (registro.get("orador_nome") or "").strip()
    segundo = (registro.get("orador_2_nome") or "").strip()
    if primeiro and segundo:
        return f"{primeiro} e {segundo}"
    return primeiro or segundo
