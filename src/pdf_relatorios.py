"""PDF de relatórios (reportlab): o retrato do arranjo em uma folha.

Traz o que só se enxerga somando o ano inteiro — quem está discursando de
menos, quem está presidindo de menos e como está a troca com cada congregação.
Temas parados ficaram de fora de propósito: a aba Temas já mostra isso, com
filtro e ordenação.

Recebe os dados já prontos (o ``main.py`` os busca no banco). Grava na área de
exports gravável (ver ``armazenamento``).
"""

from __future__ import annotations

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from armazenamento import EXPORTS_DIR, garantir_pastas

_COR_CABECALHO = colors.Color(0.13, 0.16, 0.25)
_COR_ZEBRA = colors.Color(0.96, 0.96, 0.98)
_COR_GRADE = colors.Color(0.8, 0.8, 0.82)

_ESTILO_CELULA = ParagraphStyle("cel", fontName="Helvetica", fontSize=9, leading=11)
_ESTILO_CELULA_CAB = ParagraphStyle(
    "celCab", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white
)


def _cel(texto: str, cabecalho: bool = False) -> Paragraph:
    return Paragraph(str(texto), _ESTILO_CELULA_CAB if cabecalho else _ESTILO_CELULA)


def _tabela(cabecalhos: list[str], linhas: list[list[str]], larguras: list[int]) -> Table:
    dados = [[_cel(c, cabecalho=True) for c in cabecalhos]]
    dados += [[_cel(valor) for valor in linha] for linha in linhas]
    tabela = Table(dados, colWidths=larguras, repeatRows=1)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _COR_CABECALHO),
                ("GRID", (0, 0), (-1, -1), 0.5, _COR_GRADE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _COR_ZEBRA]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabela


def _quadro_resumo(resumo: dict) -> list[list[str]]:
    """Os números do ano, em pares rótulo/valor de duas colunas."""
    semanas = int(resumo.get("semanas", 0))
    cobertas = int(resumo.get("cobertas", 0))
    return [
        ["Semanas com orador", f"{cobertas} de {semanas}"],
        ["Semanas sem orador", str(max(0, semanas - cobertas))],
        ["Semanas com presidente", f"{int(resumo.get('presidentes', 0))} de {semanas}"],
        ["Oradores recebidos", str(int(resumo.get("recebidos", 0)))],
        ["Designações enviadas", str(int(resumo.get("enviados", 0)))],
        ["Aguardando confirmação", str(int(resumo.get("pendentes", 0)))],
        ["Datas especiais", str(int(resumo.get("especiais", 0)))],
    ]


