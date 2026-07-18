"""
Geração do PDF da Lista de Oradores Públicos (envio ao superintendente).

Implementado em reportlab (sem depender de Excel/LibreOffice), para produzir
resultado idêntico em Windows, Linux, macOS e celular.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from armazenamento import EXPORTS_DIR
from database import get_connection

TITULO = "Lista de Oradores Públicos"

COR_TEXTO = colors.HexColor("#1a1a1a")
COR_LABEL = colors.HexColor("#555555")
COR_CABECALHO_TABELA = colors.HexColor("#e8e8e8")
COR_LINHA = colors.HexColor("#bbbbbb")
COR_ZEBRA = colors.HexColor("#f6f6f6")


def _formatar_esbocos(temas: str, observacoes: str) -> str:
    if observacoes and "qualquer tema" in observacoes.lower():
        return "Qualquer tema"
    if temas and str(temas).strip():
        return str(temas).strip()
    return ""


def _formatar_nome_orador(nome: str, categoria: str) -> str:
    nome = (nome or "").strip()
    categoria = (categoria or "").strip()
    if nome and categoria:
        return f"{nome} ({categoria})"
    return nome


def _linhas_endereco(endereco: str) -> tuple[str, str]:
    if not (endereco or "").strip():
        return "", ""
    partes = [p.strip() for p in endereco.replace("\n", " - ").split(" - ") if p.strip()]
    if not partes:
        return "", ""
    if len(partes) == 1:
        return partes[0], ""
    return partes[0], partes[1]


def _linha_reuniao(dia: str, horario: str) -> str:
    if dia and horario:
        return f"{dia}, {horario}"
    return dia or horario or ""


def _carregar_configuracao() -> dict:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT nome_congregacao, endereco, cidade, cep, coordenador_discursos,
                   telefone_coordenador, dia_reuniao, horario_reuniao, circuito
            FROM configuracoes WHERE id = 1
            """
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return {chave: "" for chave in (
            "nome_congregacao", "endereco", "cidade", "cep", "coordenador_discursos",
            "telefone_coordenador", "dia_reuniao", "horario_reuniao", "circuito",
        )}

    return {
        "nome_congregacao": row[0] or "",
        "endereco": row[1] or "",
        "cidade": row[2] or "",
        "cep": row[3] or "",
        "coordenador_discursos": row[4] or "",
        "telefone_coordenador": row[5] or "",
        "dia_reuniao": row[6] or "",
        "horario_reuniao": row[7] or "",
        "circuito": row[8] or "",
    }


