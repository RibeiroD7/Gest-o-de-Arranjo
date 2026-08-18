"""
Geração de imagem PNG com a lista de oradores recebidos de um arranjo mensal.
"""

from __future__ import annotations

import io
import os
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from armazenamento import ASSETS_DIR, EXPORTS_DIR

ESCALA = 3
DPI = 300
LARGURA_BASE = 480
LARGURA_IMAGEM = LARGURA_BASE * ESCALA

COR_FUNDO = "#FFFFFF"
COR_TEXTO = "#111827"
COR_SECUNDARIO = "#374151"
COR_DESTAQUE = "#1565C0"
COR_DESTAQUE_ESCURO = "#0A3D91"
COR_FAIXA_TITULO = "#F4F7FB"
COR_TITULO = "#1E3A5F"
COR_REUNIAO = "#3D4F63"
COR_CABECALHO_TABELA = "#0D47A1"
COR_TEXTO_CABECALHO = "#FFFFFF"
COR_BORDA = "#D5DEE8"
COR_LINHA_ALT = "#F3F7FB"
COR_SUBLINHADO = "#64B5F6"

NOMES_ESPECIAIS = {"Reunião Especial", "Arranjo Local"}

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


def _px(valor: int | float) -> int:
    return int(valor * ESCALA)


def _sanitizar_nome_arquivo(nome: str) -> str:
    texto = re.sub(r"[^\w\s-]", "", nome or "")
    return re.sub(r"\s+", "_", texto.strip()) or "Congregacao"


def _formatar_reuniao_cong(nome: str, dia: str, horario: str) -> str:
    nome = (nome or "—").strip()
    horario_txt = f"{(dia or '').strip()} {(horario or '').strip()}".strip() or "—"
    return f"Reunião Cong. {nome}: {horario_txt}"


def sugerir_nome_arquivo_exportacao(
    arranjo: dict,
    reunioes: dict,
    prefixo: str = "Oradores",
) -> str:
    mes = int(arranjo.get("mes_inicio", 1))
    ano = int(arranjo.get("ano", 2026))
    mes_nome = NOMES_MESES[mes] if 1 <= mes <= 12 else str(mes)
    host_nome = reunioes.get("host_nome") or "Anfitria"
    return f"{prefixo}_{mes_nome}_{ano}_{_sanitizar_nome_arquivo(host_nome)}.png"


def sugerir_nome_arquivo_oradores(arranjo: dict, reunioes: dict) -> str:
    return sugerir_nome_arquivo_exportacao(arranjo, reunioes, "Oradores")