def gerar_pdf_relatorios(
    frequencia_oradores: list[dict],
    presidencias: list[dict],
    meses: list[dict],
    resumo: dict | None = None,
    titulo: str = "Relatórios — Gestão de Arranjo",
    subtitulo: str = "",
) -> tuple[str | None, str | None]:
    """Gera o PDF com os quadros do arranjo. Retorna ``(caminho, erro)``."""
    try:
        garantir_pastas()
        caminho = EXPORTS_DIR / f"Relatorios_{datetime.now():%Y-%m-%d_%H-%M-%S}.pdf"
        doc = SimpleDocTemplate(
            str(caminho),
            pagesize=A4,
            title=titulo,
            topMargin=36,
            bottomMargin=36,
            leftMargin=36,
            rightMargin=36,
        )

        estilo_titulo = ParagraphStyle(
            "titulo", fontName="Helvetica-Bold", fontSize=16, spaceAfter=2
        )
        estilo_sub = ParagraphStyle(
            "sub", fontName="Helvetica-Bold", fontSize=12, spaceBefore=16, spaceAfter=6
        )
        estilo_info = ParagraphStyle(
            "info", fontName="Helvetica", fontSize=9, textColor=colors.grey, spaceAfter=4
        )

        rodape = f"Gerado em {datetime.now():%d/%m/%Y %H:%M}"
        elementos: list = [
            Paragraph(titulo, estilo_titulo),
            Paragraph(f"{subtitulo} · {rodape}" if subtitulo else rodape, estilo_info),
        ]

        if resumo:
            elementos.append(Paragraph("Resumo do ano", estilo_sub))
            elementos.append(
                _tabela(["Indicador", "Valor"], _quadro_resumo(resumo), [300, 170])
            )
            elementos.append(Spacer(1, 6))

        elementos.append(
            Paragraph("Oradores da minha congregação — discursos enviados", estilo_sub)
        )
        elementos.append(
            Paragraph(
                "Do que discursou menos (e há mais tempo) para o que mais discursou.",
                estilo_info,
            )
        )
        if frequencia_oradores:
            linhas = [
                [
                    o.get("nome", ""),
                    str(o.get("quantidade", 0)),
                    o.get("ultima_data") or "nunca",
                ]
                for o in frequencia_oradores
            ]
            elementos.append(
                _tabela(["Orador", "Discursos", "Último"], linhas, [300, 80, 90])
            )
        else:
            elementos.append(Paragraph("Sem oradores cadastrados.", estilo_info))

        elementos.append(Spacer(1, 6))
        elementos.append(Paragraph("Presidências da reunião", estilo_sub))
        elementos.append(
            Paragraph(
                "Quantas vezes cada um presidiu; quem presidiu menos vem primeiro.",
                estilo_info,
            )
        )
        if presidencias:
            linhas = [
                [
                    p.get("nome", ""),
                    p.get("categoria", ""),
                    str(p.get("quantidade", 0)),
                    p.get("ultima_data") or "nunca",
                ]
                for p in presidencias
            ]
            elementos.append(
                _tabela(
                    ["Presidente", "Privilégio", "Vezes", "Última"],
                    linhas,
                    [220, 120, 60, 90],
                )
            )
        else:
            elementos.append(Paragraph("Nenhum presidente cadastrado.", estilo_info))

        elementos.append(Spacer(1, 6))
        elementos.append(Paragraph("Mês a mês", estilo_sub))
        elementos.append(
            Paragraph(
                "Onde estão os buracos: semanas com orador e com presidente em "
                "cada mês já montado.",
                estilo_info,
            )
        )
        if meses:
            linhas = [
                [
                    m.get("nome", ""),
                    str(m.get("semanas", 0)),
                    f"{m.get('cobertas', 0)} de {m.get('semanas', 0)}",
                    f"{m.get('presidentes', 0)} de {m.get('semanas', 0)}",
                ]
                for m in meses
            ]
            elementos.append(
                _tabela(
                    ["Mês", "Semanas", "Com orador", "Com presidente"],
                    linhas,
                    [180, 70, 110, 110],
                )
            )
        else:
            elementos.append(Paragraph("Nenhum arranjo cadastrado.", estilo_info))

        doc.build(elementos)
        return str(caminho), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Não foi possível gerar o relatório: {exc}"


def gerar_pdf_secoes(
    secoes: list[dict],
    titulo: str,
    subtitulo: str = "",
    nome_arquivo: str = "Relatorio",
) -> tuple[str | None, str | None]:
    """Desenha uma lista de seções (ver ``relatorios.py``) num PDF.

    É o motor dos relatórios por tela: cada seção vira um título opcional, uma
    linha de descrição e uma tabela. Seção sem título encosta na anterior — é
    como um mês da programação junta as suas quatro tabelas num bloco só.

    Retorna ``(caminho, erro)``.
    """
    try:
        garantir_pastas()
        caminho = EXPORTS_DIR / f"{nome_arquivo}_{datetime.now():%Y-%m-%d_%H-%M-%S}.pdf"
        doc = SimpleDocTemplate(
            str(caminho),
            pagesize=A4,
            title=titulo,
            topMargin=36,
            bottomMargin=36,
            leftMargin=36,
            rightMargin=36,
        )

        estilo_titulo = ParagraphStyle(
            "titulo", fontName="Helvetica-Bold", fontSize=16, spaceAfter=2
        )
        estilo_sub = ParagraphStyle(
            "sub", fontName="Helvetica-Bold", fontSize=12, spaceBefore=14, spaceAfter=6
        )
        estilo_info = ParagraphStyle(
            "info", fontName="Helvetica", fontSize=9, textColor=colors.grey, spaceAfter=4
        )

        rodape = f"Gerado em {datetime.now():%d/%m/%Y %H:%M}"
        elementos: list = [
            Paragraph(titulo, estilo_titulo),
            Paragraph(f"{subtitulo} · {rodape}" if subtitulo else rodape, estilo_info),
        ]

        for secao in secoes:
            if secao.get("titulo"):
                elementos.append(Paragraph(secao["titulo"], estilo_sub))
            if secao.get("descricao"):
                elementos.append(Paragraph(secao["descricao"], estilo_info))
            if secao.get("linhas"):
                elementos.append(
                    _tabela(secao["cabecalhos"], secao["linhas"], secao["larguras"])
                )
                elementos.append(Spacer(1, 6))
            elif secao.get("vazio"):
                elementos.append(Paragraph(secao["vazio"], estilo_info))

        doc.build(elementos)
        return str(caminho), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Não foi possível gerar o relatório: {exc}"