def carregar_oradores_por_ids(orador_ids: list[int]) -> list[dict]:
    if not orador_ids:
        return []

    placeholders = ",".join("?" * len(orador_ids))
    conn = get_connection()
    try:
        cursor = conn.execute(
            f"""
            SELECT o.id,
                   o.nome,
                   o.telefone,
                   o.categoria,
                   o.observacoes,
                   COALESCE((
                       SELECT GROUP_CONCAT(ot.tema_nr, ', ')
                       FROM orador_temas ot
                       WHERE ot.orador_id = o.id
                   ), '') AS temas
            FROM oradores o
            WHERE o.id IN ({placeholders})
            ORDER BY o.categoria, o.nome
            """,
            orador_ids,
        )
        colunas = [desc[0] for desc in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    finally:
        conn.close()


def _nome_arquivo_pdf() -> str:
    return f"Lista_Oradores_Envio_{datetime.now().strftime('%Y-%m')}.pdf"


def _bloco_cabecalho(config: dict) -> Table:
    """Bloco superior com dados da congregação (esquerda) e coordenador (direita)."""
    nome = config.get("nome_congregacao") or "Minha congregação"
    circuito = (config.get("circuito") or "").strip()
    cidade = (config.get("cidade") or "").strip()
    cep = (config.get("cep") or "").strip()
    coordenador = (config.get("coordenador_discursos") or "").strip()
    telefone = (config.get("telefone_coordenador") or "").strip()
    reuniao = _linha_reuniao(
        (config.get("dia_reuniao") or "").strip(),
        (config.get("horario_reuniao") or "").strip(),
    )
    endereco1, endereco2 = _linhas_endereco(config.get("endereco", ""))

    est_forte = ParagraphStyle("forte", fontName="Helvetica-Bold", fontSize=11,
                               textColor=COR_TEXTO, leading=14)
    est_normal = ParagraphStyle("normal", fontName="Helvetica", fontSize=9.5,
                                textColor=COR_TEXTO, leading=13)
    est_label = ParagraphStyle("label", fontName="Helvetica", fontSize=8.5,
                               textColor=COR_LABEL, leading=12)

    esquerda = [Paragraph(f"{nome}" + (f" ({circuito})" if circuito else ""), est_forte)]
    for texto in (endereco1, endereco2, cidade, cep):
        if texto:
            esquerda.append(Paragraph(texto, est_normal))
    if reuniao:
        esquerda.append(Spacer(1, 4))
        esquerda.append(Paragraph("Reunião de fim de semana", est_label))
        esquerda.append(Paragraph(reuniao, est_normal))

    direita = [Paragraph("Coordenador de discursos públicos", est_label)]
    if coordenador:
        direita.append(Paragraph(coordenador, est_normal))
    if telefone:
        direita.append(Paragraph(f"Tel {telefone}", est_normal))

    tabela = Table([[esquerda, direita]], colWidths=[11 * cm, 7 * cm])
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tabela


def _tabela_oradores(oradores: list[dict]) -> Table:
    est_cel = ParagraphStyle("cel", fontName="Helvetica", fontSize=9,
                             textColor=COR_TEXTO, leading=11)
    est_cel_nome = ParagraphStyle("celnome", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=COR_TEXTO, leading=11)
    est_cab = ParagraphStyle("cab", fontName="Helvetica-Bold", fontSize=9,
                             textColor=COR_TEXTO, leading=11, alignment=TA_LEFT)

    linhas = [[
        Paragraph("Oradores", est_cab),
        Paragraph("Contato", est_cab),
        Paragraph("Esboços", est_cab),
        Paragraph("Notas", est_cab),
    ]]
    for orador in oradores:
        linhas.append([
            Paragraph(_formatar_nome_orador(orador["nome"], orador.get("categoria", "")), est_cel_nome),
            Paragraph(orador.get("telefone") or "", est_cel),
            Paragraph(_formatar_esbocos(orador.get("temas", ""), orador.get("observacoes", "")), est_cel),
            Paragraph(orador.get("observacoes") or "", est_cel),
        ])

    tabela = Table(linhas, colWidths=[6.4 * cm, 3.2 * cm, 4.6 * cm, 3.8 * cm], repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), COR_CABECALHO_TABELA),
        ("GRID", (0, 0), (-1, -1), 0.5, COR_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(linhas)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), COR_ZEBRA))
    tabela.setStyle(TableStyle(estilo))
    return tabela


def gerar_pdf_envio(oradores_selecionados: list[int]) -> tuple[str | None, str | None]:
    """Gera o PDF da lista de oradores para envio. Retorna (caminho, erro)."""
    if not oradores_selecionados:
        return None, "Nenhum orador selecionado."

    oradores = carregar_oradores_por_ids(oradores_selecionados)
    if not oradores:
        return None, "Nenhum orador válido encontrado para gerar o PDF."

    config = _carregar_configuracao()
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = (EXPORTS_DIR / _nome_arquivo_pdf()).resolve()

    try:
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
            title=TITULO,
        )
        est_titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=15,
                                    textColor=COR_TEXTO, alignment=TA_CENTER, spaceAfter=12)
        elementos = [
            Paragraph(TITULO, est_titulo),
            _bloco_cabecalho(config),
            Spacer(1, 14),
            _tabela_oradores(oradores),
        ]
        doc.build(elementos)
    except Exception as exc:  # noqa: BLE001 — reportar erro amigável na UI
        return None, f"Erro ao gerar o PDF: {exc}"

    return str(pdf_path), None