def _carminhos_fonte_sistema(negrito: bool) -> list[str]:
    sistema = platform.system()
    if sistema == "Windows":
        return [
            "C:/Windows/Fonts/segoeuib.ttf" if negrito else "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if negrito else "C:/Windows/Fonts/arial.ttf",
        ]
    if sistema == "Darwin":
        return [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if negrito
            else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    return [
        "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf" if negrito
        else "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if negrito
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrito
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]


def _fonte_embutida(negrito: bool) -> str | None:
    """Fonte Liberation Sans embutida nos assets (usada em todas as plataformas)."""
    nome = "LiberationSans-Bold.ttf" if negrito else "LiberationSans-Regular.ttf"
    for base in (ASSETS_DIR / "fonts", Path("assets") / "fonts"):
        caminho = base / nome
        if caminho.exists():
            return str(caminho)
    return None


def _carregar_fonte(tamanho: int, negrito: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    tamanho_px = _px(tamanho)
    embutida = _fonte_embutida(negrito)
    if embutida:
        return ImageFont.truetype(embutida, tamanho_px)
    for caminho in _carminhos_fonte_sistema(negrito):
        if os.path.exists(caminho):
            return ImageFont.truetype(caminho, tamanho_px)
    try:
        return ImageFont.load_default(size=tamanho_px)
    except TypeError:
        return ImageFont.load_default()


def _largura_texto(draw: ImageDraw.ImageDraw, texto: str, fonte) -> float:
    if hasattr(draw, "textlength"):
        return draw.textlength(texto, font=fonte)
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    return bbox[2] - bbox[0]


def _ajustar_fonte_titulo(
    draw: ImageDraw.ImageDraw,
    texto: str,
    largura_max: int,
    tamanho_inicial: int = 32,
    tamanho_minimo: int = 22,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for tamanho in range(tamanho_inicial, tamanho_minimo - 1, -1):
        fonte = _carregar_fonte(tamanho, negrito=True)
        if _largura_texto(draw, texto, fonte) <= largura_max:
            return fonte
    return _carregar_fonte(tamanho_minimo, negrito=True)


def _x_texto_centralizado(x_inicio: int, largura_area: int, largura_texto: float) -> int:
    return int(x_inicio + (largura_area - largura_texto) / 2)


def _quebrar_texto(
    draw: ImageDraw.ImageDraw,
    texto: str,
    fonte,
    largura_max: int,
) -> list[str]:
    texto = (texto or "—").strip() or "—"
    if _largura_texto(draw, texto, fonte) <= largura_max:
        return [texto]

    linhas: list[str] = []
    palavras = texto.split()
    atual = ""
    for palavra in palavras:
        candidato = f"{atual} {palavra}".strip()
        if _largura_texto(draw, candidato, fonte) <= largura_max:
            atual = candidato
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas or ["—"]


def _formatar_data_curta(data: str | None) -> str:
    if not data:
        return "—"
    texto = data.strip()
    if len(texto) >= 5:
        return texto[0:5]
    return texto


def _rotulo_tema(registro: dict) -> str:
    if registro.get("especial"):
        tema = (registro.get("tema_titulo") or "").strip()
        return tema or (registro.get("orador_nome") or "").strip()
    nome = (registro.get("orador_nome") or "").strip()
    if nome in NOMES_ESPECIAIS:
        return nome
    tema = (registro.get("tema_titulo") or "").strip()
    if tema:
        nr = registro.get("tema_nr")
        if nr and not tema.startswith(f"{nr}"):
            return f"{nr} - {tema}"
        return tema
    if not registro.get("tema_nr"):
        return "Sem tema definido"
    return "—"


def _ordenar_por_data(registros: list[dict]) -> list[dict]:
    def chave(registro: dict) -> tuple[str, str, str]:
        partes = (registro.get("data") or "").split("/")
        if len(partes) == 3:
            return partes[2], partes[1], partes[0]
        return "9999", "99", "99"

    return sorted(registros, key=chave)


def _desenhar_retangulo_arredondado(
    draw: ImageDraw.ImageDraw,
    caixa: tuple[int, int, int, int],
    raio: int,
    fill: str | None = None,
    outline: str | None = None,
    largura: int = 1,
) -> None:
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(caixa, radius=raio, fill=fill, outline=outline, width=largura)
        return
    draw.rectangle(caixa, fill=fill, outline=outline, width=largura)


def _montar_linhas_tabela(
    draw: ImageDraw.ImageDraw,
    registros: list[dict],
    fonte_orador,
    fonte_tema,
    largura_conteudo: int,
    altura_linha_orador: int,
    altura_linha_tema: int,
    padding_celula: int,
    gap_orador_tema: int,
) -> list[dict]:
    """Monta linhas em layout vertical: orador e tema empilhados na coluna de conteúdo."""
    linhas = []
    for registro in _ordenar_por_data(registros):
        orador_quebrado = _quebrar_texto(
            draw,
            registro.get("orador_nome") or "—",
            fonte_orador,
            largura_conteudo,
        )
        tema_quebrado = _quebrar_texto(draw, _rotulo_tema(registro), fonte_tema, largura_conteudo)
        altura_conteudo = (
            len(orador_quebrado) * altura_linha_orador
            + gap_orador_tema
            + len(tema_quebrado) * altura_linha_tema
        )
        linhas.append(
            {
                "data": _formatar_data_curta(registro.get("data")),
                "orador": orador_quebrado,
                "tema": tema_quebrado,
                "altura": altura_conteudo + (padding_celula * 2),
            }
        )
    return linhas


def gerar_png_oradores(
    arranjo: dict,
    reunioes: dict,
    registros_recebidos: list[dict],
    pasta_destino: str | Path | None = None,
    titulo_secao: str = "Oradores",
    prefixo_arquivo: str = "Oradores",
) -> tuple[str | None, str | None]:
    """Gera PNG de alta definição com a lista selecionada do mês."""
    if not registros_recebidos:
        return None, "Não há itens selecionados para exportar."

    destino = Path(pasta_destino) if pasta_destino else EXPORTS_DIR
    destino.mkdir(parents=True, exist_ok=True)

    nome_arquivo = sugerir_nome_arquivo_exportacao(arranjo, reunioes, prefixo_arquivo)
    caminho = destino / nome_arquivo

    margem_h = _px(22)
    margem_v = _px(16)
    largura_col_data = _px(68)
    espaco_colunas = _px(8)
    altura_linha_orador = _px(24)
    altura_linha_tema = _px(22)
    gap_orador_tema = _px(2)
    padding_celula = _px(5)
    padding_cab = _px(8)
    raio_borda = _px(8)

    fonte_reuniao = _carregar_fonte(15)
    fonte_cabecalho = _carregar_fonte(18, negrito=True)
    fonte_orador = _carregar_fonte(22, negrito=True)
    fonte_tema = _carregar_fonte(20)
    fonte_data = _carregar_fonte(20, negrito=True)

    largura_util = LARGURA_IMAGEM - (margem_h * 2)
    largura_conteudo = largura_util - largura_col_data - espaco_colunas - (padding_cab * 2)

    imagem_rascunho = Image.new("RGB", (LARGURA_IMAGEM, 400), COR_FUNDO)
    draw_rascunho = ImageDraw.Draw(imagem_rascunho)
    linhas = _montar_linhas_tabela(
        draw_rascunho,
        registros_recebidos,
        fonte_orador,
        fonte_tema,
        largura_conteudo,
        altura_linha_orador,
        altura_linha_tema,
        padding_celula,
        gap_orador_tema,
    )

    mes = int(arranjo.get("mes_inicio", 1))
    ano = int(arranjo.get("ano", 2026))
    mes_nome = NOMES_MESES[mes] if 1 <= mes <= 12 else str(mes)

    titulo = f"{titulo_secao} - {mes_nome} {ano}"
    linha_anfitria = _formatar_reuniao_cong(
        reunioes.get("host_nome", "Anfitriã"),
        reunioes.get("host_dia", ""),
        reunioes.get("host_horario", ""),
    )
    linha_origem = _formatar_reuniao_cong(
        reunioes.get("ita_nome", "Minha congregação"),
        reunioes.get("ita_dia", ""),
        reunioes.get("ita_horario", ""),
    )

    padding_cabecalho = _px(20)
    gap_titulo_reunioes = _px(12)
    gap_entre_reunioes = _px(6)
    altura_sublinhado = _px(2)
    gap_sublinhado = _px(8)
    altura_cabecalho_tabela = _px(38)
    altura_tabela = sum(linha["altura"] for linha in linhas)

    largura_caixa_cab = LARGURA_IMAGEM - (margem_h * 2)
    x_conteudo_cab = margem_h + padding_cabecalho
    largura_conteudo_cab = largura_caixa_cab - (padding_cabecalho * 2)

    imagem_rascunho_cab = Image.new("RGB", (LARGURA_IMAGEM, 300), COR_FUNDO)
    draw_cab = ImageDraw.Draw(imagem_rascunho_cab)
    fonte_titulo = _ajustar_fonte_titulo(draw_cab, titulo, largura_conteudo_cab)

    y_cab = padding_cabecalho
    x_titulo_cab = _x_texto_centralizado(
        x_conteudo_cab,
        largura_conteudo_cab,
        _largura_texto(draw_cab, titulo, fonte_titulo),
    )
    draw_cab.text((x_titulo_cab, y_cab), titulo, fill=COR_TITULO, font=fonte_titulo)
    bbox_titulo = draw_cab.textbbox((x_titulo_cab, y_cab), titulo, font=fonte_titulo)
    y_cab = bbox_titulo[3] + gap_sublinhado + altura_sublinhado + gap_titulo_reunioes

    x_reuniao1 = _x_texto_centralizado(
        x_conteudo_cab,
        largura_conteudo_cab,
        _largura_texto(draw_cab, linha_anfitria, fonte_reuniao),
    )
    draw_cab.text((x_reuniao1, y_cab), linha_anfitria, fill=COR_REUNIAO, font=fonte_reuniao)
    bbox_reuniao1 = draw_cab.textbbox((x_reuniao1, y_cab), linha_anfitria, font=fonte_reuniao)
    y_cab = bbox_reuniao1[3] + gap_entre_reunioes

    x_reuniao2 = _x_texto_centralizado(
        x_conteudo_cab,
        largura_conteudo_cab,
        _largura_texto(draw_cab, linha_origem, fonte_reuniao),
    )
    draw_cab.text((x_reuniao2, y_cab), linha_origem, fill=COR_REUNIAO, font=fonte_reuniao)
    bbox_reuniao2 = draw_cab.textbbox((x_reuniao2, y_cab), linha_origem, font=fonte_reuniao)
    altura_bloco_cabecalho = bbox_reuniao2[3] + padding_cabecalho

    altura_total = (
        margem_v
        + altura_bloco_cabecalho
        + _px(8)
        + altura_cabecalho_tabela
        + altura_tabela
        + margem_v
    )

    imagem = Image.new("RGB", (LARGURA_IMAGEM, altura_total), COR_FUNDO)
    draw = ImageDraw.Draw(imagem)

    y = margem_v

    _desenhar_retangulo_arredondado(
        draw,
        (margem_h, y, LARGURA_IMAGEM - margem_h, y + altura_bloco_cabecalho),
        raio_borda,
        fill=COR_FAIXA_TITULO,
        outline=COR_BORDA,
        largura=_px(1),
    )

    y_titulo = y + padding_cabecalho
    largura_titulo = _largura_texto(draw, titulo, fonte_titulo)
    x_titulo = _x_texto_centralizado(x_conteudo_cab, largura_conteudo_cab, largura_titulo)
    draw.text((x_titulo, y_titulo), titulo, fill=COR_TITULO, font=fonte_titulo)
    bbox_titulo = draw.textbbox((x_titulo, y_titulo), titulo, font=fonte_titulo)
    y_sublinhado = bbox_titulo[3] + gap_sublinhado
    draw.rectangle(
        (x_titulo, y_sublinhado, x_titulo + largura_titulo, y_sublinhado + altura_sublinhado),
        fill=COR_SUBLINHADO,
    )

    y_reuniao = y_sublinhado + altura_sublinhado + gap_titulo_reunioes
    x_reuniao1 = _x_texto_centralizado(
        x_conteudo_cab,
        largura_conteudo_cab,
        _largura_texto(draw, linha_anfitria, fonte_reuniao),
    )
    draw.text((x_reuniao1, y_reuniao), linha_anfitria, fill=COR_REUNIAO, font=fonte_reuniao)
    bbox_reuniao1 = draw.textbbox((x_reuniao1, y_reuniao), linha_anfitria, font=fonte_reuniao)
    y_reuniao = bbox_reuniao1[3] + gap_entre_reunioes
    x_reuniao2 = _x_texto_centralizado(
        x_conteudo_cab,
        largura_conteudo_cab,
        _largura_texto(draw, linha_origem, fonte_reuniao),
    )
    draw.text((x_reuniao2, y_reuniao), linha_origem, fill=COR_REUNIAO, font=fonte_reuniao)

    y += altura_bloco_cabecalho + _px(8)

    x_data = margem_h
    x_conteudo = x_data + largura_col_data + espaco_colunas
    y_inicio_tabela = y
    y_fim_tabela = y + altura_cabecalho_tabela + altura_tabela

    _desenhar_retangulo_arredondado(
        draw,
        (margem_h, y_inicio_tabela, LARGURA_IMAGEM - margem_h, y_fim_tabela),
        raio_borda,
        outline=COR_BORDA,
        largura=_px(2),
    )
    _desenhar_retangulo_arredondado(
        draw,
        (margem_h, y, LARGURA_IMAGEM - margem_h, y + altura_cabecalho_tabela),
        raio_borda,
        fill=COR_CABECALHO_TABELA,
    )
    draw.rectangle(
        (
            margem_h,
            y + altura_cabecalho_tabela - raio_borda,
            LARGURA_IMAGEM - margem_h,
            y + altura_cabecalho_tabela,
        ),
        fill=COR_CABECALHO_TABELA,
    )

    draw.text((x_data + padding_cab, y + padding_cab), "Data", fill=COR_TEXTO_CABECALHO, font=fonte_cabecalho)
    draw.text(
        (x_conteudo + padding_cab, y + padding_cab),
        "Orador / Tema",
        fill=COR_TEXTO_CABECALHO,
        font=fonte_cabecalho,
    )
    y += altura_cabecalho_tabela

    for indice, linha in enumerate(linhas):
        if indice % 2 == 1:
            draw.rectangle(
                (margem_h + _px(2), y, LARGURA_IMAGEM - margem_h - _px(2), y + linha["altura"]),
                fill=COR_LINHA_ALT,
            )
        draw.text(
            (x_data + padding_cab, y + padding_celula),
            linha["data"],
            fill=COR_DESTAQUE_ESCURO,
            font=fonte_data,
        )

        offset_y = y + padding_celula
        for parte in linha["orador"]:
            draw.text((x_conteudo + padding_cab, offset_y), parte, fill=COR_TEXTO, font=fonte_orador)
            offset_y += altura_linha_orador

        offset_y += gap_orador_tema
        for parte in linha["tema"]:
            draw.text((x_conteudo + padding_cab, offset_y), parte, fill=COR_SECUNDARIO, font=fonte_tema)
            offset_y += altura_linha_tema

        if indice < len(linhas) - 1:
            draw.line(
                (
                    margem_h + _px(6),
                    y + linha["altura"],
                    LARGURA_IMAGEM - margem_h - _px(6),
                    y + linha["altura"],
                ),
                fill=COR_BORDA,
                width=_px(1),
            )
        y += linha["altura"]

    imagem.save(caminho, format="PNG", dpi=(DPI, DPI), optimize=True)
    return str(caminho.resolve()), None


def abrir_pasta_do_arquivo(caminho: str | Path) -> None:
    """Abre a pasta que contém o arquivo exportado."""
    pasta = Path(caminho).resolve().parent
    sistema = platform.system()
    if sistema == "Windows":
        os.startfile(str(pasta))  # noqa: S606
    elif sistema == "Darwin":
        subprocess.run(["open", str(pasta)], check=False)
    else:
        subprocess.run(["xdg-open", str(pasta)], check=False)


def copiar_imagem_para_area_transferencia(caminho: str | Path) -> bool:
    """Copia o PNG para a área de transferência do Windows, como bitmap.

    É o que permite colar a imagem (Ctrl+V) direto na conversa do WhatsApp
    Web/Desktop, já que não existe um jeito programático de anexar arquivo
    num link ``wa.me`` — o formulário de composição não aceita isso. Só
    funciona no Windows (``pywin32``, já uma dependência opcional do projeto);
    nos demais sistemas, ou se algo falhar, devolve False sem levantar exceção
    — quem chamou decide o que fazer (ex: sugerir anexar o arquivo à mão).
    """
    if platform.system() != "Windows":
        return False
    try:
        import win32clipboard  # type: ignore[import-not-found]

        imagem = Image.open(caminho).convert("RGB")
        buffer_bmp = io.BytesIO()
        imagem.save(buffer_bmp, format="BMP")
        # O clipboard do Windows usa CF_DIB: o mesmo BMP, sem os 14 bytes
        # iniciais do BITMAPFILEHEADER (que só existem no arquivo em disco).
        dados_dib = buffer_bmp.getvalue()[14:]

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dados_dib)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:  # noqa: BLE001 — recurso opcional, nunca deve travar o envio
        return False


DIAS_SEMANA_PT = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

COR_CABECALHO_ENVIO = "#0D47A1"


def _formatar_data_extenso(data_str: str) -> str:
    """Converte DD/MM/AAAA em algo como 'domingo, 17 de maio de 2026'."""
    try:
        data = datetime.strptime((data_str or "").strip(), "%d/%m/%Y")
    except ValueError:
        return data_str or "—"
    dia_semana = DIAS_SEMANA_PT[data.weekday()]
    mes_nome = NOMES_MESES[data.month].lower()
    return f"{dia_semana}, {data.day} de {mes_nome} de {data.year}"


def _juntar_com_virgula(a: str | None, b: str | None) -> str:
    a, b = (a or "").strip(), (b or "").strip()
    if a and b:
        return f"{a}, {b}"
    return a or b or "—"


def _juntar_com_traco(a: str | None, b: str | None) -> str:
    a, b = (a or "").strip(), (b or "").strip()
    if a and b:
        return f"{a} - {b}"
    return a or b or "—"


def sugerir_nome_arquivo_designacao_envio(designacao: dict) -> str:
    data_arquivo = (designacao.get("data") or "").replace("/", "-") or "sem-data"
    orador = _sanitizar_nome_arquivo(designacao.get("orador") or "Orador")
    return f"Designacao_{data_arquivo}_{orador}.png"


def gerar_png_designacao_envio(
    designacao: dict,
    pasta_destino: str | Path | None = None,
) -> tuple[str | None, str | None]:
    """
    Gera PNG de uma designação enviada (orador da minha congregação indo apresentar
    discurso em outra congregação), pronto para enviar ao orador via WhatsApp.

    Inclui: data por extenso, orador, tema, congregação de destino, dia/
    horário da reunião, endereço e contato do responsável de lá.
    """
    if not designacao:
        return None, "Designação inválida."

    destino = Path(pasta_destino) if pasta_destino else EXPORTS_DIR
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / sugerir_nome_arquivo_designacao_envio(designacao)

    largura_base = 560
    largura_imagem = largura_base * ESCALA
    margem = _px(24)
    padding_corpo = _px(20)
    altura_cabecalho = _px(64)
    altura_linha = _px(30)
    gap_linha = _px(14)

    campos = [
        ("Data:", _formatar_data_extenso(designacao.get("data", ""))),
        ("Orador:", (designacao.get("orador") or "").strip() or "—"),
        ("Tema:", (designacao.get("tema") or "").strip() or "—"),
        ("Congregação:", (designacao.get("congregacao") or "").strip() or "—"),
        ("Reunião:", _juntar_com_virgula(designacao.get("dia_semana"), designacao.get("horario"))),
        ("Endereço:", (designacao.get("endereco") or "").strip() or "—"),
        ("Contato:", _juntar_com_traco(designacao.get("responsavel"), designacao.get("telefone"))),
    ]

    imagem_rascunho = Image.new("RGB", (largura_imagem, 100), COR_FUNDO)
    draw_rascunho = ImageDraw.Draw(imagem_rascunho)

    fonte_titulo = _carregar_fonte(22, negrito=True)
    fonte_label = _carregar_fonte(16, negrito=True)
    fonte_valor = _carregar_fonte(16)

    largura_label = max(
        _largura_texto(draw_rascunho, rotulo, fonte_label) for rotulo, _ in campos
    )
    x_valor = margem + padding_corpo + int(largura_label) + _px(14)
    largura_valor_util = largura_imagem - x_valor - margem - padding_corpo

    linhas_por_campo = []
    altura_corpo = padding_corpo
    for _rotulo, valor in campos:
        linhas_valor = _quebrar_texto(draw_rascunho, valor, fonte_valor, largura_valor_util)
        linhas_por_campo.append(linhas_valor)
        altura_corpo += max(len(linhas_valor), 1) * altura_linha + gap_linha
    altura_corpo += padding_corpo - gap_linha

    altura_total = altura_cabecalho + altura_corpo

    imagem = Image.new("RGB", (largura_imagem, altura_total), COR_FUNDO)
    draw = ImageDraw.Draw(imagem)

    draw.rectangle((0, 0, largura_imagem, altura_cabecalho), fill=COR_CABECALHO_ENVIO)
    titulo = "DESIGNAÇÃO PARA DISCURSO PÚBLICO"
    largura_titulo = _largura_texto(draw, titulo, fonte_titulo)
    x_titulo = (largura_imagem - largura_titulo) / 2
    y_titulo = (altura_cabecalho - _px(22)) / 2
    draw.text((x_titulo, y_titulo), titulo, fill="#FFFFFF", font=fonte_titulo)

    y = altura_cabecalho + padding_corpo
    for (rotulo, _valor), linhas_valor in zip(campos, linhas_por_campo):
        draw.text((margem + padding_corpo, y), rotulo, fill=COR_DESTAQUE_ESCURO, font=fonte_label)
        y_linha = y
        for linha in linhas_valor:
            draw.text((x_valor, y_linha), linha, fill=COR_TEXTO, font=fonte_valor)
            y_linha += altura_linha
        y += max(len(linhas_valor), 1) * altura_linha + gap_linha

    imagem.save(caminho, format="PNG", dpi=(DPI, DPI), optimize=True)
    return str(caminho.resolve()), None


# ==================== PRÉVIA DO QUADRO DE ANÚNCIOS ====================

COR_FAIXA_TITULO_QUADRO = "#C84040"
COR_FAIXA_SECUNDARIA_QUADRO = "#757070"
COR_BORDA_QUADRO = "#000000"

# Geometria do PDF modelo (em pontos, tabela de 555pt de largura)
_QUADRO_LARGURA_PT = 555
_QUADRO_ALTURA_TITULO = 31
_QUADRO_ALTURA_MES = 23
_QUADRO_ALTURA_DATA = 18
_QUADRO_ALTURAS_CORPO = (31, 30, 31)
_QUADRO_ALTURA_DIVISOR = 16
_QUADRO_ALTURA_RODAPE = 15
_QUADRO_X_VALOR = 63
_QUADRO_X_VALOR_CONG = 112
_QUADRO_X_DIVISAO_DATA = 277


def _texto_centrado(
    draw: ImageDraw.ImageDraw,
    x: int,
    y_topo: int,
    altura: int,
    texto: str,
    fonte,
    fill: str,
    largura_area: int | None = None,
) -> None:
    """Desenha texto centralizado verticalmente pela caixa real dos glifos.

    Com `largura_area`, centraliza também na horizontal a partir de `x`.
    """
    caixa = draw.textbbox((0, 0), texto, font=fonte)
    altura_texto = caixa[3] - caixa[1]
    y = y_topo + (altura - altura_texto) // 2 - caixa[1]
    if largura_area is not None:
        largura_texto = caixa[2] - caixa[0]
        x = int(x + (largura_area - largura_texto) / 2 - caixa[0])
    draw.text((x, y), texto, fill=fill, font=fonte)


def gerar_preview_quadro_mes(
    ano: int,
    mes: int,
    dados: list[dict],
    nome_congregacao: str,
    largura_base: int = 620,
) -> bytes:
    """Prévia PNG de um mês do quadro, com a mesma geometria do PDF modelo.

    `largura_base` controla a resolução: no celular passamos um valor maior
    para o texto ficar nítido quando a imagem é exibida ampliada.
    """
    largura_imagem = largura_base * ESCALA
    margem = _px(16)
    largura_util = largura_imagem - margem * 2
    escala = largura_util / _QUADRO_LARGURA_PT

    def pt(valor: float) -> int:
        return int(valor * escala)

    def fonte_pt(tamanho: float):
        tamanho_px = max(8, int(tamanho * escala))
        for caminho in _carminhos_fonte_sistema(True):
            if os.path.exists(caminho):
                return ImageFont.truetype(caminho, tamanho_px)
        return ImageFont.load_default()

    imagem_rascunho = Image.new("RGB", (largura_imagem, 10), COR_FUNDO)
    draw_rascunho = ImageDraw.Draw(imagem_rascunho)

    def fonte_ajustada(texto: str, largura_max: int, tamanho_inicial: int = 14, minimo: int = 9):
        tamanho = tamanho_inicial
        fonte = fonte_pt(tamanho)
        while tamanho > minimo and _largura_texto(draw_rascunho, texto, fonte) > largura_max:
            tamanho -= 1
            fonte = fonte_pt(tamanho)
        return fonte

    altura_total = (
        _QUADRO_ALTURA_TITULO
        + _QUADRO_ALTURA_MES
        + len(dados) * (_QUADRO_ALTURA_DATA + sum(_QUADRO_ALTURAS_CORPO))
        + max(len(dados) - 1, 0) * _QUADRO_ALTURA_DIVISOR
        + _QUADRO_ALTURA_RODAPE
        + (len(dados) + 1) * 2
    )
    altura_imagem = pt(altura_total) + margem * 2

    imagem = Image.new("RGB", (largura_imagem, altura_imagem), COR_FUNDO)
    draw = ImageDraw.Draw(imagem)

    x0 = margem
    x1 = margem + pt(_QUADRO_LARGURA_PT)
    espessura = max(2, pt(1))
    y = margem

    def linha_horizontal(y_pos: int) -> None:
        draw.line((x0, y_pos, x1, y_pos), fill=COR_BORDA_QUADRO, width=espessura)

    # Título
    altura = pt(_QUADRO_ALTURA_TITULO)
    draw.rectangle((x0, y, x1, y + altura), fill=COR_FAIXA_TITULO_QUADRO)
    titulo = f"Conferência Pública - {nome_congregacao}"
    _texto_centrado(
        draw, x0, y, altura, titulo,
        fonte_ajustada(titulo, pt(_QUADRO_LARGURA_PT - 8), 24),
        "#000000", largura_area=x1 - x0,
    )
    y += altura
    linha_horizontal(y)

    # Mês/Ano
    altura = pt(_QUADRO_ALTURA_MES)
    draw.rectangle((x0, y, x1, y + altura), fill=COR_FAIXA_SECUNDARIA_QUADRO)
    _texto_centrado(
        draw, x0, y, altura, f"{NOMES_MESES[mes]}/{ano}", fonte_pt(18),
        "#000000", largura_area=x1 - x0,
    )
    y += altura
    draw.rectangle((x0, y, x1, y + pt(2)), fill=COR_FAIXA_SECUNDARIA_QUADRO)
    linha_horizontal(y)
    y += pt(2)
    linha_horizontal(y)

    for indice, item in enumerate(dados):
        # Linha da data + presidente
        altura = pt(_QUADRO_ALTURA_DATA)
        x_divisao = x0 + pt(_QUADRO_X_DIVISAO_DATA)
        draw.rectangle((x0, y, x_divisao, y + altura), fill=COR_FAIXA_TITULO_QUADRO)
        draw.rectangle((x_divisao, y, x1, y + altura), fill=COR_FAIXA_SECUNDARIA_QUADRO)
        draw.line((x_divisao, y, x_divisao, y + altura), fill=COR_BORDA_QUADRO, width=espessura)

        rotulo_data = f"SÁBADO, {item['data'].day} DE {NOMES_MESES[mes].upper()}"
        _texto_centrado(
            draw, x0, y, altura, rotulo_data,
            fonte_ajustada(rotulo_data, pt(_QUADRO_X_DIVISAO_DATA - 6), 14),
            "#000000", largura_area=x_divisao - x0,
        )
        presidente = item["presidente"]
        texto_presidente = (
            f"PRESIDENTE:      {presidente}" if presidente and presidente != "—" else "PRESIDENTE:"
        )
        _texto_centrado(
            draw, x_divisao + pt(21), y, altura, texto_presidente,
            fonte_ajustada(texto_presidente, x1 - x_divisao - pt(23), 14),
            "#000000",
        )
        y += altura
        linha_horizontal(y)

        # Linhas do corpo
        campos = [
            ("Orador:", item["orador"], _QUADRO_X_VALOR),
            ("Tema:", item["tema"], _QUADRO_X_VALOR),
            ("Congregação:", item["congregacao"], _QUADRO_X_VALOR_CONG),
        ]
        for altura_pt, (rotulo, valor, x_valor_pt) in zip(_QUADRO_ALTURAS_CORPO, campos):
            altura = pt(altura_pt)
            _texto_centrado(draw, x0 + pt(2), y, altura, rotulo, fonte_pt(14), "#000000")
            _texto_centrado(
                draw, x0 + pt(x_valor_pt), y, altura, valor,
                fonte_ajustada(valor, x1 - x0 - pt(x_valor_pt) - pt(4), 14),
                "#000000",
            )
            y += altura
            linha_horizontal(y)

        if indice < len(dados) - 1:
            altura = pt(_QUADRO_ALTURA_DIVISOR)
            draw.rectangle((x0, y, x1, y + altura + pt(2)), fill=COR_FAIXA_SECUNDARIA_QUADRO)
            y += altura
            linha_horizontal(y)
            y += pt(2)
            linha_horizontal(y)

    # Linha branca final + linha dupla de fechamento + borda externa
    y += pt(_QUADRO_ALTURA_RODAPE)
    linha_horizontal(y)
    y += pt(2)
    draw.rectangle((x0, margem, x1, y), outline=COR_BORDA_QUADRO, width=espessura)

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", dpi=(DPI, DPI), optimize=True)
    return buffer.getvalue()


def gerar_link_whatsapp(telefone: str, mensagem: str) -> str:
    """Gera link para WhatsApp Web/API com mensagem pré-preenchida."""
    import urllib.parse
    # Remove formatação do telefone
    tel_limpo = re.sub(r"\D", "", telefone)
    if not tel_limpo.startswith("55"):
        tel_limpo = "55" + tel_limpo
    msg_codificada = urllib.parse.quote(mensagem)
    return f"https://wa.me/{tel_limpo}?text={msg_codificada}"
