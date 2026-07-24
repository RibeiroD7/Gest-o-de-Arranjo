"""PDF de relatórios (reportlab): frequência de oradores e temas parados.

Recebe os dados já prontos (o ``main.py`` os busca no banco) e monta um PDF com
dois quadros. Grava na área de exports gravável (ver ``armazenamento``).
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


def gerar_pdf_relatorios(
    frequencia_oradores: list[dict],
    temas_parados: list[dict],
    titulo: str = "Relatórios — Gestão de Arranjo",
) -> tuple[str | None, str | None]:
    """Gera um PDF com os dois quadros. Retorna ``(caminho, erro)``."""
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

        elementos: list = [
            Paragraph(titulo, estilo_titulo),
            Paragraph(f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", estilo_info),
        ]

        elementos.append(
            Paragraph("Frequência de oradores (minha congregação)", estilo_sub)
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
        elementos.append(Paragraph("Temas há mais tempo sem uso", estilo_sub))
        if temas_parados:
            linhas = [
                [
                    str(t.get("nr", "")),
                    t.get("titulo", ""),
                    t.get("ultimo_uso") or "nunca",
                ]
                for t in temas_parados
            ]
            elementos.append(
                _tabela(["Nº", "Tema", "Último uso"], linhas, [40, 330, 100])
            )
        else:
            elementos.append(Paragraph("Sem temas cadastrados.", estilo_info))

        doc.build(elementos)
        return str(caminho), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Não foi possível gerar o relatório: {exc}"
