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


# Restaurar um backup troca tudo o que está no aparelho. Quando o arquivo é
# mais VELHO do que os dados daqui, o certo é avisar: é o caso de quem mexeu na
# programação no computador e depois abre o celular, onde o backup na nuvem
# ainda é o de ontem.
#
# A folga existe porque o banco é gravado por coisas que não são edição do
# usuário (a escala de fonte, o backup do dia), e um punhado de minutos de
# diferença não significa trabalho perdido.
FOLGA_BACKUP_MINUTOS = 10


def _momento(iso: str | None) -> datetime | None:
    """Data/hora ISO como instante comparável. Sem fuso, assume o do aparelho."""
    texto = (iso or "").strip()
    if not texto:
        return None
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento.astimezone() if momento.tzinfo is None else momento


def formatar_data_hora_local(iso: str | None) -> str:
    """Data/hora de um carimbo gravado NESTE aparelho, no formato brasileiro.

    Difere de ``formatar_data_hora_sao_paulo`` no que fazer quando o texto vem
    sem fuso: aqui significa a hora do próprio aparelho, que é o que o
    ``datetime.now()`` grava; lá significa UTC, que é o que o Drive devolve.
    Trocar um pelo outro tira três horas do relógio, e foi o que aconteceu com
    o "último envio" da tela de Ajustes.

    Sem fuso o carimbo JÁ ESTÁ no relógio do aparelho, então sai como está —
    converter para São Paulo mudaria a hora de quem não vive nesse fuso
    (Manaus é -04, Rio Branco -05). Com fuso explícito, aí sim converte: o
    carimbo veio de outro relógio e precisa virar horário daqui.
    """
    texto = (iso or "").strip()
    if not texto:
        return "—"
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return texto
    if momento.tzinfo is not None:
        momento = momento.astimezone(FUSO_SAO_PAULO)
    return momento.strftime("%d/%m/%Y %H:%M")


def aviso_backup_antigo(
    gerado_em: str | None, alterado_em: str | None, aparelho: str = ""
) -> str:
    """Frase de alerta quando o backup é anterior às alterações locais.

    Devolve string vazia quando não há o que avisar: backup mais novo, dentro
    da folga, ou datas que não dá para ler.
    """
    backup, local = _momento(gerado_em), _momento(alterado_em)
    if backup is None or local is None:
        return ""
    if local - backup <= timedelta(minutes=FOLGA_BACKUP_MINUTOS):
        return ""
    origem = f", gerado em {aparelho}" if aparelho else ""
    return (
        f"Atenção: este backup é de {formatar_data_hora_local(gerado_em)}"
        f"{origem}, e os dados deste aparelho foram alterados depois, em "
        f"{formatar_data_hora_local(alterado_em)}. Restaurar descarta o que "
        "foi feito aqui desde então."
    )


# A partir de quantos dias um convite sem resposta merece ser cobrado. Cinco
# dias cobrem o fim de semana inteiro: quem foi convidado numa quarta e não
# respondeu até segunda provavelmente esqueceu.
DIAS_SEM_RESPOSTA = 5


def espera_de_resposta(convidado_em: str | None, hoje: date | None = None) -> tuple[str, str]:
    """Há quanto tempo este convite foi mandado sem resposta.

    Devolve (texto, nível), com nível "atencao" quando já passou do prazo de
    cobrança. Sem convite registrado, devolve dois vazios: o convite pode ter
    saído por fora do app, e inventar espera seria mentira.
    """
    momento = _momento(convidado_em)
    if momento is None:
        return "", ""
    hoje = hoje or date.today()
    dias = (hoje - momento.date()).days
    if dias <= 0:
        return "convite enviado hoje", ""
    if dias == 1:
        return "1 dia sem resposta", ""
    return (
        f"{dias} dias sem resposta",
        "atencao" if dias >= DIAS_SEM_RESPOSTA else "",
    )


# Depois de quantos dias sem enviar backup para a nuvem a tela chama atenção.
# Duas semanas é tempo de o envio automático ter falhado várias vezes sem
# ninguém notar, e ainda sobra margem para quem viajou.
DIAS_BACKUP_ANTIGO = 14


def descrever_ultimo_envio(iso: str | None, agora: datetime | None = None) -> tuple[str, str]:
    """Frase do último envio à nuvem e se ela deve chamar atenção.

    Devolve (texto, nível), com nível "atencao" quando já faz tempo demais.
    """
    momento = _momento(iso)
    if momento is None:
        return "Nenhum backup enviado ainda.", "atencao"
    agora = agora or datetime.now().astimezone()
    if agora.tzinfo is None:
        agora = agora.astimezone()
    dias = (agora - momento).days
    quando = formatar_data_hora_local(iso)
    if dias <= 0:
        texto = f"Último envio: hoje, {quando.split(' ')[-1]}."
    elif dias == 1:
        texto = f"Último envio: ontem, {quando.split(' ')[-1]}."
    else:
        texto = f"Último envio: há {dias} dias ({quando})."
    return texto, "atencao" if dias >= DIAS_BACKUP_ANTIGO else ""


