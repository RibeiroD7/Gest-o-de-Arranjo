"""Desenho dos relatórios em PDF (reportlab).

Este módulo só desenha: recebe as seções já montadas pelo ``relatorios.py`` e
as transforma em página — cabeçalho com a congregação e o contato do
coordenador, tarjas de bloco, tabelas com rótulo e um rodapé com a data de
geração e o número da página. Grava na área de exports gravável (ver
``armazenamento``).
"""

from __future__ import annotations

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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


# ---------------------------------------------------------------------------
# Motor dos relatórios por tela
# ---------------------------------------------------------------------------

_COR_MARCA = colors.Color(0.09, 0.42, 0.38)      # verde do app
_COR_TITULO = colors.Color(0.11, 0.16, 0.24)
_COR_APOIO = colors.Color(0.42, 0.46, 0.52)

_ESTILO_TITULO = ParagraphStyle(
    "tituloRel", fontName="Helvetica-Bold", fontSize=19, leading=22,
    textColor=_COR_TITULO, spaceAfter=0,
)
_ESTILO_CONGREGACAO = ParagraphStyle(
    "cong", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=_COR_MARCA,
    alignment=2,
)
_ESTILO_CONTATO = ParagraphStyle(
    "contato", fontName="Helvetica", fontSize=9, leading=12, textColor=_COR_APOIO,
    alignment=2,
)
_ESTILO_BLOCO = ParagraphStyle(
    "bloco", fontName="Helvetica-Bold", fontSize=12.5, leading=15,
    textColor=colors.white,
)
_ESTILO_BLOCO_APOIO = ParagraphStyle(
    "blocoApoio", fontName="Helvetica", fontSize=9, leading=12,
    textColor=colors.Color(0.85, 0.93, 0.91),
)
_ESTILO_ROTULO = ParagraphStyle(
    "rotulo", fontName="Helvetica-Bold", fontSize=8.5, leading=11,
    textColor=_COR_MARCA, spaceBefore=8, spaceAfter=3,
)
_ESTILO_NOTA = ParagraphStyle(
    "nota", fontName="Helvetica-Oblique", fontSize=8.5, leading=11,
    textColor=_COR_APOIO, spaceBefore=2, spaceAfter=4,
)

_LARGURA_UTIL = 523

# Acima disto a tabela não cabe numa página: não dá para mantê-la inteira.
_LINHAS_BLOCO_INTEIRO = 14


