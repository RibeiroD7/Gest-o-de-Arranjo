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
    intercambio: list[dict],
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
        elementos.append(Paragraph("Troca com as congregações", estilo_sub))
        elementos.append(
            Paragraph(
                "Discursos que vieram de cada congregação e os que mandamos para lá.",
                estilo_info,
            )
        )
        if intercambio:
            linhas = [
                [
                    c.get("congregacao", ""),
                    str(c.get("recebidos", 0)),
                    str(c.get("enviados", 0)),
                    c.get("ultima_data") or "—",
                ]
                for c in intercambio
            ]
            elementos.append(
                _tabela(
                    ["Congregação", "Recebidos", "Enviados", "Último"],
                    linhas,
                    [220, 80, 80, 90],
                )
            )
        else:
            elementos.append(Paragraph("Nenhum arranjo cadastrado.", estilo_info))

        doc.build(elementos)
        return str(caminho), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Não foi possível gerar o relatório: {exc}"
