"""
Geração do PDF do Quadro de Anúncios (Conferência Pública), com reportlab.

O quadro é publicado de 2 em 2 meses (Jan-Fev, Mar-Abr, Mai-Jun, Jul-Ago,
Set-Out, Nov-Dez), com uma página por mês. Cada página lista, para cada
data de reunião de fim de semana do mês, quem preside, o orador visitante,
o tema e a congregação de origem — no layout do modelo fornecido.
"""

from __future__ import annotations

import os
import platform
import subprocess
from calendar import monthrange
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from database import get_connection, reuniao_em
from util import NOMES_MESES, SEPARADOR_SIMPOSIO, eh_visita_superintendente

EXPORTS_DIR = os.path.join("exports")

# Cores e geometria extraídas do PDF modelo (DISCURSOS PÚBLICOS - MARÇO-ABRIL)
COR_FAIXA_TITULO = colors.Color(0.784, 0.251, 0.251)
COR_FAIXA_SECUNDARIA = colors.Color(0.459, 0.439, 0.439)
COR_BORDA = colors.black
COR_DIVISOR = COR_FAIXA_SECUNDARIA

LARGURA_TABELA = 555
# Limites de coluna em x=63, x=112 e x=277 (valores do modelo, relativos à tabela)
LARGURAS_COLUNAS = [63, 49, 165, 278]
ALTURA_TITULO = 31
ALTURA_MES = 23
ALTURA_DATA = 18
ALTURAS_CORPO = [31, 30, 31]
# Linha extra do discurso final, só nas datas que têm dois discursos (a visita
# do superintendente). Mais baixa que as outras para o mês de cinco semanas
# continuar cabendo na página.
ALTURA_DISCURSO_FINAL = 26
ALTURA_DIVISOR = 16
ALTURA_RODAPE = 15
FONTE_NEGRITO = "Helvetica-Bold"

# Nome do dia para o cabeçalho de cada data do quadro. Sai da própria data,
# não da configuração: o quadro trazia "SÁBADO" fixo e mentia em todo mês de
# uma época em que a reunião era no domingo.
NOMES_DIA_SEMANA = [
    "SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA",
    "SEXTA-FEIRA", "SÁBADO", "DOMINGO",
]

MAP_DIA_SEMANA = {
    "domingo": 6, "segunda-feira": 0, "segunda": 0, "terça-feira": 1, "terca-feira": 1,
    "terça": 1, "terca": 1, "quarta-feira": 2, "quarta": 2, "quinta-feira": 3, "quinta": 3,
    "sexta-feira": 4, "sexta": 4, "sábado": 5, "sabado": 5,
}

PARES_MESES = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12)]

# Como o quadro é nomeado na pasta da congregação (ver _nome_arquivo).
PREFIXO_ARQUIVO = "DISCURSOS PÚBLICOS"


def _carregar_configuracao() -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT nome_congregacao, dia_reuniao FROM configuracoes WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"nome_congregacao": "", "dia_reuniao": ""}
    return {
        "nome_congregacao": row[0] or "",
        "dia_reuniao": row[1] or "Sábado",
    }


def _dia_semana_para_weekday(dia_semana: str) -> int:
    texto = (dia_semana or "").strip().lower()
    for chave, valor in MAP_DIA_SEMANA.items():
        if chave in texto:
            return valor
    return 5


def _datas_reuniao_do_mes(ano: int, mes: int, weekday: int) -> list[date]:
    ultimo_dia = monthrange(ano, mes)[1]
    return [
        date(ano, mes, dia)
        for dia in range(1, ultimo_dia + 1)
        if date(ano, mes, dia).weekday() == weekday
    ]


def rotulo_par_meses(mes_inicial: int) -> str:
    return f"{NOMES_MESES[mes_inicial]}-{NOMES_MESES[mes_inicial + 1]}"


def par_meses_do_mes(mes: int) -> tuple[int, int]:
    for inicio, fim in PARES_MESES:
        if mes in (inicio, fim):
            return inicio, fim
    return (1, 2)