class _CanvasNumerado(canvas.Canvas):
    """Canvas que sabe o total de páginas — para o "Página X de Y" do rodapé.

    O reportlab só descobre o total depois de montar tudo, então as páginas
    ficam guardadas e o rodapé é escrito no fim.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas: list[dict] = []

    def showPage(self) -> None:
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._desenhar_rodape(total)
            super().showPage()
        super().save()

    def _desenhar_rodape(self, total: int) -> None:
        largura = self._pagesize[0]
        self.setStrokeColor(colors.Color(0.85, 0.87, 0.89))
        self.setLineWidth(0.5)
        self.line(36, 30, largura - 36, 30)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(_COR_APOIO)
        self.drawString(
            36, 20,
            f"Gestão de Arranjo · gerado em {datetime.now():%d/%m/%Y às %H:%M}",
        )
        self.drawRightString(largura - 36, 20, f"Página {self._pageNumber} de {total}")


def _faixa_bloco(titulo: str, apoio: str = "") -> Table:
    """Título de bloco (um mês, uma congregação) numa faixa colorida."""
    interno = [[Paragraph(titulo, _ESTILO_BLOCO)]]
    if apoio:
        interno.append([Paragraph(apoio, _ESTILO_BLOCO_APOIO)])
    faixa = Table(interno, colWidths=[_LARGURA_UTIL])
    faixa.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _COR_MARCA),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2 if apoio else 7),
                ("TOPPADDING", (0, 1), (-1, -1), 0),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
            ]
        )
    )
    return faixa


def _linha_marca() -> Table:
    regua = Table([[""]], colWidths=[_LARGURA_UTIL], rowHeights=[2.5])
    regua.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _COR_MARCA)]))
    return regua


def _cabecalho_relatorio(titulo: str, congregacao: str, contato: list[str]) -> list:
    """Título à esquerda; à direita, de quem é o arranjo e com quem falar."""
    direita: list = []
    if congregacao:
        direita.append(Paragraph(congregacao, _ESTILO_CONGREGACAO))
    direita += [Paragraph(linha, _ESTILO_CONTATO) for linha in contato if linha]

    cabecalho = Table(
        [[Paragraph(titulo, _ESTILO_TITULO), direita or ""]],
        colWidths=[280, _LARGURA_UTIL - 280],
    )
    cabecalho.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("VALIGN", (1, 0), (1, 0), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return [cabecalho, Spacer(1, 7), _linha_marca(), Spacer(1, 4)]


def gerar_pdf_secoes(
    secoes: list[dict],
    titulo: str,
    congregacao: str = "",
    contato: list[str] | None = None,
    nome_arquivo: str = "Relatorio",
) -> tuple[str | None, str | None]:
    """Desenha uma lista de seções (ver ``relatorios.py``) num PDF.

    Uma seção com ``faixa=True`` vira uma tarja colorida (o mês, a
    congregação); as demais viram um rótulo e a sua tabela. A data de geração
    e o número da página vão para o RODAPÉ, não para debaixo do título — o
    topo fica só com o relatório e de quem ele é.

    Retorna ``(caminho, erro)``.
    """
    try:
        garantir_pastas()
        caminho = EXPORTS_DIR / f"{nome_arquivo}_{datetime.now():%Y-%m-%d_%H-%M-%S}.pdf"
        doc = SimpleDocTemplate(
            str(caminho),
            pagesize=A4,
            title=titulo,
            author="Gestão de Arranjo",
            topMargin=32,
            bottomMargin=44,
            leftMargin=36,
            rightMargin=36,
        )

        elementos: list = _cabecalho_relatorio(titulo, congregacao, contato or [])

        for secao in secoes:
            corpo: list = []
            if secao.get("faixa"):
                elementos.append(Spacer(1, 10))
                corpo.append(_faixa_bloco(secao["titulo"], secao.get("descricao", "")))
                corpo.append(Spacer(1, 5))
            elif secao.get("titulo"):
                corpo.append(Paragraph(secao["titulo"], _ESTILO_ROTULO))
                if secao.get("descricao"):
                    corpo.append(Paragraph(secao["descricao"], _ESTILO_NOTA))
            elif secao.get("descricao"):
                corpo.append(Paragraph(secao["descricao"], _ESTILO_NOTA))

            if secao.get("linhas"):
                corpo.append(
                    _tabela(secao["cabecalhos"], secao["linhas"], secao["larguras"])
                )
            elif secao.get("vazio"):
                corpo.append(Paragraph(secao["vazio"], _ESTILO_NOTA))

            if not corpo:
                continue
            if len(corpo) == 1:
                elementos.append(corpo[0])
            elif len(secao.get("linhas") or []) <= _LINHAS_BLOCO_INTEIRO:
                # Bloco curto: rótulo e tabela viram um só, para não partir ao
                # meio nem deixar um cabeçalho órfão no pé da página.
                elementos.append(KeepTogether(corpo))
            else:
                # Tabela longa (o catálogo de temas tem ~200 linhas) não cabe
                # em página nenhuma: dentro de um KeepTogether ela seria
                # empurrada para a folha seguinte, deixando esta em branco.
                # Só se garante espaço para o rótulo e as primeiras linhas.
                elementos.append(CondPageBreak(72))
                elementos.extend(corpo)

        doc.build(elementos, canvasmaker=_CanvasNumerado)
        return str(caminho), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Não foi possível gerar o relatório: {exc}"