def mes_anterior(aaaa_mm: str) -> str:
    """O mês anterior a "AAAA-MM"; vazio se o texto não for um mês."""
    texto = (aaaa_mm or "").strip()
    if len(texto) != 7 or texto[4] != "-":
        return ""
    try:
        ano, mes = int(texto[:4]), int(texto[5:])
    except ValueError:
        return ""
    if mes == 1:
        return f"{ano - 1:04d}-12"
    return f"{ano:04d}-{mes - 1:02d}"


def mes_seguinte(aaaa_mm: str) -> str:
    """O mês seguinte a "AAAA-MM"; vazio se o texto não for um mês."""
    texto = (aaaa_mm or "").strip()
    if len(texto) != 7 or texto[4] != "-":
        return ""
    try:
        ano, mes = int(texto[:4]), int(texto[5:])
    except ValueError:
        return ""
    if mes == 12:
        return f"{ano + 1:04d}-01"
    return f"{ano:04d}-{mes + 1:02d}"


def periodos_de_reuniao(entradas: list[dict]) -> list[dict]:
    """Transforma a linha do tempo em períodos com começo e fim.

    O banco guarda "a partir de tal mês, a reunião é em tal dia" — é o que a
    Programação precisa para montar cada mês no dia que valia nele. Só que
    quem lê a tela pensa em faixas: "de 2020 a 2023 era domingo". O fim de um
    período é o mês anterior ao começo do próximo; o último fica em aberto.
    """
    em_ordem = sorted(entradas, key=lambda e: e.get("inicio") or "")
    periodos = []
    for indice, entrada in enumerate(em_ordem):
        seguinte = em_ordem[indice + 1] if indice + 1 < len(em_ordem) else None
        periodos.append({
            **entrada,
            "fim": mes_anterior(seguinte["inicio"]) if seguinte else "",
        })
    return periodos


def formatar_periodo_reuniao(periodo: dict) -> str:
    """A faixa de um período como ela aparece na tela: "05/2020 até 12/2023"."""
    def por_extenso(aaaa_mm: str) -> str:
        return f"{aaaa_mm[5:7]}/{aaaa_mm[0:4]}" if len(aaaa_mm or "") == 7 else ""

    inicio = por_extenso(periodo.get("inicio", ""))
    fim = por_extenso(periodo.get("fim", ""))
    if not inicio:
        return ""
    return f"{inicio} até {fim}" if fim else f"{inicio} até hoje"


# Uma pendência daqui a dez semanas e outra daqui a nove dias pediam a mesma
# frase na tela do Início: "falta 1 orador". Estes rótulos existem para as
# duas não se parecerem.
DIAS_URGENTE = 7
DIAS_ATENCAO = 21


def rotulo_de_prazo(data: date | None, hoje: date) -> tuple[str, str]:
    """Quanto falta para ``data`` e o quanto isso é urgente.

    Devolve (rótulo, nível), com nível em "vencido", "urgente", "atencao" ou
    "tranquilo". Sem data, devolve dois vazios: nem toda pendência tem prazo.
    """
    if data is None:
        return "", ""
    dias = (data - hoje).days
    if dias < 0:
        return "já passou", "vencido"
    if dias == 0:
        return "é hoje", "urgente"
    if dias == 1:
        return "é amanhã", "urgente"
    if dias <= DIAS_URGENTE:
        return f"em {dias} dias", "urgente"
    if dias <= DIAS_ATENCAO:
        return f"em {dias} dias", "atencao"
    return f"em {dias // 7} semanas", "tranquilo"


# Os meses por extenso, como aparecem nas telas, nos PDFs e nas imagens. O
# índice é o número do mês (1 a 12), por isso a primeira posição é vazia.
# Na visita do superintendente de circuito a reunião tem DOIS discursos: o
# público e o final. O tipo do evento é o que diz que aquela data é a visita,
# e o nome dele pode ter sido escrito de vários jeitos ("Visita do
# Superintendente", "Visita do SC de circuito") — o que não muda é a palavra.
def eh_visita_superintendente(tipo: str) -> bool:
    """Se este tipo de evento especial é a visita do superintendente."""
    return "superintendente" in _normalizar_texto_busca(tipo or "")


NOMES_MESES = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


# Como os dois nomes de um simpósio aparecem juntos, em toda parte.
SEPARADOR_SIMPOSIO = "/"


def nome_oradores(registro) -> str:
    """Nome do orador — ou dos dois, quando o discurso é um simpósio.

    O simpósio é um compromisso só, dividido entre dois oradores da
    congregação, então o par aparece junto em toda parte: na lista do mês, no
    quadro de anúncios e no relatório em PDF.
    """
    primeiro = (registro.get("orador_nome") or "").strip()
    segundo = (registro.get("orador_2_nome") or "").strip()
    if primeiro and segundo:
        return f"{primeiro}{SEPARADOR_SIMPOSIO}{segundo}"
    return primeiro or segundo