def carregar_dados_mes(ano: int, mes: int) -> list[dict]:
    """Uma linha por data de reunião do mês: presidente, orador, tema e congregação.

    O dia vem da linha do tempo da congregação, não da configuração atual: um
    quadro de 2021 (domingo) montado com o sábado de hoje procurava datas que
    não existem e saía vazio, com tudo gravado no banco.
    """
    periodo = reuniao_em(ano, mes)
    dia = periodo["dia_semana"] if periodo else _carregar_configuracao().get("dia_reuniao", "")
    weekday = _dia_semana_para_weekday(dia)
    datas = _datas_reuniao_do_mes(ano, mes, weekday)
    mes_str = f"{mes:02d}"

    conn = get_connection()
    try:
        recebidos: dict[str, dict] = {}
        for linha in conn.execute(
                """
                SELECT ao.data, COALESCE(o.nome, ''), COALESCE(t.titulo, ''), COALESCE(c.nome, ''),
                       ao.tema_nr, COALESCE(o2.nome, '')
                FROM arranjo_oradores ao
                JOIN oradores o ON ao.orador_id = o.id
                LEFT JOIN oradores o2 ON ao.orador_2_id = o2.id
                LEFT JOIN temas t ON ao.tema_nr = t.nr
                LEFT JOIN congregacoes c ON ao.congregacao_id = c.id
                WHERE ao.tipo = 'recebido'
                  AND substr(ao.data, 7, 4) = ?
                  AND substr(ao.data, 4, 2) = ?
                """,
                (str(ano), mes_str),
        ):
            data_reg, orador, tema, congregacao, tema_nr, orador_2 = linha
            if tema and tema_nr and not tema.startswith(f"{tema_nr}"):
                tema = f"{tema_nr} - {tema}"
            # Simpósio numa linha só (orador_2_id) — e o formato antigo, com
            # dois registros na mesma data, que ainda existe em arranjos
            # cadastrados antes de o simpósio virar um campo.
            if orador_2:
                orador = f"{orador}{SEPARADOR_SIMPOSIO}{orador_2}"
            if data_reg in recebidos:
                recebidos[data_reg]["orador"] += f"{SEPARADOR_SIMPOSIO}{orador}"
            else:
                recebidos[data_reg] = {
                    "orador": orador, "tema": tema, "congregacao": congregacao
                }
        presidentes = {
            linha[0]: linha[1]
            for linha in conn.execute(
                """
                SELECT p.data, COALESCE(c.nome, p.nome_avulso, '')
                FROM presidentes p
                LEFT JOIN presidentes_cadastro c ON p.presidente_id = c.id
                WHERE substr(p.data, 7, 4) = ? AND substr(p.data, 4, 2) = ?
                """,
                (str(ano), mes_str),
            )
        }
        especiais = {
            linha[0]: {
                "tipo": linha[1],
                "orador": linha[2],
                "tema": linha[3],
                "presidente": linha[4],
                "congregacao": linha[5],
                "tema_final": linha[6],
            }
            for linha in conn.execute(
                """
                SELECT e.data, e.tipo,
                       COALESCE(e.orador, ''), COALESCE(e.tema, ''),
                       COALESCE(c.nome, ''), COALESCE(cong.nome, ''),
                       COALESCE(e.tema_final, '')
                FROM datas_especiais e
                LEFT JOIN presidentes_cadastro c ON e.presidente_id = c.id
                LEFT JOIN congregacoes cong ON e.congregacao_id = cong.id
                WHERE substr(e.data, 7, 4) = ? AND substr(e.data, 4, 2) = ?
                """,
                (str(ano), mes_str),
            )
        }
    finally:
        conn.close()

    linhas = []
    for data_ref in datas:
        data_str = data_ref.strftime("%d/%m/%Y")
        especial = especiais.get(data_str)
        if especial:
            # Data especial substitui a programação normal no quadro.
            # Sem discurso (nem orador nem tema): o tipo do evento vai no
            # campo "Orador". Com discurso: mostra orador, tema e a
            # congregação de origem do orador (nunca o tipo do evento).
            orador_txt = (especial["orador"] or "").strip()
            tema_txt = (especial["tema"] or "").strip()
            # Na visita do superintendente a reunião tem dois discursos, e o
            # quadro mostra os dois: o final ganha uma linha própria, anunciada
            # mesmo quando o tema ainda não chegou.
            visita = eh_visita_superintendente(especial["tipo"])
            final_txt = (especial.get("tema_final") or "").strip()
            if not final_txt and visita:
                final_txt = "—"
            # O superintendente não vem de uma congregação: na visita a linha
            # da congregação não existe (vazio = a linha não é desenhada).
            congregacao_txt = "" if visita else (especial["congregacao"] or "—")
            linhas.append(
                {
                    "data": data_ref,
                    "presidente": especial["presidente"] or "—",
                    "orador": orador_txt or especial["tipo"],
                    "tema": tema_txt or "—",
                    "congregacao": congregacao_txt,
                    "tema_final": final_txt,
                }
            )
            continue
        info = recebidos.get(data_str, {})
        linhas.append(
            {
                "data": data_ref,
                "presidente": presidentes.get(data_str) or "—",
                "orador": info.get("orador") or "—",
                "tema": info.get("tema") or "—",
                "congregacao": info.get("congregacao") or "—",
                "tema_final": "",
            }
        )
    return linhas


def _nome_arquivo(mes_inicial: int) -> str:
    """Nome do PDF no formato em que o quadro é arquivado e enviado.

    Sai como ``DISCURSOS PÚBLICOS - SETEMBRO-OUTUBRO.pdf``, igual aos que já
    estão na pasta da congregação: o arquivo vai para lá como está, sem
    renomear na mão a cada dois meses. O ano não entra no nome porque ele é a
    pasta ("2026/Quadro"); gerar o mesmo par de meses de novo regrava o
    arquivo em ``exports/``, que é área de passagem.
    """
    return f"{PREFIXO_ARQUIVO} - {rotulo_par_meses(mes_inicial).upper()}.pdf"


def _tamanho_ajustado(texto: str, largura_max: float, tamanho_inicial: int = 14, minimo: int = 9) -> int:
    """Reduz o tamanho da fonte até o texto caber em uma linha (como no modelo)."""
    tamanho = tamanho_inicial
    while tamanho > minimo and stringWidth(texto, FONTE_NEGRITO, tamanho) > largura_max:
        tamanho -= 1
    return tamanho


def _paragrafo(texto: str, tamanho: int, centralizado: bool = False) -> Paragraph:
    """Texto preto em negrito, como todo o texto do modelo."""
    estilo = ParagraphStyle(
        "CelulaQuadro",
        fontName=FONTE_NEGRITO,
        fontSize=tamanho,
        textColor=colors.black,
        alignment=1 if centralizado else 0,
        leading=tamanho + 2,
    )
    return Paragraph(texto, estilo)


def _construir_tabela_mes(ano: int, mes: int, nome_congregacao: str) -> Table:
    """Monta a tabela de uma página (um mês) replicando a geometria do modelo."""
    dados = carregar_dados_mes(ano, mes)

    linhas: list[list] = []
    alturas: list[float] = []
    estilo_cmds: list[tuple] = []

    def adicionar_linha(celulas: list, altura: float) -> int:
        linhas.append(celulas)
        alturas.append(altura)
        return len(linhas) - 1

    titulo = f"Conferência Pública - {nome_congregacao}"
    r = adicionar_linha([_paragrafo(titulo, _tamanho_ajustado(titulo, LARGURA_TABELA - 8, 24), True), "", "", ""], ALTURA_TITULO)
    estilo_cmds += [
        ("SPAN", (0, r), (3, r)),
        ("BACKGROUND", (0, r), (3, r), COR_FAIXA_TITULO),
        ("BOTTOMPADDING", (0, r), (3, r), 2),
    ]

    r = adicionar_linha([_paragrafo(f"{NOMES_MESES[mes]}/{ano}", 18, True), "", "", ""], ALTURA_MES)
    estilo_cmds += [
        ("SPAN", (0, r), (3, r)),
        ("BACKGROUND", (0, r), (3, r), COR_FAIXA_SECUNDARIA),
        ("BOTTOMPADDING", (0, r), (3, r), 2),
    ]

    # Linha dupla do modelo: o cinza continua até encostar na faixa vermelha,
    # com as duas linhas pretas desenhadas sobre a junção (sem filete branco)
    r = adicionar_linha(["", "", "", ""], 2)
    estilo_cmds += [
        ("SPAN", (0, r), (3, r)),
        ("BACKGROUND", (0, r), (3, r), COR_FAIXA_SECUNDARIA),
    ]

    for indice, item in enumerate(dados):
        dia = item["data"].day
        nome_dia = NOMES_DIA_SEMANA[item["data"].weekday()]
        rotulo_data = f"{nome_dia}, {dia} DE {NOMES_MESES[mes].upper()}"
        largura_vermelha = sum(LARGURAS_COLUNAS[:3])
        presidente = item["presidente"]
        texto_presidente = (
            "PRESIDENTE:" + "&nbsp;" * 6 + presidente if presidente and presidente != "—"
            else "PRESIDENTE:"
        )
        tamanho_pres = _tamanho_ajustado(
            f"PRESIDENTE:      {presidente}", LARGURAS_COLUNAS[3] - 23, 14
        )
        r = adicionar_linha(
            [
                _paragrafo(rotulo_data, _tamanho_ajustado(rotulo_data, largura_vermelha - 6, 14), True),
                "",
                "",
                _paragrafo(texto_presidente, tamanho_pres),
            ],
            ALTURA_DATA,
        )
        estilo_cmds += [
            ("SPAN", (0, r), (2, r)),
            ("BACKGROUND", (0, r), (2, r), COR_FAIXA_TITULO),
            ("BACKGROUND", (3, r), (3, r), COR_FAIXA_SECUNDARIA),
            ("LINEAFTER", (2, r), (2, r), 1, COR_BORDA),
            ("LEFTPADDING", (3, r), (3, r), 21),
        ]

        # Larguras úteis dos valores: Orador/Tema começam em x=63; Congregação em x=112
        largura_valor_curto = LARGURA_TABELA - LARGURAS_COLUNAS[0] - 4
        largura_valor_longo = LARGURA_TABELA - sum(LARGURAS_COLUNAS[:2]) - 4
        campos = [
            ("Orador:", item["orador"], 0, 1, largura_valor_curto, ALTURAS_CORPO[0]),
            ("Tema:", item["tema"], 0, 1, largura_valor_curto, ALTURAS_CORPO[1]),
        ]
        if item.get("tema_final"):
            campos.append(
                ("Discurso final:", item["tema_final"], 1, 2, largura_valor_longo,
                 ALTURA_DISCURSO_FINAL)
            )
        if item["congregacao"]:
            campos.append(
                ("Congregação:", item["congregacao"], 1, 2, largura_valor_longo,
                 ALTURAS_CORPO[2])
            )
        for rotulo, valor, fim_rotulo, inicio_valor, largura_valor, altura in campos:
            celulas: list = ["", "", "", ""]
            largura_rotulo = sum(LARGURAS_COLUNAS[: fim_rotulo + 1]) - 4
            celulas[0] = _paragrafo(rotulo, _tamanho_ajustado(rotulo, largura_rotulo, 14))
            celulas[inicio_valor] = _paragrafo(valor, _tamanho_ajustado(valor, largura_valor, 14))
            r = adicionar_linha(celulas, altura)
            if fim_rotulo > 0:
                estilo_cmds.append(("SPAN", (0, r), (fim_rotulo, r)))
            estilo_cmds += [
                ("SPAN", (inicio_valor, r), (3, r)),
                ("BACKGROUND", (0, r), (3, r), colors.white),
                ("LEFTPADDING", (0, r), (0, r), 2),
            ]

        if indice < len(dados) - 1:
            r = adicionar_linha(["", "", "", ""], ALTURA_DIVISOR)
            estilo_cmds += [
                ("SPAN", (0, r), (3, r)),
                ("BACKGROUND", (0, r), (3, r), COR_DIVISOR),
            ]
            r = adicionar_linha(["", "", "", ""], 2)
            estilo_cmds += [
                ("SPAN", (0, r), (3, r)),
                ("BACKGROUND", (0, r), (3, r), COR_DIVISOR),
            ]

    r = adicionar_linha(["", "", "", ""], ALTURA_RODAPE)
    estilo_cmds += [("SPAN", (0, r), (3, r))]
    r = adicionar_linha(["", "", "", ""], 2)
    estilo_cmds.append(("SPAN", (0, r), (3, r)))

    linhas_horizontais = [
        ("LINEBELOW", (0, indice), (3, indice), 1, COR_BORDA)
        for indice in range(len(linhas) - 1)
    ]

    tabela = Table(linhas, colWidths=LARGURAS_COLUNAS, rowHeights=alturas)
    tabela.setStyle(
        TableStyle(
            [
                # Paddings globais primeiro: os específicos por célula em
                # `estilo_cmds` (rótulos 2pt, PRESIDENTE 21pt) têm precedência.
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                *estilo_cmds,
                *linhas_horizontais,
                ("BOX", (0, 0), (-1, -1), 1, COR_BORDA),
            ]
        )
    )
    return tabela


def gerar_quadro_anuncios(ano: int, mes_inicial: int) -> tuple[str | None, str | None]:
    """
    Gera o PDF do quadro de anúncios para o par de meses de `mes_inicial`
    (ex.: 3 → Março e Abril), uma página por mês.

    Retorna (caminho_arquivo, mensagem_erro).
    """
    inicio, fim = par_meses_do_mes(mes_inicial)
    config = _carregar_configuracao()
    nome_congregacao = config.get("nome_congregacao") or "Minha congregação"

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    caminho = os.path.join(EXPORTS_DIR, _nome_arquivo(inicio))

    doc = SimpleDocTemplate(
        caminho,
        pagesize=A4,
        # O Frame do platypus adiciona 6pt de padding interno; compensamos para
        # que a tabela comece exatamente em x=20 / y=54 como no modelo.
        leftMargin=14,
        rightMargin=A4[0] - 14 - LARGURA_TABELA - 12,
        topMargin=48,
        bottomMargin=40,
        title=f"Quadro de Anúncios - {rotulo_par_meses(inicio)} {ano}",
    )

    elementos = []
    for indice, mes in enumerate((inicio, fim)):
        elementos.append(_construir_tabela_mes(ano, mes, nome_congregacao))
        if indice == 0:
            elementos.append(PageBreak())

    doc.build(elementos)
    return caminho, None


def abrir_arquivo(caminho: str) -> None:
    """Abre o arquivo gerado com o aplicativo padrão do sistema."""
    sistema = platform.system()
    if sistema == "Windows":
        os.startfile(caminho)  # noqa: S606
    elif sistema == "Darwin":
        subprocess.run(["open", caminho], check=False)
    else:
        subprocess.run(["xdg-open", caminho], check=False)
