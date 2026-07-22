"""
Gestão de Arranjo — aplicativo desktop em Flet.

Execute com: python main.py
"""

from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable
import webbrowser

import flet as ft
import pandas as pd

from database import (
    adicionar_ano_coluna,
    adicionar_ano_planejamento,
    adicionar_orador_arranjo,
    adicionar_tipo_evento,
    atualizar_orador_arranjo,
    carregar_arranjo,
    carregar_arranjos_por_ano,
    carregar_dataframe_temas,
    carregar_oradores_arranjo,
    carregar_tema,
    carregar_presidentes_por_ano,
    carregar_recebidos_por_ano,
    carregar_temas_de_orador,
    contar_designacoes_por_mes,
    create_tables,
    definir_visibilidade_ano_coluna,
    excluir_ano_coluna,
    excluir_arranjo,
    excluir_data_especial,
    excluir_orador,
    excluir_presidente,
    excluir_presidente_cadastro,
    excluir_tema,
    excluir_tipo_evento,
    exportar_backup,
    garantir_configuracao_inicial,
    get_connection,
    importar_temas_pdf,
    importar_temas_planilha,
    listar_anos_arranjos,
    listar_anos_colunas,
    listar_anos_planejamento,
    listar_datas_especiais_por_ano,
    carregar_todas_designacoes_presidente,
    listar_presidentes_cadastro,
    listar_tipos_evento,
    remover_orador_arranjo,
    restaurar_backup,
    salvar_arranjo,
    salvar_data_especial,
    salvar_orador,
    salvar_ordem_presidentes,
    salvar_presidente,
    salvar_presidente_cadastro,
    salvar_tema,
)
from pdf_envio import gerar_pdf_envio
from planilha_dados import gerar_planilha_modelo, importar_planilha_dados
from pdf_quadro import (
    PARES_MESES as PARES_MESES_QUADRO,
    abrir_arquivo,
    par_meses_do_mes as par_meses_do_mes_quadro,
    carregar_dados_mes as carregar_dados_mes_quadro,
    gerar_quadro_anuncios,
)
from png_oradores import (
    abrir_pasta_do_arquivo,
    gerar_link_whatsapp,
    gerar_png_designacao_envio,
    gerar_png_oradores,
    gerar_preview_quadro_mes,
)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

LARGURA_BARRA_LATERAL = 192
ICON_SIZE_MENU = 18

# Versão exibida no app. O release.sh mantém este valor igual à tag/pyproject.
VERSAO_APP = "1.0.16"

# Identidade visual — "Meia-noite teal": azul profundo com acento verde-água
COR_DESTAQUE = "#14B8A6"
COR_DESTAQUE_CLARA = "#2DD4BF"
COR_DESTAQUE_SUAVE = "#5EEAD4"

FUNDO_APP = "#0E1524"
FUNDO_SIDEBAR = "#121A2E"
FUNDO_CARD = "#16223B"
FUNDO_ELEVADO = "#1C2A47"

TEXTO_PRIMARIO = "#E7ECF5"
TEXTO_SECUNDARIO = "#7C89A6"
BORDA_SUAVE = "#24304E"

COR_SUCESSO = "#34D399"
COR_AVISO = "#FBBF24"
COR_ERRO = "#F87171"

SECOES = [
    {"nome": "Início", "icone": ft.Icons.HOME},
    {"nome": "Programação", "icone": ft.Icons.CALENDAR_MONTH},
    {"nome": "Oradores", "icone": ft.Icons.PEOPLE},
    {"nome": "Congregações", "icone": ft.Icons.LOCATION_CITY},
    {"nome": "Temas", "icone": ft.Icons.MENU_BOOK},
    {"nome": "Quadro de Anúncios", "icone": ft.Icons.CAMPAIGN},
    {"nome": "Ajustes", "icone": ft.Icons.SETTINGS},
]

SQL_ORADORES = """
    SELECT o.id,
           o.nome,
           o.telefone,
           o.categoria,
           COALESCE((
               SELECT GROUP_CONCAT(ot.tema_nr, ', ')
               FROM orador_temas ot
               WHERE ot.orador_id = o.id
           ), '') AS temas,
           o.observacoes,
           o.congregacao_id,
           COALESCE(c.nome, '—') AS congregacao
    FROM oradores o
    LEFT JOIN congregacoes c ON o.congregacao_id = c.id
    WHERE COALESCE(o.ativo, 1) = 1
    ORDER BY o.categoria, o.nome
"""

SQL_CONGREGACOES = """
    SELECT id, nome, responsavel, telefone, endereco, dia_semana, horario, observacoes
    FROM congregacoes
    ORDER BY nome
"""

ANO_PADRAO_ARRANJOS = 2026
LARGURA_DIALOG_MES = 1040
ALTURA_CONTEUDO_DIALOG_MES = 480
LARGURA_COL_DATA_MES = 76
LARGURA_COL_ORADOR_MES = 150
LARGURA_COL_ACOES_MES = 80
ESPACO_COLUNAS_MES = 8
QUANTIDADE_DATAS_SUGERIDAS = 5

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

MESES_ANO = [(mes, NOMES_MESES[mes]) for mes in range(1, 13)]


COLUNAS_NUMERICAS = {"id", "nr", "ano"}

ROTULOS_COLUNAS = {
    "nome": "Nome",
    "responsavel": "Responsável",
    "telefone": "Telefone",
    "categoria": "Categoria",
    "temas": "Temas que pode fazer",
    "endereco": "Endereço",
    "dia_semana": "Dia",
    "horario": "Horário",
    "observacoes": "Observações",
    "restricoes": "Observações/Restrições",
    "congregacao": "Congregação",
}

CONFIG_TABELA_TEMAS = {
    "coluna_id": "nr",
    "colunas_ocultas": ["data_limite_uso", "restrito", "tem_observacao", "ultimo_uso_chave"],
    "colunas_acoes_separadas": True,
    "rotulos_colunas": {
        "nr": "Nº",
        "titulo": "Tema",
        "assunto": "Assunto",
        "ultimo_uso": "Último uso",
    },
    "destacar_observacao": True,
    "column_spacing": 14,
    "horizontal_margin": 12,
    "heading_row_height": 44,
    "data_row_min_height": 40,
    "data_row_max_height": 72,
    "cor_alternada": 0.025,
}

CONFIG_TABELA_CONGREGACOES = {
    "colunas_ocultas": ["id"],
    "colunas_acoes_separadas": True,
    "rotulos_colunas": {"nome": "Congregação"},
    "column_spacing": 14,
    "horizontal_margin": 10,
    "heading_row_height": 44,
    "data_row_min_height": 40,
    "data_row_max_height": 64,
    "cor_alternada": 0.025,
}

CONFIG_TABELA_ORADORES = {
    "colunas_ocultas": ["id", "congregacao_id"],
    "colunas_acoes_separadas": True,
    "column_spacing": 16,
    "horizontal_margin": 12,
    "heading_row_height": 46,
    "data_row_min_height": 44,
    "data_row_max_height": 72,
    "cor_alternada": 0.03,
    "rotulo_coluna_acoes": "Ações",
}


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def carregar_dados(query: str) -> pd.DataFrame:
    """Executa uma consulta SQL e retorna o resultado como DataFrame."""
    conn = get_connection()
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def executar_escrita(query: str, params: tuple) -> None:
    """Executa INSERT/UPDATE/DELETE com commit."""
    conn = get_connection()
    try:
        conn.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def inserir_orador(
    nome: str,
    telefone: str,
    categoria: str,
    congregacao_id: int | None,
    observacoes: str = "",
) -> int:
    """Insere um orador e retorna o ID gerado."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO oradores (nome, telefone, categoria, congregacao_id, observacoes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nome, telefone, categoria, congregacao_id, observacoes),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def garantir_tabelas() -> None:
    """Garante que as tabelas do banco existam (incluindo designacoes)."""
    conn = get_connection()
    try:
        create_tables(conn)
        garantir_configuracao_inicial(conn)
        # O app é distribuído vazio: os temas são preenchidos pelo próprio
        # usuário (Temas → Importar S-99/S-99a). Não semeamos nada aqui.
    finally:
        conn.close()


def carregar_configuracao() -> dict:
    """Carrega as configurações da congregação principal (linha única)."""
    df = carregar_dados(
        "SELECT nome_congregacao, endereco, cidade, cep, coordenador_discursos, "
        "telefone_coordenador, dia_reuniao, horario_reuniao, circuito "
        "FROM configuracoes WHERE id = 1"
    )
    if df.empty:
        return {
            "nome_congregacao": "",
            "endereco": "",
            "cidade": "",
            "cep": "",
            "coordenador_discursos": "",
            "telefone_coordenador": "",
            "dia_reuniao": "",
            "horario_reuniao": "",
            "circuito": "",
        }
    row = df.iloc[0]
    return {
        "nome_congregacao": row["nome_congregacao"] or "",
        "endereco": row["endereco"] or "",
        "cidade": row.get("cidade", "") or "",
        "cep": row.get("cep", "") or "",
        "coordenador_discursos": row["coordenador_discursos"] or "",
        "telefone_coordenador": row["telefone_coordenador"] or "",
        "dia_reuniao": row["dia_reuniao"] or "",
        "horario_reuniao": row["horario_reuniao"] or "",
        "circuito": row["circuito"] or "",
    }


def salvar_configuracao(dados: dict) -> None:
    """Salva ou atualiza as configurações da congregação principal."""
    nome_antigo = carregar_configuracao()["nome_congregacao"].strip()
    nome_novo = (dados.get("nome_congregacao") or "").strip()

    executar_escrita(
        """
        INSERT INTO configuracoes (
            id, nome_congregacao, endereco, cidade, cep, coordenador_discursos,
            telefone_coordenador, dia_reuniao, horario_reuniao, circuito
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome_congregacao = excluded.nome_congregacao,
            endereco = excluded.endereco,
            cidade = excluded.cidade,
            cep = excluded.cep,
            coordenador_discursos = excluded.coordenador_discursos,
            telefone_coordenador = excluded.telefone_coordenador,
            dia_reuniao = excluded.dia_reuniao,
            horario_reuniao = excluded.horario_reuniao,
            circuito = excluded.circuito
        """,
        (
            nome_novo,
            dados["endereco"],
            dados.get("cidade", ""),
            dados.get("cep", ""),
            dados["coordenador_discursos"],
            dados["telefone_coordenador"],
            dados["dia_reuniao"],
            dados["horario_reuniao"],
            dados["circuito"],
        ),
    )

    if not nome_novo:
        return

    # Mantém a própria congregação cadastrada em congregacoes (usada nos
    # filtros "Minha congregação" e nas sugestões de data).
    conn = get_connection()
    try:
        existe_novo = conn.execute(
            "SELECT id FROM congregacoes WHERE nome = ?", (nome_novo,)
        ).fetchone()
        if not existe_novo and nome_antigo and nome_antigo != nome_novo:
            conn.execute(
                "UPDATE congregacoes SET nome = ? WHERE nome = ?",
                (nome_novo, nome_antigo),
            )
            existe_novo = conn.execute(
                "SELECT id FROM congregacoes WHERE nome = ?", (nome_novo,)
            ).fetchone()
        if existe_novo:
            conn.execute(
                """
                UPDATE congregacoes
                SET responsavel = ?, telefone = ?, endereco = ?,
                    dia_semana = ?, horario = ?
                WHERE nome = ?
                """,
                (
                    dados["coordenador_discursos"],
                    dados["telefone_coordenador"],
                    dados["endereco"],
                    dados["dia_reuniao"],
                    dados["horario_reuniao"],
                    nome_novo,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO congregacoes (
                    nome, responsavel, telefone, endereco, dia_semana, horario, observacoes
                ) VALUES (?, ?, ?, ?, ?, ?, '')
                """,
                (
                    nome_novo,
                    dados["coordenador_discursos"],
                    dados["telefone_coordenador"],
                    dados["endereco"],
                    dados["dia_reuniao"],
                    dados["horario_reuniao"],
                ),
            )
        conn.commit()
    finally:
        conn.close()


def carregar_congregacoes_opcoes() -> list[ft.dropdown.Option]:
    """Lista congregações para uso em formulários."""
    df = carregar_dados("SELECT id, nome FROM congregacoes ORDER BY nome")
    return [ft.dropdown.Option(key=str(row.id), text=row.nome) for row in df.itertuples()]


def obter_id_minha_congregacao() -> str | None:
    """Retorna o ID da congregação definida em Minha Congregação."""
    nome = carregar_configuracao()["nome_congregacao"].strip()
    if not nome:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM congregacoes WHERE nome = ?", (nome,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return str(int(row[0]))


def carregar_oradores_opcoes() -> list[ft.dropdown.Option]:
    """Lista oradores para comboboxes de designação."""
    df = carregar_dados("SELECT id, nome FROM oradores WHERE COALESCE(ativo, 1) = 1 ORDER BY nome")
    return [ft.dropdown.Option(key=str(row.id), text=row.nome) for row in df.itertuples()]


def carregar_temas_opcoes(incluir_sem_tema: bool = False) -> list[ft.dropdown.Option]:
    """Lista temas para combobox de designação."""
    df = carregar_dados("SELECT nr, titulo FROM temas ORDER BY nr")
    opcoes = [
        ft.dropdown.Option(
            key=str(row.nr),
            text=row.titulo if row.titulo.startswith(f"{row.nr}") else f"{row.nr} - {row.titulo}",
        )
        for row in df.itertuples()
    ]
    if incluir_sem_tema:
        return [ft.dropdown.Option(key="", text="Reunião Especial / Sem tema"), *opcoes]
    return opcoes


NOMES_ESPECIAIS_ARRANJO = {
    "Reunião Especial",
    "Visita do Superintendente",
    "Congresso",
    "Sem designação",
    "Arranjo Local",
}


def _formatar_data_exibicao(data: str | None) -> str:
    """Exibe data DD/MM/AAAA ou DD/MM."""
    if not data:
        return "—"
    texto = data.strip()
    if len(texto) >= 10:
        return f"{texto[0:2]}/{texto[3:5]}/{texto[6:10]}"
    return texto


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


def _obter_reunioes_dialog(arranjo: dict) -> dict:
    """Busca dia e horário de reunião na tabela congregacoes (anfitriã + minha congregação)."""
    host_nome = (arranjo.get("congregacao") or "").strip()
    host_dia = (arranjo.get("dia_semana") or "").strip()
    host_horario = (arranjo.get("horario") or "").strip()

    host_id = arranjo.get("congregacao_host_id")
    if host_id:
        cong_host = carregar_congregacao(int(host_id))
        if cong_host:
            host_nome = (cong_host.get("nome") or host_nome).strip()
            if cong_host.get("dia_semana"):
                host_dia = cong_host["dia_semana"].strip()
            if cong_host.get("horario"):
                host_horario = cong_host["horario"].strip()

    ita_nome = carregar_configuracao()["nome_congregacao"].strip() or "Minha congregação"
    ita_dia = ""
    ita_horario = ""
    ita_id = obter_id_minha_congregacao()
    if ita_id:
        cong_ita = carregar_congregacao(int(ita_id))
        if cong_ita:
            ita_nome = (cong_ita.get("nome") or ita_nome).strip()
            ita_dia = (cong_ita.get("dia_semana") or "").strip()
            ita_horario = (cong_ita.get("horario") or "").strip()

    if not ita_dia or not ita_horario:
        config = carregar_configuracao()
        ita_dia = ita_dia or (config.get("dia_reuniao") or "").strip()
        ita_horario = ita_horario or (config.get("horario_reuniao") or "").strip()

    return {
        "host_nome": host_nome or "Anfitriã",
        "host_dia": host_dia,
        "host_horario": host_horario,
        "ita_nome": ita_nome,
        "ita_dia": ita_dia,
        "ita_horario": ita_horario,
    }


def _formatar_linha_reunioes(reunioes: dict) -> str:
    """Formata linha de reuniões para o topo do dialog."""
    host = f"Reunião {reunioes['host_nome']}: {reunioes['host_dia']} {reunioes['host_horario']}".strip()
    ita = f"Reunião {reunioes['ita_nome']}: {reunioes['ita_dia']} {reunioes['ita_horario']}".strip()
    return f"{host}  |  {ita}"


def _rotulo_dia_congregacao(nome: str, dia: str, horario: str) -> str:
    weekday = _dia_semana_para_weekday(dia)
    if weekday is None:
        return nome
    rotulo = f"{nome} — {_rotulo_weekday(weekday)}"
    if horario:
        rotulo += f" {horario}"
    return rotulo


def _sugerir_datas_arranjo(
    arranjo: dict,
    tipo: str,
    registros: list[dict],
    quantidade: int = QUANTIDADE_DATAS_SUGERIDAS,
    orador_id: int | None = None,
) -> list[dict]:
    """Sugere datas com base nos dias de reunião da anfitriã e da minha congregação."""
    _ = orador_id
    ano = int(arranjo.get("ano", ANO_PADRAO_ARRANJOS))
    mes = int(arranjo.get("mes_inicio", 1))
    ocupadas = {
        data_norm
        for registro in registros
        if registro.get("tipo") == tipo
        for data_norm in [_normalizar_data_arranjo(registro.get("data"))]
        if data_norm
    }

    reunioes = _obter_reunioes_dialog(arranjo)
    host_nome = reunioes["host_nome"]
    host_dia = reunioes["host_dia"]
    host_horario = reunioes["host_horario"]
    ita_nome = reunioes["ita_nome"]
    ita_dia = reunioes["ita_dia"]
    ita_horario = reunioes["ita_horario"]

    weekday_padrao = _weekday_mais_usado(registros, tipo)
    host_wd = _dia_semana_para_weekday(host_dia)
    ita_wd = _dia_semana_para_weekday(ita_dia)

    candidatos: list[tuple[int, str]] = []
    if tipo == "recebido" and host_wd == 6:
        candidatos.append((5, f"Sábado (véspera — {host_nome})"))
    if host_wd is not None:
        candidatos.append(
            (host_wd, _rotulo_dia_congregacao(host_nome, host_dia, host_horario))
        )
    if ita_wd is not None:
        candidatos.append(
            (ita_wd, _rotulo_dia_congregacao(ita_nome, ita_dia, ita_horario))
        )
    if weekday_padrao is not None:
        usados = {wd for wd, _ in candidatos}
        if weekday_padrao not in usados:
            candidatos.append((weekday_padrao, "Padrão do mês"))

    vistos: set[int] = set()
    sugestoes: list[dict] = []
    for weekday, rotulo_base in candidatos:
        if weekday in vistos:
            continue
        vistos.add(weekday)
        for data_ref in _datas_por_weekday_no_mes(ano, mes, weekday):
            data_txt = _formatar_data_arranjo(data_ref)
            if data_txt in ocupadas:
                continue
            sugestoes.append(
                {
                    "data": data_txt,
                    "rotulo": f"{data_txt[0:5]} — {rotulo_base}",
                    "weekday": weekday,
                }
            )

    sugestoes.sort(key=lambda item: _parse_data_arranjo(item["data"]) or date.max)
    return sugestoes[:quantidade]


def _rotulo_tema_orador_arranjo(registro: dict) -> str:
    """Formata o tema exibido em uma linha de orador/designação."""
    nome = (registro.get("orador_nome") or "").strip()
    if nome in NOMES_ESPECIAIS_ARRANJO:
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


def carregar_oradores_com_congregacao_opcoes(
    congregacao_id: int | None = None,
) -> list[ft.dropdown.Option]:
    """Lista oradores com congregação para seletores de arranjo."""
    query = """
        SELECT o.id, o.nome, COALESCE(c.nome, '') AS congregacao
        FROM oradores o
        LEFT JOIN congregacoes c ON o.congregacao_id = c.id
        WHERE COALESCE(o.ativo, 1) = 1
    """
    params: list = []
    if congregacao_id is not None:
        query += " AND o.congregacao_id = ?"
        params.append(congregacao_id)
    query += " ORDER BY o.nome"
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params or None)
    finally:
        conn.close()
    opcoes = []
    for row in df.itertuples():
        texto = row.nome
        if row.congregacao:
            texto = f"{row.nome} — {row.congregacao}"
        opcoes.append(ft.dropdown.Option(key=str(row.id), text=texto))
    return opcoes


def carregar_congregacao(congregacao_id: int) -> dict | None:
    """Carrega uma congregação pelo ID para edição."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT id, nome, responsavel, telefone, endereco, dia_semana, horario, observacoes "
            "FROM congregacoes WHERE id = ?",
            conn,
            params=(congregacao_id,),
        )
    finally:
        conn.close()
    if df.empty:
        return None
    row = df.iloc[0]
    return {
        "id": int(row["id"]),
        "nome": row["nome"] or "",
        "responsavel": row["responsavel"] or "",
        "telefone": row["telefone"] or "",
        "endereco": row["endereco"] or "",
        "dia_semana": row["dia_semana"] or "",
        "horario": row["horario"] or "",
        "observacoes": row["observacoes"] or "",
    }


def carregar_orador(orador_id: int) -> dict | None:
    """Carrega um orador pelo ID para edição."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT id, nome, telefone, categoria, congregacao_id, observacoes "
            "FROM oradores WHERE id = ?",
            conn,
            params=(orador_id,),
        )
    finally:
        conn.close()
    if df.empty:
        return None
    row = df.iloc[0]
    return {
        "id": int(row["id"]),
        "nome": row["nome"] or "",
        "telefone": row["telefone"] or "",
        "categoria": row["categoria"] or "Ancião",
        "congregacao_id": str(row["congregacao_id"]) if pd.notna(row["congregacao_id"]) else None,
        "observacoes": row["observacoes"] or "",
        "temas_nr": carregar_temas_de_orador(int(row["id"])),
    }


# ---------------------------------------------------------------------------
# Utilitários de dados
# ---------------------------------------------------------------------------

def formatar_valor(valor) -> str:
    """Converte um valor de célula para texto exibível."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor)


def filtrar_dataframe(df: pd.DataFrame, termo: str, colunas: list[str]) -> pd.DataFrame:
    """Filtra o DataFrame pelas colunas informadas."""
    termo = termo.strip().lower()
    if not termo:
        return df.copy()

    mascara = pd.Series(False, index=df.index)
    for coluna in colunas:
        if coluna in df.columns:
            mascara |= (
                df[coluna]
                .astype(str)
                .str.lower()
                .str.contains(termo, na=False)
            )
    return df[mascara].copy()


def alinhamento_celula(nome_coluna: str) -> ft.TextAlign:
    """Define alinhamento da célula conforme o tipo de dado."""
    if nome_coluna in COLUNAS_NUMERICAS:
        return ft.TextAlign.RIGHT
    return ft.TextAlign.LEFT


# ---------------------------------------------------------------------------
# Tema e componentes visuais reutilizáveis
# ---------------------------------------------------------------------------

def _sombra_card(intensidade: float = 0.35) -> ft.BoxShadow:
    """Sombra suave para cards no modo escuro."""
    return ft.BoxShadow(
        blur_radius=16,
        spread_radius=0,
        color=ft.Colors.with_opacity(intensidade, "#000000"),
        offset=ft.Offset(0, 4),
    )


def _estilo_campo_busca() -> dict:
    """Estilo compartilhado dos campos de busca."""
    return {
        "border_radius": 10,
        "height": 44,
        "content_padding": ft.Padding.symmetric(horizontal=12),
        "bgcolor": FUNDO_ELEVADO,
        "border_color": BORDA_SUAVE,
        "focused_border_color": COR_DESTAQUE,
        "cursor_color": COR_DESTAQUE,
        "color": TEXTO_PRIMARIO,
    }


def aplicar_tema(page: ft.Page) -> None:
    """Aplica o tema "Meia-noite teal" (azul profundo com acento verde-água)."""
    esquema = ft.ColorScheme(
        primary=COR_DESTAQUE,
        on_primary="#04342C",
        primary_container="#0F3D3A",
        on_primary_container=COR_DESTAQUE_SUAVE,
        secondary=COR_DESTAQUE_CLARA,
        on_secondary="#04342C",
        surface=FUNDO_APP,
        on_surface=TEXTO_PRIMARIO,
        on_surface_variant=TEXTO_SECUNDARIO,
        surface_container_lowest=FUNDO_APP,
        surface_container_low=FUNDO_SIDEBAR,
        surface_container=FUNDO_CARD,
        surface_container_high=FUNDO_ELEVADO,
        surface_container_highest="#233250",
        outline=BORDA_SUAVE,
        outline_variant="#1E2942",
        error=COR_ERRO,
    )
    tema = ft.Theme(color_scheme=esquema, use_material3=True)
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = tema
    page.dark_theme = tema
    page.bgcolor = FUNDO_APP


def criar_secao_titulo(texto: str) -> ft.Text:
    """Subtítulo de seção usado em todas as telas."""
    return ft.Text(texto, size=16, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO)


def criar_cabecalho_tela(titulo: str, subtitulo: str = "") -> ft.Column:
    """Cabeçalho padronizado de cada tela."""
    controles = [
        ft.Text(titulo, size=28, weight=ft.FontWeight.BOLD, color=TEXTO_PRIMARIO),
    ]
    if subtitulo:
        controles.append(
            ft.Text(subtitulo, size=14, color=TEXTO_SECUNDARIO)
        )
    return ft.Column(controles, spacing=4)


def criar_painel_informativo(titulo: str, mensagem: str, icone=ft.Icons.INFO_OUTLINE) -> ft.Container:
    """Painel de destaque com o mesmo estilo do Dashboard."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icone, color=COR_DESTAQUE, size=22),
                        ft.Text(titulo, size=16, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
                    ],
                    spacing=10,
                ),
                ft.Text(mensagem, size=14, color=TEXTO_SECUNDARIO),
            ],
            spacing=8,
        ),
        padding=24,
        bgcolor=FUNDO_ELEVADO,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(0.25),
    )


def _rotulo_coluna(nome: str, config: dict | None = None) -> str:
    """Retorna rótulo amigável da coluna, se existir."""
    if config:
        rotulos = config.get("rotulos_colunas", {})
        if nome in rotulos:
            return rotulos[nome]
    return ROTULOS_COLUNAS.get(nome, str(nome))


def obs_tem_qualquer_tema(observacoes: str) -> bool:
    """True se as observações marcam que o orador pode fazer qualquer tema."""
    return bool(observacoes and "qualquer tema" in observacoes.lower())


def obs_sem_qualquer_tema(observacoes: str) -> str:
    """Devolve as observações sem o marcador 'qualquer tema' (mantém o resto)."""
    texto = re.sub(r"\bqualquer\s+tema\b", "", observacoes or "", flags=re.IGNORECASE)
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto.strip(" •·-|,;\n\t")


def obs_definir_qualquer_tema(observacoes: str, marcado: bool) -> str:
    """Aplica ou remove o marcador 'qualquer tema' nas observações."""
    base = obs_sem_qualquer_tema(observacoes)
    if not marcado:
        return base
    return f"{base} • Qualquer tema" if base else "Qualquer tema"


def formatar_temas_orador(temas: str, observacoes: str) -> str:
    """Formata a coluna de temas para exibição legível."""
    if obs_tem_qualquer_tema(observacoes):
        return "Qualquer tema"
    if temas and str(temas).strip():
        return str(temas).strip()
    return "—"


def criar_tabela(
    df: pd.DataFrame,
    on_editar: Callable[[int], None] | None = None,
    on_excluir: Callable[[int], None] | None = None,
    coluna_id: str = "id",
    config: dict | None = None,
) -> ft.DataTable:
    """Monta ft.DataTable com linhas alternadas e alinhamento adequado."""
    config = config or {}
    coluna_id = config.get("coluna_id", coluna_id)
    colunas_ocultas = set(config.get("colunas_ocultas", []))
    cor_alternada = config.get("cor_alternada", 0.04)
    acoes_separadas = config.get("colunas_acoes_separadas", False)
    habilitar_selecao = config.get("habilitar_selecao", False)
    estado_selecao = config.get("estado_selecao")

    colunas_exibir = [c for c in df.columns if c not in colunas_ocultas]

    rotulo_acoes = config.get("rotulo_coluna_acoes", "Ações")

    colunas = []
    if habilitar_selecao:
        colunas.append(
            ft.DataColumn(
                ft.Text("Selecionar", weight=ft.FontWeight.W_600, size=12, color=TEXTO_PRIMARIO),
                numeric=False,
            )
        )
    colunas.extend(
            ft.DataColumn(
                ft.Text(
                    _rotulo_coluna(nome, config),
                    weight=ft.FontWeight.W_600,
                    text_align=alinhamento_celula(nome),
                    size=12,
                    color=TEXTO_PRIMARIO,
                )
            )
        for nome in colunas_exibir
    )
    if coluna_id in df.columns:
        if acoes_separadas:
            if on_editar:
                colunas.append(
                    ft.DataColumn(
                        ft.Text("Editar", weight=ft.FontWeight.W_600, size=12, color=TEXTO_PRIMARIO)
                    )
                )
            if on_excluir:
                colunas.append(
                    ft.DataColumn(
                        ft.Text("Excluir", weight=ft.FontWeight.W_600, size=12, color=TEXTO_PRIMARIO)
                    )
                )
        elif on_editar:
            colunas.append(
                ft.DataColumn(
                    ft.Text(rotulo_acoes, weight=ft.FontWeight.W_600, size=12, color=TEXTO_PRIMARIO)
                )
            )

    linhas = []
    for indice, linha in enumerate(df.itertuples(index=False, name=None)):
        mapa = dict(zip(df.columns, linha))
        if config.get("destacar_observacao") and int(mapa.get("tem_observacao", 0) or 0) == 1:
            cor_linha = ft.Colors.with_opacity(0.18, COR_DESTAQUE)
        elif config.get("destacar_restrito") and int(mapa.get("restrito", 0) or 0) == 1:
            cor_linha = ft.Colors.with_opacity(0.14, COR_AVISO)
        elif indice % 2 == 1:
            cor_linha = ft.Colors.with_opacity(cor_alternada, FUNDO_ELEVADO)
        else:
            cor_linha = None
        celulas = []
        registro_id = int(mapa[coluna_id]) if coluna_id in df.columns else None

        if habilitar_selecao and registro_id is not None and estado_selecao is not None:

            def alternar_selecao(e, rid=registro_id):
                if e.control.value:
                    estado_selecao["ids"].add(rid)
                else:
                    estado_selecao["ids"].discard(rid)

            celulas.append(
                ft.DataCell(
                    ft.Checkbox(
                        value=registro_id in estado_selecao["ids"],
                        on_change=alternar_selecao,
                    )
                )
            )

        for nome in colunas_exibir:
            valor = mapa[nome]
            if nome == "temas":
                texto = formatar_temas_orador(
                    formatar_valor(valor),
                    formatar_valor(mapa.get("observacoes", "")),
                )
                max_linhas = 3
            elif nome == "titulo":
                texto = formatar_valor(valor)
                max_linhas = 3
            elif nome.isdigit():
                texto = formatar_valor(valor)
                max_linhas = 1
            else:
                texto = formatar_valor(valor)
                max_linhas = 2
            celulas.append(
                ft.DataCell(
                    ft.Text(
                        texto,
                        size=12,
                        color=TEXTO_PRIMARIO,
                        text_align=alinhamento_celula(nome),
                        max_lines=max_linhas,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    )
                )
            )
        if registro_id is not None:
            if acoes_separadas:
                if on_editar:
                    celulas.append(
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                icon_size=18,
                                tooltip="Editar",
                                on_click=lambda e, rid=registro_id: on_editar(rid),
                            )
                        )
                    )
                if on_excluir:
                    celulas.append(
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                icon_size=18,
                                tooltip="Excluir",
                                icon_color=COR_ERRO,
                                on_click=lambda e, rid=registro_id: on_excluir(rid),
                            )
                        )
                    )
            elif on_editar:
                celulas.append(
                    ft.DataCell(
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_size=18,
                            tooltip="Editar orador",
                            on_click=lambda e, rid=registro_id: on_editar(rid),
                        )
                    )
                )
        linhas.append(ft.DataRow(cells=celulas, color=cor_linha))

    return ft.DataTable(
        columns=colunas,
        rows=linhas,
        heading_row_color=ft.Colors.with_opacity(0.12, COR_DESTAQUE),
        heading_row_height=config.get("heading_row_height", 50),
        data_row_min_height=config.get("data_row_min_height", 46),
        data_row_max_height=config.get("data_row_max_height", 80),
        column_spacing=config.get("column_spacing", 20),
        horizontal_margin=config.get("horizontal_margin", 16),
        divider_thickness=0.4,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
    )


def criar_area_tabela(
    df: pd.DataFrame,
    on_editar: Callable[[int], None] | None = None,
    on_excluir: Callable[[int], None] | None = None,
    config: dict | None = None,
    coluna_id: str = "id",
) -> ft.Container:
    """Envolve a tabela em container com scroll horizontal e vertical."""
    config = config or {}
    if "coluna_id" not in config:
        config = {**config, "coluna_id": coluna_id}
    return ft.Container(
        content=ft.Column(
            [criar_tabela(df, on_editar=on_editar, on_excluir=on_excluir, config=config)],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        expand=True,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        padding=ft.Padding.symmetric(horizontal=12, vertical=14),
        bgcolor=FUNDO_CARD,
        shadow=_sombra_card(0.25),
    )


def criar_tela_padrao(
    page: ft.Page,
    titulo: str,
    descricao: str,
    df: pd.DataFrame | Callable[[], pd.DataFrame],
    colunas_filtro: list[str],
    barra_acoes: list[ft.Control] | None = None,
    on_editar: Callable[[int], None] | None = None,
    on_excluir: Callable[[int], None] | None = None,
    config_tabela: dict | None = None,
    controles_filtro: list[ft.Control] | None = None,
    on_atualizar_disponivel: Callable[[Callable[[str], None]], None] | None = None,
    renderizador_tabela: Callable[[pd.DataFrame], ft.Control] | None = None,
) -> ft.Column:
    """
    Layout padronizado para telas com tabela, busca e barra de ações.

    Usado em Oradores, Temas, Congregações, Arranjos e Designações.

    `df` pode ser um DataFrame fixo ou uma função sem argumentos que retorna o
    DataFrame atual — use a segunda forma quando a tela tiver filtros extras
    (ex.: `controles_filtro`) que mudam quais dados devem ser exibidos.
    Quando isso acontecer, passe `on_atualizar_disponivel` para receber uma
    referência de `atualizar_view` e poder chamá-la a partir do filtro extra.

    `renderizador_tabela`, se informado, substitui a tabela padrão por uma
    visão customizada (ex.: cartões agrupados) construída a partir do
    DataFrame já filtrado pela busca.
    """
    area_tabela = ft.Container(expand=True)
    texto_contagem = ft.Text(size=13, color=TEXTO_SECUNDARIO)

    def atualizar_view(termo_busca: str = ""):
        df_atual = df() if callable(df) else df
        df_filtrado = filtrar_dataframe(df_atual, termo_busca, colunas_filtro)
        if renderizador_tabela:
            area_tabela.content = renderizador_tabela(df_filtrado)
        else:
            area_tabela.content = criar_area_tabela(
                df_filtrado,
                on_editar=on_editar,
                on_excluir=on_excluir,
                config=config_tabela,
            )
        texto_contagem.value = f"Exibindo {len(df_filtrado)} de {len(df_atual)} registro(s)"
        page.update()

    campo_busca = ft.TextField(
        hint_text="Buscar por nome ou título...",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        on_change=lambda e: atualizar_view(e.control.value),
        **_estilo_campo_busca(),
    )

    itens_barra = [campo_busca]
    if barra_acoes:
        itens_barra.extend(barra_acoes)

    if on_atualizar_disponivel:
        on_atualizar_disponivel(atualizar_view)

    atualizar_view()

    linhas_filtro = []
    if controles_filtro:
        linhas_filtro = [
            ft.Row(controles_filtro, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=12),
        ]

    return ft.Column(
        [
            criar_cabecalho_tela(titulo, descricao),
            ft.Container(height=28),
            criar_secao_titulo("Dados"),
            ft.Container(height=12),
            *linhas_filtro,
            ft.Row(itens_barra, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=8),
            texto_contagem,
            ft.Container(height=8),
            area_tabela,
        ],
        spacing=0,
        expand=True,
    )


# ---------------------------------------------------------------------------
# Formulário de oradores
# ---------------------------------------------------------------------------

def abrir_dialog_orador(
    page: ft.Page,
    recarregar: Callable[[], None],
    orador_id: int | None = None,
    congregacao_padrao: int | None = None,
) -> None:
    """Abre dialog para adicionar ou editar um orador."""
    dados = carregar_orador(orador_id) if orador_id else None
    editando = dados is not None

    campo_nome = ft.TextField(label="Nome", value=dados["nome"] if dados else "", expand=True)
    campo_telefone = ft.TextField(label="Telefone", value=dados["telefone"] if dados else "", expand=True)
    campo_categoria = ft.Dropdown(
        label="Categoria",
        value=dados["categoria"] if dados else "Ancião",
        options=[
            ft.dropdown.Option("Ancião"),
            ft.dropdown.Option("Servo Ministerial"),
        ],
        expand=True,
    )
    campo_congregacao = ft.Dropdown(
        label="Congregação",
        value=dados["congregacao_id"] if dados else (
            str(congregacao_padrao) if congregacao_padrao else obter_id_minha_congregacao()
        ),
        options=carregar_congregacoes_opcoes(),
        expand=True,
    )
    obs_inicial = dados["observacoes"] if dados else ""
    faz_qualquer_tema = obs_tem_qualquer_tema(obs_inicial)
    campo_observacoes = ft.TextField(
        label="Observações",
        # Mostra as observações sem o marcador "qualquer tema" — quem controla
        # isso agora é o checkbox abaixo (o marcador é reescrito ao salvar).
        value=obs_sem_qualquer_tema(obs_inicial),
        multiline=True,
        min_lines=2,
        max_lines=4,
        expand=True,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    temas_selecionados: set[int] = set(dados["temas_nr"]) if dados else set()
    df_temas = carregar_dados("SELECT nr, titulo FROM temas ORDER BY nr")
    lista_temas = ft.Column(spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, height=220)
    texto_contagem_temas = ft.Text(size=12, color=TEXTO_SECUNDARIO)
    texto_qualquer_tema = ft.Text(
        "Este orador pode fazer qualquer tema — não é preciso selecionar temas.",
        size=12,
        italic=True,
        color=TEXTO_SECUNDARIO,
        visible=faz_qualquer_tema,
    )
    campo_qualquer_tema = ft.Checkbox(
        label="Pode fazer qualquer tema",
        value=faz_qualquer_tema,
    )

    def atualizar_contagem_temas() -> None:
        texto_contagem_temas.value = f"{len(temas_selecionados)} tema(s) selecionado(s)"

    def alternar_tema(nr: int, marcado: bool) -> None:
        if marcado:
            temas_selecionados.add(nr)
        else:
            temas_selecionados.discard(nr)
        atualizar_contagem_temas()
        page.update()

    def construir_lista_temas(filtro: str = "") -> None:
        filtro = filtro.strip().lower()
        linhas = []
        for row in df_temas.itertuples():
            # Mostra o número do esboço antes do título (a não ser que o título
            # já comece pelo número), para identificar o tema na lista.
            rotulo = (
                row.titulo
                if str(row.titulo).startswith(str(row.nr))
                else f"{row.nr} - {row.titulo}"
            )
            if filtro and filtro not in rotulo.lower():
                continue
            linhas.append(
                ft.Checkbox(
                    label=rotulo,
                    value=row.nr in temas_selecionados,
                    on_change=lambda e, nr=row.nr: alternar_tema(nr, e.control.value),
                )
            )
        lista_temas.controls = linhas
        atualizar_contagem_temas()

    campo_busca_temas = ft.TextField(
        label="Buscar tema",
        prefix_icon=ft.Icons.SEARCH,
        on_change=lambda e: (construir_lista_temas(e.control.value), page.update()),
    )
    construir_lista_temas()

    def alternar_qualquer_tema(_=None) -> None:
        # Quando o orador faz qualquer tema, a lista de temas fica irrelevante:
        # desabilita a seleção e mostra o aviso.
        ativo = bool(campo_qualquer_tema.value)
        campo_busca_temas.disabled = ativo
        lista_temas.disabled = ativo
        texto_qualquer_tema.visible = ativo
        page.update()

    campo_qualquer_tema.on_change = alternar_qualquer_tema
    campo_busca_temas.disabled = faz_qualquer_tema
    lista_temas.disabled = faz_qualquer_tema

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        nome = campo_nome.value.strip()
        if not nome:
            texto_erro.value = "O nome é obrigatório."
            texto_erro.visible = True
            page.update()
            return

        congregacao_id = int(campo_congregacao.value) if campo_congregacao.value else None
        observacoes_final = obs_definir_qualquer_tema(
            campo_observacoes.value.strip(), campo_qualquer_tema.value
        )
        salvar_orador(
            nome,
            campo_telefone.value.strip(),
            campo_categoria.value,
            congregacao_id,
            observacoes_final,
            temas_selecionados,
            orador_id=orador_id if editando else None,
        )

        fechar()
        recarregar()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Editar orador" if editando else "Novo orador"),
        content=ft.Container(
            content=ft.Column(
                [
                    campo_nome,
                    campo_telefone,
                    ft.Row([campo_categoria, campo_congregacao], spacing=12),
                    campo_observacoes,
                    texto_erro,
                    ft.Container(height=4),
                    campo_qualquer_tema,
                    ft.Text("Temas que pode fazer", weight=ft.FontWeight.W_600, size=13),
                    texto_qualquer_tema,
                    campo_busca_temas,
                    lista_temas,
                    texto_contagem_temas,
                ],
                spacing=12,
                tight=True,
                width=480,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.Padding.only(top=8),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=fechar),
            ft.FilledButton("Salvar", icon=ft.Icons.SAVE, on_click=salvar),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dialog)


def confirmar_exclusao_orador(
    page: ft.Page,
    recarregar: Callable[[], None],
    orador_id: int,
) -> None:
    """Exibe confirmação e exclui o orador se o usuário confirmar."""
    dados = carregar_orador(orador_id)
    nome = dados["nome"] if dados else "este orador"

    def fechar(_=None):
        page.pop_dialog()

    def excluir(_=None):
        try:
            excluir_orador(orador_id)
            fechar()
            recarregar()
        except Exception:
            fechar()
            mostrar_aviso(page, "Erro", "Não foi possível excluir este orador.")

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar exclusão"),
            content=ft.Text(
                f'Tem certeza que deseja excluir o orador "{nome}"?\n\n'
                "As designações antigas dele continuam no histórico e no quadro.",
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton(
                    "Excluir",
                    icon=ft.Icons.DELETE,
                    on_click=excluir,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


# ---------------------------------------------------------------------------
# Formulário de congregações
# ---------------------------------------------------------------------------

def abrir_dialog_congregacao(
    page: ft.Page,
    recarregar: Callable[[], None],
    congregacao_id: int | None = None,
) -> None:
    """Abre dialog para cadastrar ou editar uma congregação."""
    dados = carregar_congregacao(congregacao_id) if congregacao_id else None
    editando = dados is not None

    campo_nome = ft.TextField(
        label="Nome da congregação",
        value=dados["nome"] if dados else "",
        expand=True,
    )
    campo_responsavel = ft.TextField(
        label="Responsável",
        value=dados["responsavel"] if dados else "",
        expand=True,
    )
    campo_telefone = ft.TextField(
        label="Telefone",
        value=dados["telefone"] if dados else "",
        expand=True,
    )
    campo_endereco = ft.TextField(
        label="Endereço",
        value=dados["endereco"] if dados else "",
        expand=True,
    )
    campo_dia = ft.TextField(
        label="Dia da reunião",
        hint_text="Ex: Domingo",
        value=dados["dia_semana"] if dados else "",
        expand=True,
    )
    campo_horario = ft.TextField(
        label="Horário da reunião",
        hint_text="Ex: 19:00",
        value=dados["horario"] if dados else "",
        expand=True,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        nome = (campo_nome.value or "").strip()
        if not nome:
            texto_erro.value = "O nome da congregação é obrigatório."
            texto_erro.visible = True
            page.update()
            return

        params = (
            nome,
            (campo_responsavel.value or "").strip(),
            (campo_telefone.value or "").strip(),
            (campo_endereco.value or "").strip(),
            (campo_dia.value or "").strip(),
            (campo_horario.value or "").strip(),
        )

        try:
            if editando:
                executar_escrita(
                    """
                    UPDATE congregacoes
                    SET nome=?, responsavel=?, telefone=?, endereco=?, dia_semana=?, horario=?
                    WHERE id=?
                    """,
                    params + (congregacao_id,),
                )
            else:
                executar_escrita(
                    """
                    INSERT INTO congregacoes (
                        nome, responsavel, telefone, endereco, dia_semana, horario, observacoes
                    ) VALUES (?, ?, ?, ?, ?, ?, '')
                    """,
                    params,
                )
        except Exception:
            texto_erro.value = "Não foi possível salvar. Verifique se o nome já existe."
            texto_erro.visible = True
            page.update()
            return

        fechar()
        recarregar()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar congregação" if editando else "Nova congregação"),
            content=ft.Container(
                content=ft.Column(
                    [
                        campo_nome,
                        ft.Row([campo_responsavel, campo_telefone], spacing=12),
                        campo_endereco,
                        ft.Row([campo_dia, campo_horario], spacing=12),
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=480,
                ),
                padding=ft.Padding.only(top=8),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Salvar", icon=ft.Icons.SAVE, on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def confirmar_exclusao_congregacao(
    page: ft.Page,
    recarregar: Callable[[], None],
    congregacao_id: int,
) -> None:
    """Exibe confirmação e exclui a congregação se o usuário confirmar."""
    dados = carregar_congregacao(congregacao_id)
    nome = dados["nome"] if dados else "esta congregação"

    def fechar(_=None):
        page.pop_dialog()

    def excluir(_=None):
        try:
            executar_escrita("DELETE FROM congregacoes WHERE id = ?", (congregacao_id,))
            fechar()
            recarregar()
        except Exception:
            fechar()
            mostrar_aviso(
                page,
                "Não foi possível excluir",
                "Esta congregação possui registros vinculados (oradores, arranjos ou designações). "
                "Remova os vínculos antes de excluir.",
            )

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar exclusão"),
            content=ft.Text(f'Tem certeza que deseja excluir a congregação "{nome}"?'),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton(
                    "Excluir",
                    icon=ft.Icons.DELETE,
                    on_click=excluir,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


# ---------------------------------------------------------------------------
# Formulário de designações
# ---------------------------------------------------------------------------

def mostrar_aviso(page: ft.Page, titulo: str, mensagem: str) -> None:
    """Exibe um dialog informativo."""
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Text(mensagem),
            actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
        )
    )


def mostrar_sucesso(page: ft.Page, mensagem: str) -> None:
    """Confirmação discreta no rodapé (snackbar), sem interromper o fluxo."""
    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(mensagem, color="#04342C", weight=ft.FontWeight.W_600),
            bgcolor=COR_DESTAQUE_CLARA,
        )
    )


def acionar_geracao_pdf_envio(page: ft.Page, orador_ids: set[int]) -> None:
    """Gera o PDF de envio de oradores selecionados ou exibe aviso."""
    if not orador_ids:
        mostrar_aviso(
            page,
            "Nenhum orador selecionado",
            "Marque pelo menos um orador na coluna \"Selecionar\" antes de gerar o PDF.",
        )
        return

    try:
        caminho, erro = gerar_pdf_envio(list(orador_ids))
        if erro:
            mostrar_aviso(page, "Não foi possível gerar o PDF", erro)
            return

        abrir_arquivo(caminho)
        mostrar_aviso(
            page,
            "PDF gerado com sucesso",
            f"A lista de oradores para envio foi salva em:\n{caminho}",
        )
    except Exception as exc:
        mostrar_aviso(
            page,
            "Erro ao gerar PDF",
            f"Não foi possível gerar o arquivo. Detalhes: {exc}",
        )


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------

def _proximas_datas_reuniao(quantidade: int = 4) -> list[date]:
    """Próximas datas de reunião de fim de semana da minha congregação, a partir de hoje."""
    config = carregar_configuracao()
    weekday = _dia_semana_para_weekday(config.get("dia_reuniao", ""))
    if weekday is None:
        weekday = 5
    datas: list[date] = []
    atual = date.today()
    while len(datas) < quantidade and (atual - date.today()).days < 120:
        if atual.weekday() == weekday:
            datas.append(atual)
        atual += timedelta(days=1)
    return datas


def _semanas_reuniao_mes(ano: int, mes: int) -> list[date]:
    """Datas de reunião de fim de semana da minha congregação num mês."""
    config = carregar_configuracao()
    weekday = _dia_semana_para_weekday(config.get("dia_reuniao", ""))
    if weekday is None:
        weekday = 5
    return _datas_por_weekday_no_mes(ano, mes, weekday)


def _resumo_mes_programacao(
    ano: int,
    mes: int,
    recebidos: dict | None = None,
    presidentes: dict | None = None,
    contagens_ano: dict | None = None,
    especiais: dict | None = None,
) -> dict:
    """Resumo de um mês: semanas, cobertas por orador, presidentes e enviados.

    Datas especiais (Assembleia, Congresso…) contam como semana coberta e
    não cobram presidente — quem decide isso é o cadastro da data especial.
    """
    semanas = _semanas_reuniao_mes(ano, mes)
    datas_semanas = {_formatar_data_arranjo(d) for d in semanas}
    recebidos = recebidos if recebidos is not None else carregar_recebidos_por_ano(ano)
    presidentes = presidentes if presidentes is not None else carregar_presidentes_por_ano(ano)
    contagens_ano = contagens_ano if contagens_ano is not None else contar_designacoes_por_mes(ano)
    especiais = especiais if especiais is not None else listar_datas_especiais_por_ano(ano)
    contagens = contagens_ano.get(mes, {"recebidos": 0, "enviados": 0})
    cobertas = sum(1 for d in datas_semanas if d in recebidos or d in especiais)
    pres_definidos = sum(1 for d in datas_semanas if d in presidentes or d in especiais)
    return {
        "semanas": len(semanas),
        "cobertas": cobertas,
        "presidentes": pres_definidos,
        "recebidos": contagens["recebidos"],
        "enviados": contagens["enviados"],
    }


def _linha_agenda_especial(data_ref: date, especial: dict) -> ft.Control:
    detalhes = " · ".join(
        parte
        for parte in (
            especial.get("orador") or "",
            _resumir_texto_tabela(especial.get("tema") or "", 40),
        )
        if parte
    )
    presidente = especial.get("presidente_nome") or ""
    return ft.Row(
        [
            ft.Container(
                content=ft.Text(
                    data_ref.strftime("%d/%m"),
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=COR_AVISO,
                ),
                bgcolor=ft.Colors.with_opacity(0.14, COR_AVISO),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            ),
            ft.Container(
                content=ft.Text(
                    especial.get("tipo", "Data especial"),
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=COR_AVISO,
                ),
                bgcolor=ft.Colors.with_opacity(0.10, COR_AVISO),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            ),
            ft.Text(
                detalhes,
                size=12,
                color=TEXTO_SECUNDARIO,
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                f"Pres.: {presidente}" if presidente else "",
                size=12,
                color=TEXTO_SECUNDARIO,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _linha_agenda_inicio(
    data_ref: date,
    recebidos: dict[str, dict],
    presidentes: dict[str, dict],
    especiais: dict[str, dict] | None = None,
) -> ft.Control:
    data_str = _formatar_data_arranjo(data_ref)
    especial = (especiais or {}).get(data_str)
    if especial:
        return _linha_agenda_especial(data_ref, especial)
    info = recebidos.get(data_str)
    presidente = presidentes.get(data_str)
    orador = info["orador"] if info else "—"
    tema = _resumir_texto_tabela(info["tema"], 46) if info and info.get("tema") else ""
    if info and info.get("tema_nr") and tema:
        tema = f"{info['tema_nr']} - {tema}" if not tema.startswith(str(info["tema_nr"])) else tema

    return ft.Row(
        [
            ft.Container(
                content=ft.Text(
                    data_ref.strftime("%d/%m"),
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=COR_DESTAQUE_SUAVE,
                ),
                bgcolor=ft.Colors.with_opacity(0.14, COR_DESTAQUE_CLARA),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            ),
            ft.Text(
                orador,
                size=13,
                weight=ft.FontWeight.W_600,
                color=TEXTO_PRIMARIO if info else TEXTO_SECUNDARIO,
                width=150,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                tema or ("sem orador definido" if not info else "sem tema"),
                size=12,
                color=TEXTO_SECUNDARIO,
                italic=not tema,
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                f"Pres.: {presidente['nome']}" if presidente else "sem presidente",
                size=12,
                color=TEXTO_SECUNDARIO if presidente else COR_ERRO,
                max_lines=1,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _card_kpi_inicio(
    rotulo: str,
    valor: str,
    detalhe: str,
    cor_valor: str,
    icone: str | None = None,
) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(icone or ft.Icons.INSIGHTS, size=20, color=cor_valor),
                    bgcolor=ft.Colors.with_opacity(0.12, cor_valor),
                    border_radius=10,
                    padding=10,
                ),
                ft.Column(
                    [
                        ft.Text(rotulo, size=12, color=TEXTO_SECUNDARIO),
                        ft.Row(
                            [
                                ft.Text(valor, size=22, weight=ft.FontWeight.W_700, color=cor_valor),
                                ft.Text(detalhe, size=12, color=TEXTO_SECUNDARIO),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                    ],
                    spacing=2,
                    tight=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        expand=True,
    )


DIAS_SEMANA_EXTENSO = [
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira", "Sexta-feira", "Sábado", "Domingo",
]


def _card_proxima_reuniao(
    data_ref: date,
    recebidos: dict[str, dict],
    presidentes: dict[str, dict],
    especiais: dict[str, dict],
) -> ft.Container:
    """Card em destaque com os detalhes da próxima reunião de fim de semana."""
    data_str = _formatar_data_arranjo(data_ref)
    especial = especiais.get(data_str)
    info = recebidos.get(data_str)
    presidente = presidentes.get(data_str)

    dias_faltando = (data_ref - date.today()).days
    if dias_faltando == 0:
        quando = "É hoje!"
    elif dias_faltando == 1:
        quando = "É amanhã"
    else:
        quando = f"Em {dias_faltando} dias"

    if especial:
        titulo_principal = especial.get("tipo") or "Data especial"
        cor_borda = COR_AVISO
        linhas_detalhe = [
            parte
            for parte in (especial.get("orador") or "", especial.get("tema") or "")
            if parte
        ]
        rotulo_presidente = especial.get("presidente_nome") or ""
    else:
        cor_borda = COR_DESTAQUE
        titulo_principal = (info or {}).get("orador") or "Nenhum orador designado"
        tema = (info or {}).get("tema") or ""
        if info and info.get("tema_nr") and tema and not tema.startswith(str(info["tema_nr"])):
            tema = f"{info['tema_nr']} - {tema}"
        linhas_detalhe = [tema] if tema else []
        rotulo_presidente = presidente["nome"] if presidente else ""

    coluna_data = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    f"{data_ref.day:02d}",
                    size=30,
                    weight=ft.FontWeight.W_700,
                    color=COR_DESTAQUE_SUAVE if not especial else COR_AVISO,
                ),
                ft.Text(
                    NOMES_MESES[data_ref.month][:3].upper(),
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=TEXTO_SECUNDARIO,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        bgcolor=FUNDO_ELEVADO,
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=18, vertical=10),
    )

    detalhes: list[ft.Control] = [
        ft.Row(
            [
                ft.Text(
                    "PRÓXIMA REUNIÃO",
                    size=11,
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Container(
                    content=ft.Text(quando, size=11, weight=ft.FontWeight.W_600, color=cor_borda),
                    bgcolor=ft.Colors.with_opacity(0.12, cor_borda),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                ),
                ft.Text(
                    DIAS_SEMANA_EXTENSO[data_ref.weekday()],
                    size=11,
                    color=TEXTO_SECUNDARIO,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        ft.Text(
            titulo_principal,
            size=18,
            weight=ft.FontWeight.W_700,
            color=TEXTO_PRIMARIO if (info or especial) else TEXTO_SECUNDARIO,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    ]
    for linha in linhas_detalhe:
        detalhes.append(
            ft.Text(
                linha,
                size=13,
                color=TEXTO_SECUNDARIO,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )
    detalhes.append(
        ft.Text(
            f"Presidente: {rotulo_presidente}" if rotulo_presidente else "Presidente: a definir",
            size=12,
            color=TEXTO_SECUNDARIO if rotulo_presidente else COR_ERRO,
        )
    )

    return ft.Container(
        content=ft.Row(
            [
                coluna_data,
                ft.Column(detalhes, spacing=4, tight=True, expand=True),
            ],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.55, cor_borda)),
        border_radius=12,
        padding=16,
        expand=True,
    )


def _linha_sugestao_tema(mapa: dict) -> ft.Control:
    ultimo = mapa.get("ultimo_uso") or "Nunca"
    return ft.Row(
        [
            ft.Container(
                content=ft.Text(
                    str(mapa["nr"]),
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=COR_DESTAQUE_SUAVE,
                ),
                bgcolor=ft.Colors.with_opacity(0.12, COR_DESTAQUE_CLARA),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                width=46,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Text(
                mapa["titulo"],
                size=13,
                color=TEXTO_PRIMARIO,
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                mapa.get("assunto") if mapa.get("assunto") not in (None, "—") else "",
                size=11,
                color=TEXTO_SECUNDARIO,
                width=180,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Container(
                content=ft.Text(
                    ultimo,
                    size=11,
                    weight=ft.FontWeight.W_600,
                    color=COR_AVISO if ultimo == "Nunca" else TEXTO_SECUNDARIO,
                ),
                width=64,
                alignment=ft.Alignment.CENTER_RIGHT,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def tela_inicio(
    page: ft.Page,
    recarregar: Callable[[], None],
    navegar: Callable[[int], None] | None = None,
) -> ft.Control:
    """Central de trabalho: próxima reunião, agenda, pendências e sugestões."""
    hoje = date.today()
    ano, mes = hoje.year, hoje.month

    arranjos = {a["mes_inicio"]: a for a in carregar_arranjos_por_ano(ano)}
    arranjo_mes = arranjos.get(mes)
    recebidos = carregar_recebidos_por_ano(ano)
    presidentes = carregar_presidentes_por_ano(ano)
    especiais = listar_datas_especiais_por_ano(ano)
    resumo = _resumo_mes_programacao(ano, mes, recebidos, presidentes, None, especiais)

    df_temas = carregar_dataframe_temas(apenas_anos_visiveis=True)
    total_temas = len(df_temas)
    nunca_feitos = int((df_temas["ultimo_uso_chave"] == "").sum()) if total_temas else 0
    total_oradores = int(carregar_dados("SELECT COUNT(*) AS n FROM oradores")["n"].iloc[0])

    config = carregar_configuracao()
    subtitulo = (
        f"{DIAS_SEMANA_EXTENSO[hoje.weekday()]}, {hoje.day} de "
        f"{NOMES_MESES[mes].lower()} · {config.get('dia_reuniao') or 'Sábado'} é o dia da reunião"
    )
    if arranjo_mes and arranjo_mes.get("congregacao"):
        subtitulo += f" · Anfitriã do mês: {arranjo_mes['congregacao']}"

    def ir_para(indice: int):
        if navegar:
            navegar(indice)

    kpis = ft.Row(
        [
            _card_kpi_inicio(
                "Semanas com orador",
                str(resumo["cobertas"]),
                f"de {resumo['semanas']} no mês",
                COR_SUCESSO if resumo["cobertas"] >= resumo["semanas"] else COR_AVISO,
                ft.Icons.RECORD_VOICE_OVER_OUTLINED,
            ),
            _card_kpi_inicio(
                "Presidentes definidos",
                str(resumo["presidentes"]),
                f"de {resumo['semanas']}",
                COR_SUCESSO if resumo["presidentes"] >= resumo["semanas"] else COR_AVISO,
                ft.Icons.CO_PRESENT_OUTLINED,
            ),
            _card_kpi_inicio(
                "Envios do mês",
                str(resumo["enviados"]),
                "oradores fora",
                COR_DESTAQUE_SUAVE,
                ft.Icons.SEND_OUTLINED,
            ),
            _card_kpi_inicio(
                "Temas nunca feitos",
                str(nunca_feitos),
                f"de {total_temas}",
                COR_AVISO if nunca_feitos else COR_SUCESSO,
                ft.Icons.MENU_BOOK_OUTLINED,
            ),
        ],
        spacing=12,
    )

    proximas = _proximas_datas_reuniao(5)
    card_destaque = (
        _card_proxima_reuniao(proximas[0], recebidos, presidentes, especiais)
        if proximas
        else None
    )
    linhas_agenda = [
        _linha_agenda_inicio(data_ref, recebidos, presidentes, especiais)
        for data_ref in proximas[1:]
    ]
    card_agenda = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Semanas seguintes", size=14, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "Ver programação",
                            icon=ft.Icons.ARROW_FORWARD,
                            on_click=lambda _: ir_para(1),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=2),
                *[
                    item
                    for linha in linhas_agenda
                    for item in (linha, ft.Divider(height=1, color=BORDA_SUAVE))
                ][:-1],
            ],
            spacing=8,
            tight=True,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
        padding=16,
    )

    pendencias: list[str] = []
    contagens_ano = contar_designacoes_por_mes(ano)
    for mes_ref in range(mes, 13):
        if mes_ref not in arranjos:
            continue
        r = _resumo_mes_programacao(ano, mes_ref, recebidos, presidentes, contagens_ano, especiais)
        nome_mes = NOMES_MESES[mes_ref]
        if r["semanas"] and r["cobertas"] == 0:
            pendencias.append(f"{nome_mes}: nenhuma semana com orador")
        elif r["cobertas"] < r["semanas"]:
            pendencias.append(f"{nome_mes}: só {r['cobertas']} de {r['semanas']} semanas com orador")
        if r["cobertas"] and r["presidentes"] < r["semanas"]:
            faltam = r["semanas"] - r["presidentes"]
            pendencias.append(f"{nome_mes}: {faltam} semana(s) sem presidente")
    if len(pendencias) > 6:
        restante = len(pendencias) - 6
        pendencias = pendencias[:6] + [f"… e mais {restante} pendência(s)"]

    linhas_pendencias: list[ft.Control] = [
        ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=15, color=COR_AVISO),
                ft.Text(texto, size=12, color=TEXTO_PRIMARIO, expand=True, max_lines=2),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        for texto in pendencias
    ] or [
        ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=15, color=COR_SUCESSO),
                ft.Text("Tudo em dia até o fim do ano.", size=12, color=TEXTO_PRIMARIO),
            ],
            spacing=8,
        )
    ]

    def exportar_quadro_atual(_=None):
        try:
            caminho, erro = gerar_quadro_anuncios(ano, mes)
            if erro:
                mostrar_aviso(page, "Não foi possível exportar", erro)
                return
            abrir_arquivo(caminho)
            mostrar_sucesso(page, f"Quadro exportado: {caminho}")
        except Exception as exc:
            mostrar_aviso(page, "Erro", f"Não foi possível gerar o PDF: {exc}")

    par_inicio, par_fim = par_meses_do_mes_quadro(mes)
    card_pendencias = ft.Container(
        content=ft.Column(
            [
                ft.Text("Pendências", size=14, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
                ft.Container(height=6),
                *linhas_pendencias,
            ],
            spacing=8,
            tight=True,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
        padding=16,
    )

    card_acoes = ft.Container(
        content=ft.Column(
            [
                ft.Text("Ações rápidas", size=14, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
                ft.Container(height=6),
                ft.FilledButton(
                    f"Exportar quadro {NOMES_MESES[par_inicio][:3]}–{NOMES_MESES[par_fim][:3]}",
                    icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
                    on_click=exportar_quadro_atual,
                ),
                ft.OutlinedButton(
                    "Abrir programação",
                    icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                    on_click=lambda _: ir_para(1),
                ),
                ft.OutlinedButton(
                    "Cadastro de oradores",
                    icon=ft.Icons.GROUPS_OUTLINED,
                    on_click=lambda _: ir_para(2),
                ),
                ft.OutlinedButton(
                    "Catálogo de temas",
                    icon=ft.Icons.MENU_BOOK_OUTLINED,
                    on_click=lambda _: ir_para(4),
                ),
            ],
            spacing=8,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
        padding=16,
    )

    # Sugestões: temas há mais tempo sem fazer (ignora os "(Não use.)" e pendentes)
    df_sugestoes = df_temas[~df_temas["titulo"].str.startswith("(")]
    df_sugestoes = df_sugestoes.sort_values(["ultimo_uso_chave", "nr"]).head(6)
    linhas_sugestoes = [
        _linha_sugestao_tema(dict(zip(df_sugestoes.columns, linha)))
        for linha in df_sugestoes.itertuples(index=False, name=None)
    ]
    card_sugestoes = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=16, color=COR_AVISO),
                        ft.Text(
                            "Sugestões de temas — há mais tempo sem fazer",
                            size=14,
                            weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO,
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "Ver catálogo",
                            icon=ft.Icons.ARROW_FORWARD,
                            on_click=lambda _: ir_para(4),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=2),
                *[
                    item
                    for linha in linhas_sugestoes
                    for item in (linha, ft.Divider(height=1, color=BORDA_SUAVE))
                ][:-1],
            ],
            spacing=8,
            tight=True,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
        padding=16,
    ) if linhas_sugestoes else None

    # Primeiros passos: aparece só enquanto o app está sem dados básicos
    card_primeiros_passos = None
    if total_oradores == 0 or total_temas == 0:
        passos: list[ft.Control] = []
        if total_temas == 0:
            passos.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LOOKS_ONE_OUTLINED, size=18, color=COR_DESTAQUE_SUAVE),
                        ft.Text(
                            "Importe os formulários S-99/S-99a (PDF) na aba Temas.",
                            size=13, color=TEXTO_PRIMARIO, expand=True,
                        ),
                        ft.TextButton("Abrir Temas", on_click=lambda _: ir_para(4)),
                    ],
                    spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        if total_oradores == 0:
            passos.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LOOKS_TWO_OUTLINED, size=18, color=COR_DESTAQUE_SUAVE),
                        ft.Text(
                            "Cadastre congregações, oradores e presidentes — pela planilha-modelo "
                            "em Ajustes ou restaurando um backup.",
                            size=13, color=TEXTO_PRIMARIO, expand=True,
                        ),
                        ft.TextButton("Abrir Ajustes", on_click=lambda _: ir_para(6)),
                    ],
                    spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        card_primeiros_passos = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Primeiros passos", size=14, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
                    ft.Container(height=4),
                    *passos,
                ],
                spacing=8,
                tight=True,
            ),
            bgcolor=FUNDO_CARD,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.55, COR_DESTAQUE)),
            border_radius=12,
            padding=16,
        )

    coluna_principal = ft.Column(
        [c for c in (card_destaque, card_agenda) if c is not None],
        spacing=12,
        expand=True,
        tight=True,
    )
    coluna_lateral = ft.Column(
        [card_pendencias, card_acoes],
        spacing=12,
        width=300,
        tight=True,
    )

    blocos: list[ft.Control] = [
        criar_cabecalho_tela(f"{NOMES_MESES[mes]} de {ano}", subtitulo),
        ft.Container(height=20),
    ]
    if card_primeiros_passos is not None:
        blocos += [card_primeiros_passos, ft.Container(height=12)]
    blocos += [
        kpis,
        ft.Container(height=12),
        ft.Row(
            [coluna_principal, coluna_lateral],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
    ]
    if card_sugestoes is not None:
        blocos += [ft.Container(height=12), card_sugestoes]

    return ft.Column(
        blocos,
        spacing=0,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _iniciais_nome(nome: str) -> str:
    partes = [p for p in (nome or "").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def _criar_lista_oradores(
    df: pd.DataFrame,
    estado_selecao: dict,
    on_editar: Callable[[int], None],
    on_excluir: Callable[[int], None],
) -> ft.Container:
    """Lista de oradores com iniciais, privilégio, telefone e chip de temas."""
    if df.empty:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.PERSON_SEARCH, size=36, color=TEXTO_SECUNDARIO),
                    ft.Text("Nenhum orador encontrado.", size=13, color=TEXTO_SECUNDARIO),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=32,
            alignment=ft.Alignment.CENTER,
        )

    linhas: list[ft.Control] = []
    registros = list(df.itertuples(index=False, name=None))
    colunas = list(df.columns)
    for indice, linha in enumerate(registros):
        mapa = dict(zip(colunas, linha))
        orador_id = int(mapa["id"])
        nome = formatar_valor(mapa.get("nome"))
        categoria = formatar_valor(mapa.get("categoria"))
        telefone = formatar_valor(mapa.get("telefone")) or "sem telefone"
        observacoes = formatar_valor(mapa.get("observacoes"))
        temas_txt = formatar_valor(mapa.get("temas"))
        qualquer_tema = "qualquer tema" in observacoes.lower() if observacoes else False
        qtd_temas = len([x for x in temas_txt.split(",") if x.strip()]) if temas_txt else 0

        if qualquer_tema:
            chip_texto, chip_cor = "qualquer tema", COR_SUCESSO
        elif qtd_temas:
            chip_texto, chip_cor = f"{qtd_temas} tema(s)", COR_DESTAQUE_SUAVE
        else:
            chip_texto, chip_cor = "sem temas", COR_AVISO

        def alternar_selecao(e, rid=orador_id):
            if e.control.value:
                estado_selecao["ids"].add(rid)
            else:
                estado_selecao["ids"].discard(rid)

        linhas.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Checkbox(
                            value=orador_id in estado_selecao["ids"],
                            on_change=alternar_selecao,
                            tooltip="Selecionar para o PDF de envio",
                        ),
                        ft.Container(
                            content=ft.Text(
                                _iniciais_nome(nome),
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=COR_DESTAQUE_SUAVE,
                            ),
                            width=36,
                            height=36,
                            border_radius=18,
                            bgcolor=ft.Colors.with_opacity(0.16, COR_DESTAQUE_CLARA),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(nome, size=14, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
                                        ft.Text(f"· {categoria}" if categoria else "", size=12, color=TEXTO_SECUNDARIO),
                                    ],
                                    spacing=6,
                                ),
                                ft.Text(telefone, size=12, color=TEXTO_SECUNDARIO),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(chip_texto, size=11, weight=ft.FontWeight.W_600, color=chip_cor),
                            bgcolor=ft.Colors.with_opacity(0.13, chip_cor),
                            border_radius=9,
                            padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_size=17,
                            tooltip="Editar",
                            icon_color=TEXTO_SECUNDARIO,
                            on_click=lambda e, rid=orador_id: on_editar(rid),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=17,
                            tooltip="Excluir",
                            icon_color=COR_ERRO,
                            on_click=lambda e, rid=orador_id: on_excluir(rid),
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                border=ft.Border(
                    ft.BorderSide(0, BORDA_SUAVE),
                    ft.BorderSide(0, BORDA_SUAVE),
                    ft.BorderSide(1 if indice < len(registros) - 1 else 0, BORDA_SUAVE),
                    ft.BorderSide(0, BORDA_SUAVE),
                ),
            )
        )

    return ft.Container(
        content=ft.Column(linhas, spacing=0, tight=True, scroll=ft.ScrollMode.AUTO),
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        bgcolor=FUNDO_CARD,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        expand=True,
    )


def tela_oradores(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Lista oradores locais com temas, busca e formulário de adição/edição."""
    df_completo = carregar_dados(SQL_ORADORES)
    id_minha_congregacao = obter_id_minha_congregacao()
    estado_selecao = {"ids": set()}
    estado_filtro = {"modo": "minha" if id_minha_congregacao else "outras"}
    referencia_atualizar: dict[str, Callable[[str], None]] = {}

    def df_filtrado_congregacao() -> pd.DataFrame:
        if not id_minha_congregacao:
            return df_completo
        coluna_congregacao = df_completo["congregacao_id"].astype("Int64").astype(str)
        if estado_filtro["modo"] == "minha":
            return df_completo[coluna_congregacao == str(id_minha_congregacao)]
        resultado = df_completo[coluna_congregacao != str(id_minha_congregacao)]
        return resultado.sort_values(["congregacao", "categoria", "nome"])

    def abrir_novo(_=None):
        abrir_dialog_orador(page, recarregar)

    def abrir_editar(orador_id: int):
        abrir_dialog_orador(page, recarregar, orador_id=orador_id)

    def abrir_excluir(orador_id: int):
        confirmar_exclusao_orador(page, recarregar, orador_id)

    def gerar_pdf_envio(_=None):
        acionar_geracao_pdf_envio(page, estado_selecao["ids"])

    def registrar_atualizar(fn: Callable[[str], None]) -> None:
        referencia_atualizar["fn"] = fn

    def ao_mudar_filtro(e):
        estado_filtro["modo"] = e.control.selected[0] if e.control.selected else "minha"
        if "fn" in referencia_atualizar:
            referencia_atualizar["fn"]("")

    seletor_congregacao = ft.SegmentedButton(
        selected=[estado_filtro["modo"]],
        allow_empty_selection=False,
        on_change=ao_mudar_filtro,
        segments=[
            ft.Segment(value="minha", label=ft.Text("Minha congregação")),
            ft.Segment(value="outras", label=ft.Text("Outras congregações")),
        ],
    )

    def renderizar_oradores(df_filtrado: pd.DataFrame) -> ft.Control:
        if estado_filtro["modo"] != "outras":
            return _criar_lista_oradores(df_filtrado, estado_selecao, abrir_editar, abrir_excluir)

        if df_filtrado.empty:
            return _criar_lista_oradores(df_filtrado, estado_selecao, abrir_editar, abrir_excluir)

        def bloco_congregacao(nome_congregacao: str, grupo: pd.DataFrame) -> ft.Control:
            cong_ids = [c for c in grupo["congregacao_id"].dropna().unique()]
            cong_id = int(cong_ids[0]) if len(cong_ids) else None

            def adicionar_aqui(_=None, cong_id=cong_id):
                abrir_dialog_orador(page, recarregar, congregacao_padrao=cong_id)

            return ft.ExpansionTile(
                title=ft.Row(
                    [
                        ft.Text(
                            f"{nome_congregacao} ({len(grupo)})",
                            weight=ft.FontWeight.W_600,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.PERSON_ADD_ALT,
                            icon_size=18,
                            icon_color=COR_DESTAQUE_SUAVE,
                            tooltip=f"Adicionar orador em {nome_congregacao}",
                            on_click=adicionar_aqui,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                controls=[
                    _criar_lista_oradores(grupo, estado_selecao, abrir_editar, abrir_excluir)
                ],
            )

        blocos = [
            bloco_congregacao(nome_congregacao, grupo)
            for nome_congregacao, grupo in df_filtrado.groupby("congregacao", sort=True)
        ]
        return ft.Container(
            content=ft.Column(blocos, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True,
            border=ft.Border.all(1, BORDA_SUAVE),
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=12, vertical=14),
            bgcolor=FUNDO_CARD,
            shadow=_sombra_card(0.25),
        )

    return criar_tela_padrao(
        page=page,
        titulo="Oradores",
        descricao="Oradores da minha congregação e temas que podem apresentar",
        df=df_filtrado_congregacao,
        colunas_filtro=["nome", "categoria", "telefone", "temas", "observacoes", "congregacao"],
        controles_filtro=[seletor_congregacao],
        on_atualizar_disponivel=registrar_atualizar,
        renderizador_tabela=renderizar_oradores,
        barra_acoes=[
            ft.FilledButton(
                "Novo orador",
                icon=ft.Icons.PERSON_ADD,
                on_click=abrir_novo,
            ),
            ft.OutlinedButton(
                "Gerar PDF para Envio",
                icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
                on_click=gerar_pdf_envio,
            ),
        ],
        on_editar=abrir_editar,
        on_excluir=abrir_excluir,
    )


def _colunas_filtro_temas() -> list[str]:
    anos = [str(item["ano"]) for item in listar_anos_colunas(apenas_visiveis=True)]
    return ["nr", "titulo", "assunto", *anos, "ultimo_uso", "restricoes"]


def _validar_mes_ano(valor: str) -> bool:
    """Aceita vazio ou data no formato MM/AAAA."""
    texto = (valor or "").strip()
    if not texto or texto == "—":
        return True
    partes = texto.split("/")
    if len(partes) != 2:
        return False
    try:
        mes = int(partes[0])
        ano = int(partes[1])
        return 1 <= mes <= 12 and 2000 <= ano <= 2100
    except ValueError:
        return False


def abrir_dialog_tema(
    page: ft.Page,
    recarregar: Callable[[], None],
    tema_nr: int,
) -> None:
    """Abre dialog para editar título, observações e datas de uso por ano."""
    dados = carregar_tema(tema_nr)
    if not dados:
        mostrar_aviso(page, "Tema não encontrado", f"O tema nº {tema_nr} não foi encontrado.")
        return

    campo_titulo = ft.TextField(
        label="Tema",
        value=dados["titulo"],
        expand=True,
        min_lines=2,
        max_lines=4,
    )

    from pdf_temas import CATEGORIAS_EXIBICAO

    assuntos_conhecidos = sorted(set(CATEGORIAS_EXIBICAO.values()))
    df_assuntos_db = carregar_dados(
        "SELECT DISTINCT categoria FROM temas WHERE COALESCE(categoria, '') != ''"
    )
    assuntos = sorted(set(assuntos_conhecidos) | set(df_assuntos_db["categoria"]))
    campo_assunto = ft.Dropdown(
        label="Assunto",
        value=dados.get("categoria") or "",
        options=[
            ft.dropdown.Option(key="", text="Sem assunto"),
            *[ft.dropdown.Option(key=a, text=a) for a in assuntos],
        ],
        expand=True,
    )

    campo_notas = ft.TextField(
        label="Observações",
        value=dados["notas"],
        expand=True,
        min_lines=2,
        max_lines=5,
        hint_text="Restrições, notas ou lembretes sobre este tema",
    )
    campo_data_limite = ft.TextField(
        label="Data limite de uso",
        hint_text="Ex: 2026-09-01 (opcional)",
        value=dados["data_limite_uso"],
        width=200,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    anos_visiveis = listar_anos_colunas(apenas_visiveis=True)
    campos_ano: dict[int, ft.TextField] = {}
    linhas_anos: list[ft.Control] = []
    for item in anos_visiveis:
        ano = item["ano"]
        valor = dados["uso_por_ano"].get(ano, "")
        if valor in ("—", None):
            valor = ""
        campo = ft.TextField(
            label=str(ano),
            hint_text="MM/AAAA",
            value=valor,
            width=110,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        campos_ano[ano] = campo
        linhas_anos.append(campo)

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        titulo = (campo_titulo.value or "").strip()
        if not titulo:
            texto_erro.value = "O título do tema é obrigatório."
            texto_erro.visible = True
            page.update()
            return

        for ano, campo in campos_ano.items():
            if not _validar_mes_ano(campo.value or ""):
                texto_erro.value = f"Data inválida em {ano}. Use o formato MM/AAAA."
                texto_erro.visible = True
                page.update()
                return

        uso_por_ano = {
            ano: (campo.value or "").strip()
            for ano, campo in campos_ano.items()
        }

        try:
            salvar_tema(
                tema_nr,
                titulo,
                (campo_notas.value or "").strip(),
                (campo_data_limite.value or "").strip() or None,
                uso_por_ano,
                categoria=campo_assunto.value or "",
            )
        except Exception:
            texto_erro.value = "Não foi possível salvar o tema."
            texto_erro.visible = True
            page.update()
            return

        fechar()
        recarregar()

    conteudo_anos = []
    if linhas_anos:
        conteudo_anos = [
            ft.Text("Datas de uso por ano", weight=ft.FontWeight.W_600, size=13),
            ft.Container(height=4),
            ft.Row(linhas_anos, spacing=8, wrap=True),
            ft.Container(height=4),
        ]

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Editar tema nº {tema_nr}"),
            content=ft.Container(
                content=ft.Column(
                    [
                        campo_titulo,
                        campo_assunto,
                        campo_notas,
                        campo_data_limite,
                        *conteudo_anos,
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=520,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding.only(top=8),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Salvar", icon=ft.Icons.SAVE, on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def confirmar_exclusao_tema(
    page: ft.Page,
    recarregar: Callable[[], None],
    tema_nr: int,
) -> None:
    """Exibe confirmação e exclui o tema se o usuário confirmar."""
    dados = carregar_tema(tema_nr)
    titulo = dados["titulo"] if dados else f"tema nº {tema_nr}"
    if len(titulo) > 60:
        titulo = titulo[:57] + "..."

    def fechar(_=None):
        page.pop_dialog()

    def excluir(_=None):
        try:
            excluir_tema(tema_nr)
            fechar()
            recarregar()
        except Exception:
            fechar()
            mostrar_aviso(
                page,
                "Não foi possível excluir",
                "Este tema possui registros vinculados (oradores ou designações). "
                "Remova os vínculos antes de excluir.",
            )

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar exclusão"),
            content=ft.Text(f'Tem certeza que deseja excluir o tema nº {tema_nr}?\n\n"{titulo}"'),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton(
                    "Excluir",
                    icon=ft.Icons.DELETE,
                    on_click=excluir,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def abrir_dialog_gerenciar_anos(page: ft.Page, recarregar: Callable[[], None]) -> None:
    """Permite adicionar, ocultar/exibir ou excluir colunas de ano."""
    lista_anos = ft.Column(spacing=8, tight=True, scroll=ft.ScrollMode.AUTO)
    campo_novo_ano = ft.TextField(
        label="Adicionar ano",
        hint_text="Ex: 2029",
        width=140,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def fechar(_=None):
        page.pop_dialog()

    def atualizar_lista():
        lista_anos.controls.clear()
        for item in listar_anos_colunas(apenas_visiveis=False):
            ano = item["ano"]
            visivel = item["visivel"]

            def alternar_visibilidade(e, ano_ref=ano, novo_estado=not visivel):
                definir_visibilidade_ano_coluna(ano_ref, novo_estado)
                atualizar_lista()
                recarregar()
                page.update()

            def confirmar_exclusao(e, ano_ref=ano):
                excluir_ano_coluna(ano_ref)
                atualizar_lista()
                recarregar()
                page.update()

            lista_anos.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(str(ano), width=56, weight=ft.FontWeight.W_600),
                            ft.Text(
                                "Visível" if visivel else "Oculto",
                                size=12,
                                color=TEXTO_SECUNDARIO if visivel else COR_AVISO,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.VISIBILITY if visivel else ft.Icons.VISIBILITY_OFF,
                                tooltip="Ocultar coluna" if visivel else "Exibir coluna",
                                icon_size=20,
                                on_click=alternar_visibilidade,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip="Excluir ano e seus dados",
                                icon_size=20,
                                icon_color=COR_ERRO,
                                on_click=confirmar_exclusao,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )

    def adicionar_ano(_=None):
        valor = (campo_novo_ano.value or "").strip()
        try:
            ano = int(valor)
            if ano < 2000 or ano > 2100:
                raise ValueError
        except ValueError:
            texto_erro.value = "Informe um ano válido (ex: 2029)."
            texto_erro.visible = True
            page.update()
            return

        adicionar_ano_coluna(ano)
        campo_novo_ano.value = ""
        texto_erro.visible = False
        atualizar_lista()
        recarregar()
        page.update()

    atualizar_lista()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Gerenciar anos"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Cada ano corresponde a uma coluna da planilha. "
                            "Ocultar remove da tabela sem apagar dados; excluir apaga o ano e as datas.",
                            size=13,
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Container(height=8),
                        lista_anos,
                        ft.Container(height=12),
                        ft.Row(
                            [campo_novo_ano, ft.FilledButton("Adicionar", icon=ft.Icons.ADD, on_click=adicionar_ano)],
                            spacing=12,
                        ),
                        texto_erro,
                    ],
                    tight=True,
                    width=420,
                ),
                padding=ft.Padding.only(top=8),
            ),
            actions=[ft.TextButton("Fechar", on_click=fechar)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def tela_temas(page: ft.Page, file_picker: ft.FilePicker) -> ft.Control:
    """Catálogo de temas com colunas por ano (como na planilha)."""
    area_tabela = ft.Container(expand=True)
    texto_contagem = ft.Text(size=13, color=TEXTO_SECUNDARIO)

    def _opcoes_assunto() -> list[ft.dropdown.Option]:
        df_assuntos = carregar_dados(
            "SELECT DISTINCT categoria FROM temas "
            "WHERE COALESCE(categoria, '') != '' ORDER BY categoria"
        )
        return [
            ft.dropdown.Option(key="", text="Todos"),
            *[ft.dropdown.Option(key=c, text=c) for c in df_assuntos["categoria"]],
            ft.dropdown.Option(key="—", text="Sem assunto"),
        ]

    filtro_assunto = ft.Dropdown(
        label="Assunto",
        value="",
        options=_opcoes_assunto(),
        width=250,
    )
    filtro_uso = ft.Dropdown(
        label="Uso",
        value="",
        options=[
            ft.dropdown.Option(key="", text="Todos"),
            ft.dropdown.Option(key="nunca", text="Nunca feitos"),
            ft.dropdown.Option(key="feitos", text="Já feitos"),
        ],
        width=160,
    )
    filtro_ordem = ft.Dropdown(
        label="Ordenar por",
        value="nr",
        options=[
            ft.dropdown.Option(key="nr", text="Número"),
            ft.dropdown.Option(key="antigos", text="Há mais tempo sem fazer"),
            ft.dropdown.Option(key="recentes", text="Feitos recentemente"),
        ],
        width=230,
    )

    TEMAS_POR_PAGINA = 50
    # Cache do dataframe: consultas ao banco só quando os dados mudam de fato
    estado_temas: dict = {"df": None, "pagina": 0, "montado": False}

    texto_pagina = ft.Text(size=13, color=TEXTO_SECUNDARIO)
    botao_pag_anterior = ft.IconButton(
        icon=ft.Icons.CHEVRON_LEFT, tooltip="Página anterior", icon_size=20
    )
    botao_pag_proxima = ft.IconButton(
        icon=ft.Icons.CHEVRON_RIGHT, tooltip="Próxima página", icon_size=20
    )
    linha_paginacao = ft.Row(
        [texto_contagem, ft.Container(expand=True), botao_pag_anterior, texto_pagina, botao_pag_proxima],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
    )

    def _df_temas() -> pd.DataFrame:
        if estado_temas["df"] is None:
            estado_temas["df"] = carregar_dataframe_temas(apenas_anos_visiveis=True)
        return estado_temas["df"]

    def atualizar_view(_=None, manter_pagina: bool = False):
        if not manter_pagina:
            estado_temas["pagina"] = 0
        df = _df_temas()
        df_filtrado = filtrar_dataframe(
            df, campo_busca.value or "", _colunas_filtro_temas()
        )
        if filtro_assunto.value:
            df_filtrado = df_filtrado[df_filtrado["assunto"] == filtro_assunto.value]
        if filtro_uso.value == "nunca":
            df_filtrado = df_filtrado[df_filtrado["ultimo_uso_chave"] == ""]
        elif filtro_uso.value == "feitos":
            df_filtrado = df_filtrado[df_filtrado["ultimo_uso_chave"] != ""]
        if filtro_ordem.value == "antigos":
            # Nunca feitos primeiro (chave vazia), depois do uso mais antigo ao mais recente
            df_filtrado = df_filtrado.sort_values(["ultimo_uso_chave", "nr"])
        elif filtro_ordem.value == "recentes":
            df_filtrado = df_filtrado.sort_values(
                ["ultimo_uso_chave", "nr"], ascending=[False, True]
            )

        total = len(df_filtrado)
        paginas = max(1, -(-total // TEMAS_POR_PAGINA))
        pagina = min(estado_temas["pagina"], paginas - 1)
        estado_temas["pagina"] = pagina
        inicio = pagina * TEMAS_POR_PAGINA
        df_pagina = df_filtrado.iloc[inicio : inicio + TEMAS_POR_PAGINA]

        area_tabela.content = criar_area_tabela(
            df_pagina,
            on_editar=abrir_editar,
            on_excluir=abrir_excluir,
            config=CONFIG_TABELA_TEMAS,
        )
        if total > TEMAS_POR_PAGINA:
            fim = min(inicio + TEMAS_POR_PAGINA, total)
            texto_contagem.value = f"Exibindo {inicio + 1}–{fim} de {total} tema(s) filtrado(s) ({len(df)} no total)"
        else:
            texto_contagem.value = f"Exibindo {total} de {len(df)} tema(s)"
        texto_pagina.value = f"{pagina + 1}/{paginas}"
        botao_pag_anterior.disabled = pagina <= 0
        botao_pag_proxima.disabled = pagina >= paginas - 1
        linha_paginacao.visible = paginas > 1
        if estado_temas["montado"]:
            # Atualiza só os controles afetados — bem mais rápido que page.update()
            area_tabela.update()
            linha_paginacao.update()

    def mudar_pagina(delta: int):
        estado_temas["pagina"] += delta
        atualizar_view(manter_pagina=True)

    botao_pag_anterior.on_click = lambda _: mudar_pagina(-1)
    botao_pag_proxima.on_click = lambda _: mudar_pagina(1)

    filtro_assunto.on_select = atualizar_view
    filtro_uso.on_select = atualizar_view
    filtro_ordem.on_select = atualizar_view

    def recarregar():
        estado_temas["df"] = None  # dados mudaram: invalida o cache
        atualizar_view(manter_pagina=True)

    def abrir_editar(tema_nr: int):
        abrir_dialog_tema(page, recarregar, tema_nr)

    def abrir_excluir(tema_nr: int):
        confirmar_exclusao_tema(page, recarregar, tema_nr)

    def abrir_anos(_=None):
        abrir_dialog_gerenciar_anos(page, recarregar)

    async def importar_pdf_click(_=None):
        arquivos = await file_picker.pick_files(
            dialog_title="Selecione o formulário S-99 e/ou S-99a em PDF",
            allowed_extensions=["pdf"],
            allow_multiple=True,
        )
        if not arquivos:
            return

        resumos: list[str] = []
        erros: list[str] = []
        for arquivo in arquivos:
            try:
                resultado = importar_temas_pdf(arquivo.path)
            except Exception as exc:
                erros.append(f"{arquivo.name}: {exc}")
                continue
            resumos.append(
                f"{resultado['formulario']} — {resultado['total']} temas lidos: "
                f"{resultado['novos']} novo(s), {resultado['atualizados']} atualizado(s), "
                f"{resultado['sem_alteracao']} sem alteração."
            )

        if resumos:
            filtro_assunto.options = _opcoes_assunto()
            recarregar()
        mostrar_aviso(
            page,
            "Importação de temas" if not erros else "Importação com problemas",
            "\n\n".join([*resumos, *erros]),
        )

    def abrir_importar(_=None):
        page.run_task(importar_pdf_click)

    campo_busca = ft.TextField(
        hint_text="Buscar por número, título, assunto ou ano...",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        on_change=atualizar_view,
        **_estilo_campo_busca(),
    )

    atualizar_view()
    estado_temas["montado"] = True

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Temas",
                "Colunas por ano conforme a planilha — temas com observações aparecem destacados em azul",
            ),
            ft.Container(height=28),
            criar_secao_titulo("Catálogo"),
            ft.Container(height=12),
            ft.Row(
                [
                    campo_busca,
                    ft.FilledButton(
                        "Importar S-99/S-99a",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=abrir_importar,
                        tooltip="Preenche os temas a partir dos formulários oficiais em PDF",
                    ),
                    ft.OutlinedButton(
                        "Gerenciar",
                        icon=ft.Icons.CALENDAR_MONTH,
                        on_click=abrir_anos,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=12),
            ft.Row(
                [filtro_assunto, filtro_uso, filtro_ordem],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=8),
            linha_paginacao,
            ft.Container(height=8),
            area_tabela,
        ],
        spacing=0,
        expand=True,
    )


def tela_congregacoes(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Lista congregações com busca, cadastro, edição e exclusão."""

    def abrir_nova(_=None):
        abrir_dialog_congregacao(page, recarregar)

    def abrir_editar(congregacao_id: int):
        abrir_dialog_congregacao(page, recarregar, congregacao_id=congregacao_id)

    def abrir_excluir(congregacao_id: int):
        confirmar_exclusao_congregacao(page, recarregar, congregacao_id)

    return criar_tela_padrao(
        page=page,
        titulo="Congregações",
        descricao="Congregações do circuito e informações de reunião",
        df=carregar_dados(SQL_CONGREGACOES),
        colunas_filtro=["nome", "responsavel", "endereco", "dia_semana", "telefone"],
        barra_acoes=[
            ft.FilledButton(
                "Nova congregação",
                icon=ft.Icons.ADD,
                on_click=abrir_nova,
            ),
        ],
        on_editar=abrir_editar,
        on_excluir=abrir_excluir,
        config_tabela=CONFIG_TABELA_CONGREGACOES,
    )


def _rotulo_periodo_arranjo(mes_inicio: int, mes_fim: int) -> str:
    """Retorna rótulo legível do mês ou período do arranjo."""
    if mes_inicio == mes_fim and 1 <= mes_inicio <= 12:
        return NOMES_MESES[mes_inicio]
    if 1 <= mes_inicio <= 12 and 1 <= mes_fim <= 12:
        return f"{NOMES_MESES[mes_inicio]} — {NOMES_MESES[mes_fim]}"
    return f"{mes_inicio} — {mes_fim}"


def _opcoes_anos_arranjos() -> list[ft.dropdown.Option]:
    """Monta opções do seletor de ano (arranjos + anos adicionados manualmente)."""
    anos = set(listar_anos_arranjos()) | set(listar_anos_planejamento())
    anos.add(ANO_PADRAO_ARRANJOS)
    return [
        ft.dropdown.Option(key=str(ano), text=str(ano))
        for ano in sorted(anos, reverse=True)
    ]


def abrir_dialog_adicionar_ano(page: ft.Page, ao_concluir: Callable[[int], None]) -> None:
    """Dialog simples para adicionar um ano ao planejamento."""
    campo_ano = ft.TextField(
        label="Ano",
        hint_text="Ex: 2027",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        try:
            ano = int((campo_ano.value or "").strip())
            if ano < 2000 or ano > 2100:
                raise ValueError
        except (TypeError, ValueError):
            texto_erro.value = "Informe um ano válido (entre 2000 e 2100)."
            texto_erro.visible = True
            page.update()
            return
        adicionar_ano_planejamento(ano)
        fechar()
        ao_concluir(ano)

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Adicionar ano"),
            content=ft.Container(
                content=ft.Column([campo_ano, texto_erro], spacing=12, tight=True, width=280),
                padding=ft.Padding.only(top=8),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Adicionar", icon=ft.Icons.ADD, on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _opcoes_meses_arranjo() -> list[ft.dropdown.Option]:
    """Opções de mês para o formulário de arranjos."""
    return [
        ft.dropdown.Option(key=str(mes), text=rotulo)
        for mes, rotulo in MESES_ANO
    ]


def _linha_detalhe_arranjo(rotulo: str, valor: str, icone: str) -> ft.Control:
    """Linha de detalhe dentro de um bloco de arranjo."""
    texto = (valor or "").strip() or "—"
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(icone, size=16, color=COR_DESTAQUE),
                    ft.Text(rotulo, size=12, weight=ft.FontWeight.W_600, color=TEXTO_SECUNDARIO),
                ],
                spacing=6,
            ),
            ft.Text(texto, size=14, color=TEXTO_PRIMARIO),
        ],
        spacing=4,
    )


def _resumir_texto_tabela(texto: str, limite: int = 42) -> str:
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto or "—"
    return texto[: limite - 3] + "..."


def _criar_cabecalho_tabela_oradores() -> ft.Container:
    """Cabeçalho da tabela: Data | Orador | Tema | Ações."""
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.06, COR_DESTAQUE),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            [
                ft.Text(
                    "Data",
                    width=LARGURA_COL_DATA_MES,
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    "Orador",
                    width=LARGURA_COL_ORADOR_MES,
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    "Tema",
                    expand=True,
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    "Ações",
                    width=LARGURA_COL_ACOES_MES,
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
            ],
            spacing=ESPACO_COLUNAS_MES,
        ),
    )


def _criar_linha_orador_arranjo(
    registro: dict,
    on_editar: Callable[[dict], None],
    on_remover: Callable[[int], None],
    ultima_linha: bool = False,
    on_whatsapp: Callable[[dict], None] | None = None,
) -> ft.Container:
    """Linha da tabela: Data | Orador | Tema | Ações."""
    tema = _rotulo_tema_orador_arranjo(registro)
    data = _formatar_data_exibicao(registro.get("data"))
    if data != "—" and len(data) >= 5:
        data = data[0:5]

    return ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    data,
                    width=LARGURA_COL_DATA_MES,
                    size=13,
                    weight=ft.FontWeight.W_600,
                    color=TEXTO_PRIMARIO,
                ),
                ft.Text(
                    registro.get("orador_nome", ""),
                    size=13,
                    color=TEXTO_PRIMARIO,
                    width=LARGURA_COL_ORADOR_MES,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    tema,
                    size=13,
                    color=TEXTO_SECUNDARIO,
                    expand=True,
                ),
                ft.Row(
                    [
                        *(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.CHAT_OUTLINED,
                                    icon_size=17,
                                    tooltip="Enviar ao orador (WhatsApp)",
                                    icon_color="#34D399",
                                    style=ft.ButtonStyle(padding=4),
                                    on_click=lambda e, item=dict(registro): on_whatsapp(item),
                                )
                            ]
                            if on_whatsapp
                            else []
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_size=17,
                            tooltip="Editar",
                            icon_color=COR_DESTAQUE,
                            style=ft.ButtonStyle(padding=4),
                            on_click=lambda e, item=dict(registro): on_editar(item),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=17,
                            tooltip="Remover",
                            icon_color=COR_ERRO,
                            style=ft.ButtonStyle(padding=4),
                            on_click=lambda e, rid=int(registro["id"]): on_remover(rid),
                        ),
                    ],
                    spacing=0,
                    width=LARGURA_COL_ACOES_MES + (34 if on_whatsapp else 0),
                ),
            ],
            spacing=ESPACO_COLUNAS_MES,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border=ft.Border(
            ft.BorderSide(0, BORDA_SUAVE),
            ft.BorderSide(0, BORDA_SUAVE),
            ft.BorderSide(1 if not ultima_linha else 0, BORDA_SUAVE),
            ft.BorderSide(0, BORDA_SUAVE),
        ),
    )


def _altura_conteudo_dialog_mes(page: ft.Page) -> int:
    """Altura máxima do conteúdo rolável conforme o tamanho da janela."""
    if page.window and page.window.height:
        return max(280, min(560, int(page.window.height * 0.52)))
    return ALTURA_CONTEUDO_DIALOG_MES


def _criar_rodape_dialog_mes(
    on_fechar: Callable,
    on_editar: Callable,
    on_excluir: Callable,
) -> ft.Container:
    """Barra fixa de ações na parte inferior do dialog."""
    return ft.Container(
        content=ft.Row(
            [
                ft.TextButton("Fechar", on_click=on_fechar),
                ft.OutlinedButton(
                    content="Editar arranjo",
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=on_editar,
                ),
                ft.OutlinedButton(
                    content="Excluir arranjo",
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=on_excluir,
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
            spacing=12,
        ),
        padding=ft.Padding.symmetric(horizontal=4, vertical=4),
        border=ft.Border(top=ft.BorderSide(1, BORDA_SUAVE)),
    )


def _montar_tabela_secao(
    registros: list[dict],
    mensagem_vazia: str,
    on_editar: Callable[[dict], None],
    on_remover: Callable[[int], None],
    on_whatsapp: Callable[[dict], None] | None = None,
) -> list[ft.Control]:
    """Monta tabela simples com cabeçalho e linhas."""
    if not registros:
        return [
            ft.Text(
                mensagem_vazia,
                size=13,
                color=TEXTO_SECUNDARIO,
                italic=True,
            )
        ]

    linhas = [
        _criar_linha_orador_arranjo(
            item,
            on_editar,
            on_remover,
            ultima_linha=indice == len(registros) - 1,
            on_whatsapp=on_whatsapp,
        )
        for indice, item in enumerate(registros)
    ]
    return [
        ft.Container(
            content=ft.Column(
                [_criar_cabecalho_tabela_oradores(), *linhas],
                spacing=0,
                tight=True,
            ),
            border=ft.Border.all(1, BORDA_SUAVE),
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
    ]


def abrir_dialog_editar_orador_arranjo(
    page: ft.Page,
    registro: dict,
    atualizar_listas: Callable[[], None],
) -> None:
    """Abre formulário para editar tema e congregação de uma designação."""
    registro_id = int(registro["id"])
    tipo = registro["tipo"]
    rotulo_cong = "Origem" if tipo == "recebido" else "Destino"
    tema_atual = str(registro["tema_nr"]) if registro.get("tema_nr") else ""
    data_atual = registro.get("data") or ""

    campo_data = ft.TextField(
        label="Data",
        hint_text="DD/MM/AAAA",
        value=data_atual,
        expand=True,
    )
    campo_tema = ft.Dropdown(
        label="Tema",
        options=carregar_temas_opcoes(incluir_sem_tema=True),
        value=tema_atual,
        expand=True,
    )
    campo_congregacao = ft.Dropdown(
        label=f"Congregação ({rotulo_cong.lower()})",
        options=carregar_congregacoes_opcoes(),
        value=str(registro["congregacao_id"]) if registro.get("congregacao_id") else None,
        expand=True,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        data_norm = _normalizar_data_arranjo(campo_data.value or "")
        if not data_norm:
            texto_erro.value = "Informe uma data válida (DD/MM ou DD/MM/AAAA)."
            texto_erro.visible = True
            page.update()
            return
        try:
            tema_nr = int(campo_tema.value) if campo_tema.value else None
            congregacao_id = (
                int(campo_congregacao.value) if campo_congregacao.value else None
            )
            atualizar_orador_arranjo(registro_id, tema_nr, congregacao_id, data_norm)
        except Exception:
            texto_erro.value = "Não foi possível salvar as alterações."
            texto_erro.visible = True
            page.update()
            return
        fechar()
        atualizar_listas()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Editar — {registro.get('orador_nome', '')}"),
            content=ft.Container(
                content=ft.Column(
                    [campo_data, campo_tema, campo_congregacao, texto_erro],
                    spacing=12,
                    tight=True,
                    width=460,
                ),
                padding=ft.Padding.only(top=8),
            ),
            content_padding=ft.Padding.symmetric(horizontal=24, vertical=16),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton(
                    content="Salvar",
                    icon=ft.Icons.SAVE,
                    on_click=salvar,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


def abrir_seletor_oradores(
    page: ft.Page,
    arranjo_id: int,
    tipo: str,
    atualizar_listas: Callable[[], None],
    arranjo: dict | None = None,
) -> None:
    """Abre seletor para adicionar orador (recebido) ou designação (enviado)."""
    eh_oradores = tipo == "recebido"
    titulo_dialog = "Adicionar orador" if eh_oradores else "Adicionar designação"
    id_minha_congregacao = obter_id_minha_congregacao()
    congregacao_filtro = int(id_minha_congregacao) if not eh_oradores and id_minha_congregacao else None

    dados_arranjo = arranjo or carregar_arranjo(arranjo_id) or {
        "id": arranjo_id,
        "ano": ANO_PADRAO_ARRANJOS,
        "mes_inicio": 1,
        "dia_semana": "",
        "horario": "",
    }
    registros_mes = carregar_oradores_arranjo(arranjo_id)
    estado = {"modo": "existente", "checkboxes": [], "datas_checkbox": {}}

    campo_orador = ft.Dropdown(
        label="Orador",
        options=carregar_oradores_com_congregacao_opcoes(congregacao_filtro),
        expand=True,
    )
    campo_data_manual = ft.TextField(
        label="Data manual (opcional)",
        hint_text="DD/MM/AAAA",
        expand=True,
    )
    campo_tema = ft.Dropdown(
        label="Tema",
        options=carregar_temas_opcoes(incluir_sem_tema=eh_oradores),
        expand=True,
    )
    area_sugestoes = ft.Column(spacing=6, tight=True)
    texto_sugestoes = ft.Text(
        "Selecione o orador para ver as datas sugeridas.",
        size=12,
        color=TEXTO_SECUNDARIO,
        italic=True,
    )
    campo_nome_novo = ft.TextField(label="Nome", expand=True, visible=False)
    campo_categoria_novo = ft.Dropdown(
        label="Categoria",
        value="Ancião",
        options=[
            ft.dropdown.Option("Ancião"),
            ft.dropdown.Option("Servo Ministerial"),
        ],
        expand=True,
        visible=False,
    )
    campo_congregacao_novo = ft.Dropdown(
        label="Congregação",
        options=carregar_congregacoes_opcoes(),
        expand=True,
        visible=False,
    )
    area_existente = ft.Column([campo_orador], spacing=12, tight=True)
    area_novo = ft.Column(
        [
            campo_nome_novo,
            ft.Row([campo_categoria_novo, campo_congregacao_novo], spacing=12),
        ],
        spacing=12,
        tight=True,
        visible=False,
    )
    alternador_modo = ft.SegmentedButton(
        selected=["existente"],
        allow_empty_selection=False,
        segments=[
            ft.Segment(value="existente", label=ft.Text("Orador existente")),
            ft.Segment(value="novo", label=ft.Text("Novo orador")),
        ],
        visible=eh_oradores,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def aplicar_modo(modo: str):
        estado["modo"] = modo
        criando = modo == "novo"
        area_existente.visible = not criando
        area_novo.visible = criando
        campo_nome_novo.visible = criando
        campo_categoria_novo.visible = criando
        campo_congregacao_novo.visible = criando
        atualizar_sugestoes_datas()
        page.update()

    def mudar_modo(e):
        selecionado = e.control.selected[0] if e.control.selected else "existente"
        aplicar_modo(selecionado)

    alternador_modo.on_change = mudar_modo

    def _orador_id_selecionado() -> int | None:
        if eh_oradores and estado["modo"] == "novo":
            return None
        if not campo_orador.value:
            return None
        return int(campo_orador.value)

    def atualizar_sugestoes_datas(_=None):
        orador_id = _orador_id_selecionado()
        if orador_id is None and not (eh_oradores and estado["modo"] == "novo"):
            estado["checkboxes"] = []
            estado["datas_checkbox"] = {}
            area_sugestoes.controls = []
            texto_sugestoes.value = "Selecione o orador para ver as datas sugeridas."
            page.update()
            return

        sugestoes = _sugerir_datas_arranjo(
            dados_arranjo,
            tipo,
            registros_mes,
            orador_id=orador_id,
        )
        estado["checkboxes"] = []
        estado["datas_checkbox"] = {}
        if not sugestoes:
            area_sugestoes.controls = [
                ft.Text(
                    "Nenhuma data disponível neste mês.",
                    size=12,
                    color=TEXTO_SECUNDARIO,
                    italic=True,
                )
            ]
            texto_sugestoes.value = "Datas sugeridas"
            page.update()
            return

        linhas: list[ft.Control] = []
        for item in sugestoes:
            checkbox = ft.Checkbox(label=item["rotulo"], value=False)
            estado["datas_checkbox"][id(checkbox)] = item["data"]
            estado["checkboxes"].append(checkbox)
            linhas.append(checkbox)

        area_sugestoes.controls = linhas
        reunioes = _obter_reunioes_dialog(dados_arranjo)
        texto_sugestoes.value = (
            f"Datas sugeridas ({len(sugestoes)}) — {_formatar_linha_reunioes(reunioes)}"
        )
        page.update()

    def preencher_datas_automaticamente(_=None):
        if not estado["checkboxes"]:
            atualizar_sugestoes_datas()
        for checkbox in estado["checkboxes"]:
            checkbox.value = True
        page.update()

    def ao_mudar_orador(_=None):
        atualizar_sugestoes_datas()

    campo_orador.on_select = ao_mudar_orador

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        texto_erro.visible = False
        datas_selecionadas = [
            estado["datas_checkbox"][id(cb)]
            for cb in estado["checkboxes"]
            if cb.value and id(cb) in estado["datas_checkbox"]
        ]
        data_manual = _normalizar_data_arranjo(campo_data_manual.value or "")
        if data_manual and data_manual not in datas_selecionadas:
            datas_selecionadas.append(data_manual)

        if not datas_selecionadas:
            texto_erro.value = "Selecione ao menos uma data sugerida ou informe manualmente."
            texto_erro.visible = True
            page.update()
            return
        if not eh_oradores and not campo_tema.value:
            texto_erro.value = "Selecione um tema."
            texto_erro.visible = True
            page.update()
            return

        try:
            if eh_oradores and estado["modo"] == "novo":
                nome = (campo_nome_novo.value or "").strip()
                if not nome:
                    texto_erro.value = "Informe o nome do orador."
                    texto_erro.visible = True
                    page.update()
                    return
                if not campo_congregacao_novo.value:
                    texto_erro.value = "Selecione a congregação."
                    texto_erro.visible = True
                    page.update()
                    return
                orador_id = inserir_orador(
                    nome,
                    "",
                    campo_categoria_novo.value or "Ancião",
                    int(campo_congregacao_novo.value),
                )
            else:
                if not campo_orador.value:
                    texto_erro.value = "Selecione um orador."
                    texto_erro.visible = True
                    page.update()
                    return
                orador_id = int(campo_orador.value)

            tema_nr = int(campo_tema.value) if campo_tema.value else None
            for data_norm in datas_selecionadas:
                adicionar_orador_arranjo(
                    arranjo_id,
                    tipo,
                    orador_id,
                    tema_nr,
                    data=data_norm,
                )
        except Exception:
            texto_erro.value = "Não foi possível adicionar. Verifique se já existe nesta data."
            texto_erro.visible = True
            page.update()
            return
        fechar()
        atualizar_listas()

    conteudo = [alternador_modo] if eh_oradores else []
    conteudo.extend(
        [
            area_existente,
            area_novo,
            campo_tema,
            ft.Container(height=4),
            texto_sugestoes,
            area_sugestoes,
            ft.OutlinedButton(
                content="Preencher datas automaticamente",
                icon=ft.Icons.EVENT_AVAILABLE,
                on_click=preencher_datas_automaticamente,
            ),
            campo_data_manual,
            texto_erro,
        ]
    )

    try:
        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(titulo_dialog, size=18, weight=ft.FontWeight.W_600),
                content=ft.Container(
                    content=ft.Column(
                        conteudo,
                        spacing=12,
                        tight=True,
                        width=560,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=ft.Padding.only(top=8),
                ),
                content_padding=ft.Padding.symmetric(horizontal=24, vertical=16),
                actions=[
                    ft.TextButton("Cancelar", on_click=fechar),
                    ft.FilledButton(
                        content="Adicionar",
                        icon=ft.Icons.ADD,
                        on_click=salvar,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )
        page.update()
    except Exception:
        mostrar_aviso(page, "Erro", "Não foi possível abrir o seletor de oradores.")


def _ordenar_registros_por_data(registros: list[dict]) -> list[dict]:
    """Ordena registros de arranjo por data DD/MM/AAAA."""

    def chave(registro: dict) -> tuple[str, str, str]:
        partes = (registro.get("data") or "").split("/")
        if len(partes) == 3:
            return partes[2], partes[1], partes[0]
        return "9999", "99", "99"

    return sorted(registros, key=chave)


def _resumir_tema_selecao_exportacao(registro: dict, limite: int = 72) -> str:
    tema = _rotulo_tema_orador_arranjo(registro)
    if len(tema) <= limite:
        return tema
    return tema[: limite - 3] + "..."


def abrir_dialog_selecao_exportacao_png(
    page: ft.Page,
    arranjo: dict,
    reunioes: dict,
    registros: list[dict],
    file_picker: ft.FilePicker,
    titulo_secao: str = "Oradores",
    prefixo_arquivo: str = "Oradores",
) -> None:
    """Abre dialog para escolher quais itens incluir na exportação PNG."""
    estado: dict = {"checkboxes": [], "por_checkbox": {}}

    def fechar(_=None):
        page.pop_dialog()

    def criar_linha_selecao(registro: dict) -> ft.Control:
        data = _formatar_data_exibicao(registro.get("data"))
        if data != "—" and len(data) >= 5:
            data = data[0:5]
        nome = registro.get("orador_nome") or "—"
        tema = _resumir_tema_selecao_exportacao(registro)
        checkbox = ft.Checkbox(value=True)
        estado["checkboxes"].append(checkbox)
        estado["por_checkbox"][id(checkbox)] = registro
        return ft.Container(
            content=ft.Row(
                [
                    checkbox,
                    ft.Column(
                        [
                            ft.Text(
                                nome,
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=TEXTO_PRIMARIO,
                            ),
                            ft.Text(
                                f"{data} · {tema}",
                                size=12,
                                color=TEXTO_SECUNDARIO,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.symmetric(vertical=6),
        )

    lista_selecao = ft.Column(
        [criar_linha_selecao(r) for r in _ordenar_registros_por_data(registros)],
        spacing=0,
        tight=True,
        scroll=ft.ScrollMode.AUTO,
    )
    texto_erro = ft.Text("", color=COR_ERRO, size=13, visible=False)

    async def gerar_imagem(_=None):
        selecionados = [
            estado["por_checkbox"][id(cb)]
            for cb in estado["checkboxes"]
            if cb.value and id(cb) in estado["por_checkbox"]
        ]
        if not selecionados:
            texto_erro.value = "Selecione ao menos um item para exportar."
            texto_erro.visible = True
            page.update()
            return

        try:
            pasta = await file_picker.get_directory_path(
                dialog_title="Escolha a pasta para salvar a imagem",
                initial_directory=str(Path("exports").resolve()),
            )
            if not pasta:
                return

            caminho, erro = gerar_png_oradores(
                arranjo,
                reunioes,
                selecionados,
                pasta_destino=pasta,
                titulo_secao=titulo_secao,
                prefixo_arquivo=prefixo_arquivo,
            )
            if erro:
                texto_erro.value = erro
                texto_erro.visible = True
                page.update()
                return

            fechar()
            abrir_pasta_do_arquivo(caminho)
            mostrar_aviso(
                page,
                "Imagem exportada",
                f"A imagem foi salva em:\n{caminho}",
            )
        except Exception as exc:
            texto_erro.value = f"Não foi possível gerar a imagem. Detalhes: {exc}"
            texto_erro.visible = True
            page.update()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Exportar {titulo_secao} — selecionar itens"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Desmarque os itens que não devem aparecer na imagem.",
                            size=13,
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Container(height=8),
                        ft.Container(
                            content=lista_selecao,
                            height=360,
                            border=ft.Border.all(1, BORDA_SUAVE),
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ),
                        texto_erro,
                    ],
                    spacing=0,
                    tight=True,
                    width=520,
                ),
                padding=ft.Padding.only(top=8),
            ),
            content_padding=ft.Padding.symmetric(horizontal=24, vertical=16),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton(
                    content="Gerar Imagem PNG",
                    icon=ft.Icons.IMAGE_OUTLINED,
                    on_click=gerar_imagem,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


def _chave_data_br(data_str: str) -> tuple[str, str, str]:
    return (data_str[6:10], data_str[3:5], data_str[0:2])


def preencher_presidentes_rodizio(ano: int, mes: int) -> int:
    """Preenche as semanas sem presidente do mês por rodízio justo.

    Para cada data vazia, escolhe quem presidiu há mais tempo (ou nunca),
    desempatando pela ordem do rodízio. Assim respeita a sequência inicial
    quando está tudo vazio, mas se adapta a mudanças manuais — evitando
    repetir alguém recém-designado. Pula datas especiais e respeita as
    atribuições já feitas. Retorna quantas semanas foram preenchidas.
    """
    cadastro = listar_presidentes_cadastro()
    if not cadastro:
        return 0
    ordem_pos = {item["id"]: indice for indice, item in enumerate(cadastro)}
    ids = [item["id"] for item in cadastro]

    especiais = listar_datas_especiais_por_ano(ano)
    datas = _semanas_reuniao_mes(ano, mes)
    if not datas:
        return 0

    # Histórico completo (todos os anos), como {chave ordenável: presidente_id}
    designacoes = {
        _chave_data_br(data_str): pid
        for data_str, pid in carregar_todas_designacoes_presidente().items()
    }

    preenchidas = 0
    for data_ref in datas:
        data_str = _formatar_data_arranjo(data_ref)
        chave = _chave_data_br(data_str)
        if data_str in especiais or chave in designacoes:
            continue

        # Última vez que cada candidato presidiu antes desta data
        ultima: dict[int, tuple] = {}
        for k, pid in designacoes.items():
            if k < chave and pid in ordem_pos and k > ultima.get(pid, ()):
                ultima[pid] = k

        # Quem presidiu há mais tempo (ou nunca); desempate pela ordem do rodízio
        escolhido = min(ids, key=lambda pid: (ultima.get(pid, ()), ordem_pos[pid]))
        salvar_presidente(data_str, escolhido)
        designacoes[chave] = escolhido
        preenchidas += 1
    return preenchidas


def abrir_dialog_gerenciar_tipos_evento(
    page: ft.Page,
    ao_fechar: Callable[[], None],
) -> None:
    """Adicionar e remover tipos de evento especial."""
    lista = ft.Column(spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, height=220)
    campo_nome = ft.TextField(label="Novo tipo", hint_text="Ex: Escola de Pioneiros", expand=True)
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def preencher():
        tipos = listar_tipos_evento()
        if not tipos:
            lista.controls = [
                ft.Text("Nenhum tipo cadastrado.", size=13, color=TEXTO_SECUNDARIO, italic=True)
            ]
            return

        def linha_tipo(item: dict) -> ft.Control:
            def excluir(_=None, item=item):
                excluir_tipo_evento(item["id"])
                preencher()
                page.update()

            return ft.Row(
                [
                    ft.Text(item["nome"], size=14, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        icon_color=COR_ERRO,
                        tooltip="Remover (datas já cadastradas não mudam)",
                        on_click=excluir,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        lista.controls = [linha_tipo(item) for item in tipos]

    def adicionar(_=None):
        nome = (campo_nome.value or "").strip()
        if not nome:
            texto_erro.value = "Informe o nome do tipo."
            texto_erro.visible = True
            page.update()
            return
        adicionar_tipo_evento(nome)
        campo_nome.value = ""
        texto_erro.visible = False
        preencher()
        page.update()

    def fechar(_=None):
        page.pop_dialog()
        ao_fechar()

    preencher()
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Tipos de evento"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                campo_nome,
                                ft.FilledButton("Adicionar", icon=ft.Icons.ADD, on_click=adicionar),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        texto_erro,
                        ft.Container(height=8),
                        lista,
                    ],
                    spacing=8,
                    tight=True,
                    width=420,
                ),
                padding=ft.Padding.only(top=8),
            ),
            actions=[ft.TextButton("Fechar", on_click=fechar)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def abrir_dialog_data_especial(
    page: ft.Page,
    ano: int,
    mes: int,
    ao_concluir: Callable[[], None],
    registro: dict | None = None,
) -> None:
    """Cadastra/edita uma data especial: tipo, orador, tema e presidente opcionais."""
    editando = registro is not None
    datas_mes = [_formatar_data_arranjo(d) for d in _semanas_reuniao_mes(ano, mes)]
    if editando and registro["data"] not in datas_mes:
        datas_mes.insert(0, registro["data"])

    campo_data = ft.Dropdown(
        label="Data",
        options=[ft.dropdown.Option(d) for d in datas_mes],
        value=registro["data"] if editando else None,
        expand=True,
    )
    tipos = [item["nome"] for item in listar_tipos_evento()]
    if editando and registro["tipo"] not in tipos:
        tipos.insert(0, registro["tipo"])
    campo_tipo = ft.Dropdown(
        label="Tipo de evento",
        options=[ft.dropdown.Option(tipo) for tipo in tipos],
        value=registro["tipo"] if editando else (tipos[0] if tipos else None),
        expand=True,
    )

    def atualizar_tipos():
        atuais = [item["nome"] for item in listar_tipos_evento()]
        campo_tipo.options = [ft.dropdown.Option(tipo) for tipo in atuais]
        if campo_tipo.value not in atuais and atuais:
            campo_tipo.value = atuais[0]
        page.update()

    def abrir_gerenciar_tipos(_=None):
        abrir_dialog_gerenciar_tipos_evento(page, atualizar_tipos)
    campo_orador = ft.TextField(
        label="Orador (opcional)",
        hint_text="Deixe vazio se não houver discurso",
        value=registro["orador"] if editando else "",
        expand=True,
    )
    campo_tema = ft.TextField(
        label="Tema (opcional)",
        hint_text="Ex: tema do discurso do superintendente",
        value=registro["tema"] if editando else "",
        expand=True,
    )
    campo_congregacao = ft.Dropdown(
        label="Congregação do orador (opcional)",
        hint_text="Aparece no quadro quando houver discurso",
        options=[
            ft.dropdown.Option(key="", text="— Sem congregação"),
            *carregar_congregacoes_opcoes(),
        ],
        value=str(registro["congregacao_id"]) if editando and registro.get("congregacao_id") else "",
        expand=True,
    )

    df_oradores_cong = carregar_dados(
        "SELECT nome, congregacao_id FROM oradores WHERE congregacao_id IS NOT NULL"
    )
    mapa_orador_cong = {
        _normalizar_texto_busca(row.nome): str(int(row.congregacao_id))
        for row in df_oradores_cong.itertuples()
    }

    def ao_mudar_orador(_=None):
        # Auto-preenche a congregação se o orador digitado for um cadastrado
        # e nenhuma congregação tiver sido escolhida ainda.
        if campo_congregacao.value:
            return
        chave = _normalizar_texto_busca(campo_orador.value or "")
        cong_id = mapa_orador_cong.get(chave)
        if cong_id:
            campo_congregacao.value = cong_id
            page.update()

    campo_orador.on_change = ao_mudar_orador

    campo_presidente = ft.Dropdown(
        label="Presidente (opcional)",
        options=[
            ft.dropdown.Option(key="", text="— Sem presidente"),
            *[
                ft.dropdown.Option(
                    key=str(item["id"]),
                    text=f"{item['nome']} ({item['categoria']})",
                )
                for item in listar_presidentes_cadastro()
            ],
        ],
        value=str(registro["presidente_id"]) if editando and registro.get("presidente_id") else "",
        expand=True,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        if not campo_data.value:
            texto_erro.value = "Selecione a data."
            texto_erro.visible = True
            page.update()
            return
        try:
            salvar_data_especial(
                campo_data.value,
                campo_tipo.value or (campo_tipo.options[0].key if campo_tipo.options else "Evento"),
                (campo_orador.value or "").strip(),
                (campo_tema.value or "").strip(),
                int(campo_presidente.value) if campo_presidente.value else None,
                registro_id=registro["id"] if editando else None,
                congregacao_id=int(campo_congregacao.value) if campo_congregacao.value else None,
            )
        except Exception:
            texto_erro.value = "Não foi possível salvar esta data especial."
            texto_erro.visible = True
            page.update()
            return
        fechar()
        ao_concluir()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar data especial" if editando else "Nova data especial"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                campo_data,
                                campo_tipo,
                                ft.IconButton(
                                    icon=ft.Icons.SETTINGS_OUTLINED,
                                    tooltip="Gerenciar tipos de evento",
                                    on_click=abrir_gerenciar_tipos,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        campo_orador,
                        campo_tema,
                        campo_congregacao,
                        campo_presidente,
                        ft.Text(
                            "Sem orador nem tema, o tipo do evento aparece no lugar do "
                            "orador no Quadro de Anúncios. Com discurso, mostra o orador, "
                            "o tema e a congregação escolhida.",
                            size=12,
                            color=TEXTO_SECUNDARIO,
                        ),
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=520,
                ),
                padding=ft.Padding.only(top=8),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Salvar", icon=ft.Icons.SAVE, on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


async def _dialog_whatsapp_designacao_envio(page: ft.Page, designacao: dict):
    """Gera o PNG da designação enviada e oferece compartilhar no WhatsApp."""
    try:
        caminho, erro = gerar_png_designacao_envio(designacao)
        if erro:
            mostrar_aviso(page, "Erro ao gerar imagem", erro)
            return

        def fechar_dialog(_=None):
            page.pop_dialog()

        def abrir_whatsapp_web(_=None):
            dia = (designacao.get("dia_semana") or "").strip()
            horario = (designacao.get("horario") or "").strip()
            reuniao = f"{dia}, {horario}" if dia and horario else (dia or horario or "—")
            responsavel = (designacao.get("responsavel") or "").strip()
            telefone = (designacao.get("telefone") or "").strip()
            contato = (
                f"{responsavel} - {telefone}" if responsavel and telefone
                else (responsavel or telefone or "—")
            )
            mensagem = (
                f"📋 *Designação para Discurso Público*\n\n"
                f"📅 *Data:* {_formatar_data_exibicao(designacao.get('data', ''))}\n"
                f"🎤 *Orador:* {designacao.get('orador', '')}\n"
                f"📖 *Tema:* {designacao.get('tema', '')}\n"
                f"🏛️ *Congregação:* {designacao.get('congregacao', '')}\n"
                f"⏰ *Reunião:* {reuniao}\n"
                f"📍 *Endereço:* {designacao.get('endereco', '')}\n"
                f"☎️ *Contato:* {contato}\n\n"
                f"_Enviado via Gestão de Arranjo_"
            )
            config = carregar_configuracao()
            tel = config.get("telefone_coordenador", "")
            if tel:
                webbrowser.open(gerar_link_whatsapp(tel, mensagem))
            else:
                page.set_clipboard(mensagem)
                mostrar_sucesso(page, "Mensagem copiada — cole no WhatsApp e anexe a imagem.")
            fechar_dialog()

        def abrir_pasta(_=None):
            abrir_pasta_do_arquivo(caminho)
            fechar_dialog()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Imagem gerada"),
                content=ft.Text(f"A imagem foi salva em:\n{caminho}", size=13, color=TEXTO_SECUNDARIO),
                actions=[
                    ft.TextButton("Fechar", on_click=fechar_dialog),
                    ft.OutlinedButton("Abrir pasta", icon=ft.Icons.FOLDER_OPEN, on_click=abrir_pasta),
                    ft.FilledButton(
                        "Enviar pelo WhatsApp",
                        icon=ft.Icons.CHAT,
                        style=ft.ButtonStyle(bgcolor="#25D366", color="#FFFFFF"),
                        on_click=abrir_whatsapp_web,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )
        page.update()
    except Exception as exc:
        mostrar_aviso(page, "Erro", f"Não foi possível gerar a imagem: {exc}")


def _abrir_whatsapp_designacao_envio(page: ft.Page, registro: dict) -> None:
    """Prepara os dados da designação enviada (com a congregação de destino)."""
    cong = None
    if registro.get("congregacao_id"):
        cong = carregar_congregacao(int(registro["congregacao_id"]))
    cong = cong or {}
    designacao = {
        "data": registro.get("data") or "",
        "orador": registro.get("orador_nome", ""),
        "tema": _rotulo_tema_orador_arranjo(registro),
        "congregacao": cong.get("nome") or registro.get("congregacao_nome", ""),
        "dia_semana": cong.get("dia_semana", ""),
        "horario": cong.get("horario", ""),
        "endereco": cong.get("endereco", ""),
        "responsavel": cong.get("responsavel", ""),
        "telefone": cong.get("telefone", ""),
    }
    page.run_task(_dialog_whatsapp_designacao_envio, page, designacao)


def abrir_dialog_oradores_mes(
    page: ft.Page,
    arranjo: dict,
    on_editar_arranjo: Callable[[int], None],
    on_excluir_arranjo: Callable[[int], None],
    file_picker: ft.FilePicker,
) -> None:
    """Dialog do mês com abas: Oradores, Designações e Presidentes."""
    arranjo_id = int(arranjo["id"])
    mes = int(arranjo["mes_inicio"])
    ano = int(arranjo["ano"])
    titulo_mes = f"{_rotulo_periodo_arranjo(mes, mes)} {ano}"

    reunioes = _obter_reunioes_dialog(arranjo)
    linha_reunioes = _formatar_linha_reunioes(reunioes)

    lista_recebidos = ft.Column(spacing=0, tight=True)
    lista_enviados = ft.Column(spacing=0, tight=True)
    lista_presidentes = ft.Column(spacing=12, tight=True)
    lista_especiais = ft.Column(spacing=8, tight=True)
    altura_conteudo = _altura_conteudo_dialog_mes(page)

    def fechar(_=None):
        page.pop_dialog()

    def remover_orador(registro_id: int):
        try:
            remover_orador_arranjo(registro_id)
            atualizar_listas()
        except Exception:
            mostrar_aviso(page, "Erro", "Não foi possível remover o orador.")

    def editar_orador(item: dict):
        abrir_dialog_editar_orador_arranjo(page, item, atualizar_listas)

    def whatsapp_designacao(item: dict):
        _abrir_whatsapp_designacao_envio(page, item)

    def preencher_listas():
        registros = carregar_oradores_arranjo(arranjo_id)
        recebidos = [r for r in registros if r["tipo"] == "recebido"]
        enviados = [r for r in registros if r["tipo"] == "enviado"]

        lista_recebidos.controls = _montar_tabela_secao(
            recebidos,
            "Nenhum orador cadastrado.",
            editar_orador,
            remover_orador,
        )
        lista_enviados.controls = _montar_tabela_secao(
            enviados,
            "Nenhuma designação cadastrada.",
            editar_orador,
            remover_orador,
            on_whatsapp=whatsapp_designacao,
        )
        preencher_presidentes()
        preencher_especiais()

    def preencher_especiais():
        especiais_ano = listar_datas_especiais_por_ano(ano)
        do_mes = sorted(
            (
                registro
                for data_str, registro in especiais_ano.items()
                if len(data_str) == 10 and int(data_str[3:5]) == mes
            ),
            key=lambda r: r["data"],
        )
        if not do_mes:
            lista_especiais.controls = [
                ft.Text(
                    "Nenhuma data especial neste mês.",
                    size=13,
                    color=TEXTO_SECUNDARIO,
                    italic=True,
                )
            ]
            return

        def linha_especial(registro: dict) -> ft.Control:
            def editar(_=None, registro=registro):
                abrir_dialog_data_especial(page, ano, mes, atualizar_listas, registro)

            def excluir(_=None, registro=registro):
                excluir_data_especial(registro["id"])
                atualizar_listas()

            detalhes = " · ".join(
                parte
                for parte in (
                    registro.get("orador") or "",
                    _resumir_texto_tabela(registro.get("tema") or "", 40),
                    f"Pres.: {registro['presidente_nome']}" if registro.get("presidente_nome") else "",
                )
                if parte
            ) or "sem orador nem presidente"

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Text(
                            registro["data"][:5],
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO,
                            width=52,
                        ),
                        ft.Container(
                            content=ft.Text(
                                registro["tipo"],
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=COR_AVISO,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.13, COR_AVISO),
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                        ),
                        ft.Text(
                            detalhes,
                            size=12,
                            color=TEXTO_SECUNDARIO,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_size=17,
                            tooltip="Editar",
                            icon_color=COR_DESTAQUE,
                            on_click=editar,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=17,
                            tooltip="Excluir",
                            icon_color=COR_ERRO,
                            on_click=excluir,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border=ft.Border.all(1, BORDA_SUAVE),
                border_radius=8,
            )

        lista_especiais.controls = [linha_especial(registro) for registro in do_mes]

    def preencher_presidentes():
        datas = _semanas_reuniao_mes(ano, mes)
        presidentes = carregar_presidentes_por_ano(ano)
        cadastro = listar_presidentes_cadastro()

        if not cadastro:
            lista_presidentes.controls = [
                ft.Text(
                    "Nenhum presidente cadastrado ainda. "
                    "Cadastre-os na aba Ajustes → Gerenciar presidentes.",
                    size=13,
                    color=TEXTO_SECUNDARIO,
                    italic=True,
                )
            ]
            return

        opcoes = [
            ft.dropdown.Option(key=str(item["id"]), text=f"{item['nome']} ({item['categoria']})")
            for item in cadastro
        ]
        linhas: list[ft.Control] = []
        for data_ref in datas:
            data_str = _formatar_data_arranjo(data_ref)
            atual = presidentes.get(data_str)
            campo = ft.Dropdown(
                label="Presidente",
                options=opcoes,
                value=str(atual["presidente_id"]) if atual else None,
                expand=True,
            )

            def ao_mudar(e, data_ref=data_str, campo=campo):
                if campo.value:
                    salvar_presidente(data_ref, int(campo.value))
                else:
                    excluir_presidente(data_ref)

            campo.on_select = ao_mudar

            def ao_remover(e, data_ref=data_str, campo=campo):
                excluir_presidente(data_ref)
                campo.value = None
                page.update()

            linhas.append(
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(
                                f"{_rotulo_weekday(data_ref.weekday())}, "
                                f"{data_ref.day:02d}/{data_ref.month:02d}",
                                size=13,
                                weight=ft.FontWeight.W_600,
                            ),
                            width=170,
                        ),
                        campo,
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=18,
                            icon_color=COR_ERRO,
                            tooltip="Remover presidente desta data",
                            on_click=ao_remover,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        lista_presidentes.controls = linhas

    def atualizar_listas():
        preencher_listas()
        page.update()

    def _abrir_selecao_exportacao_png(tipo: str, titulo_secao: str, prefixo_arquivo: str):
        registros = carregar_oradores_arranjo(arranjo_id)
        filtrados = [r for r in registros if r["tipo"] == tipo]
        if tipo == "recebido":
            especiais_ano = listar_datas_especiais_por_ano(ano)
            for data_str, esp in especiais_ano.items():
                if len(data_str) == 10 and int(data_str[3:5]) == mes:
                    filtrados.append(
                        {
                            "id": -int(esp["id"]),
                            "tipo": "recebido",
                            "orador_id": None,
                            "tema_nr": None,
                            "congregacao_id": None,
                            "data": data_str,
                            "orador_nome": esp["tipo"],
                            "tema_titulo": esp.get("tema") or "",
                            "congregacao_nome": "",
                            "especial": True,
                        }
                    )
        if not filtrados:
            mostrar_aviso(
                page,
                "Não foi possível exportar",
                f"Não há {titulo_secao.lower()} cadastrados para exportar neste mês.",
            )
            return
        abrir_dialog_selecao_exportacao_png(
            page,
            arranjo,
            reunioes,
            filtrados,
            file_picker,
            titulo_secao=titulo_secao,
            prefixo_arquivo=prefixo_arquivo,
        )

    def exportar_png_oradores(_=None):
        _abrir_selecao_exportacao_png("recebido", "Oradores", "Oradores")

    def exportar_png_designacoes(_=None):
        _abrir_selecao_exportacao_png("enviado", "Designações", "Designacoes")

    def abrir_adicionar_orador(_=None):
        abrir_seletor_oradores(
            page, arranjo_id, "recebido", atualizar_listas, arranjo=arranjo
        )

    def abrir_adicionar_designacao(_=None):
        abrir_seletor_oradores(
            page, arranjo_id, "enviado", atualizar_listas, arranjo=arranjo
        )

    def editar_arranjo(_=None):
        fechar()
        on_editar_arranjo(arranjo_id)

    def excluir_arranjo(_=None):
        fechar()
        on_excluir_arranjo(arranjo_id)

    def _cabecalho_secao(titulo: str, on_exportar, on_adicionar) -> ft.Row:
        return ft.Row(
            [
                ft.Text(titulo, size=16, weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO, expand=True),
                ft.OutlinedButton(
                    content="Exportar PNG",
                    icon=ft.Icons.IMAGE_OUTLINED,
                    on_click=on_exportar,
                ),
                ft.FilledButton(content="Adicionar", icon=ft.Icons.ADD, on_click=on_adicionar),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    secao_recebidos = ft.Column(
        [
            _cabecalho_secao("Oradores recebidos", exportar_png_oradores, abrir_adicionar_orador),
            ft.Container(height=12),
            lista_recebidos,
        ],
        spacing=0,
        tight=True,
    )
    secao_enviados = ft.Column(
        [
            _cabecalho_secao("Designações enviadas", exportar_png_designacoes, abrir_adicionar_designacao),
            ft.Container(height=12),
            lista_enviados,
        ],
        spacing=0,
        tight=True,
        visible=False,
    )
    def preencher_rodizio(_=None):
        preenchidas = preencher_presidentes_rodizio(ano, mes)
        if preenchidas:
            mostrar_sucesso(page, f"{preenchidas} semana(s) preenchida(s) pelo rodízio.")
            atualizar_listas()
        else:
            mostrar_aviso(
                page,
                "Nada para preencher",
                "Todas as semanas já têm presidente (ou não há presidentes cadastrados). "
                "A ordem do rodízio é definida em Ajustes → Gerenciar presidentes.",
            )

    def refazer_rodizio(_=None):
        def fechar(_=None):
            page.pop_dialog()

        def confirmar(_=None):
            fechar()
            for data_ref in _semanas_reuniao_mes(ano, mes):
                data_str = _formatar_data_arranjo(data_ref)
                if data_str not in listar_datas_especiais_por_ano(ano):
                    excluir_presidente(data_str)
            preenchidas = preencher_presidentes_rodizio(ano, mes)
            mostrar_sucesso(page, f"Rodízio refeito: {preenchidas} semana(s).")
            atualizar_listas()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Refazer rodízio do mês"),
                content=ft.Text(
                    "Isto apaga os presidentes já designados neste mês e refaz o "
                    "rodízio do zero, evitando repetir quem presidiu há pouco.\n\n"
                    "Ajustes manuais deste mês serão perdidos. Continuar?",
                    size=13,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=fechar),
                    ft.FilledButton("Refazer", icon=ft.Icons.AUTORENEW, on_click=confirmar),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    secao_presidentes = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        "Quem preside a reunião de fim de semana em cada data",
                        size=13,
                        color=TEXTO_SECUNDARIO,
                        expand=True,
                    ),
                    ft.TextButton(
                        content="Refazer",
                        icon=ft.Icons.RESTART_ALT,
                        on_click=refazer_rodizio,
                    ),
                    ft.OutlinedButton(
                        content="Preencher em rodízio",
                        icon=ft.Icons.AUTORENEW,
                        on_click=preencher_rodizio,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=12),
            lista_presidentes,
        ],
        spacing=0,
        tight=True,
        visible=False,
    )

    def abrir_adicionar_especial(_=None):
        abrir_dialog_data_especial(page, ano, mes, atualizar_listas)

    secao_especiais = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        "Assembleias, congressos, visitas e outros eventos que "
                        "substituem a reunião normal",
                        size=13,
                        color=TEXTO_SECUNDARIO,
                        expand=True,
                    ),
                    ft.FilledButton(
                        content="Adicionar",
                        icon=ft.Icons.ADD,
                        on_click=abrir_adicionar_especial,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=12),
            lista_especiais,
        ],
        spacing=0,
        tight=True,
        visible=False,
    )

    def mudar_aba(e):
        selecionada = e.control.selected[0] if e.control.selected else "recebidos"
        secao_recebidos.visible = selecionada == "recebidos"
        secao_enviados.visible = selecionada == "enviados"
        secao_presidentes.visible = selecionada == "presidentes"
        secao_especiais.visible = selecionada == "especiais"
        page.update()

    alternador_abas = ft.SegmentedButton(
        selected=["recebidos"],
        allow_empty_selection=False,
        on_change=mudar_aba,
        segments=[
            ft.Segment(value="recebidos", label=ft.Text("Oradores")),
            ft.Segment(value="enviados", label=ft.Text("Designações")),
            ft.Segment(value="presidentes", label=ft.Text("Presidentes")),
            ft.Segment(value="especiais", label=ft.Text("Especiais")),
        ],
    )

    dialog_mes = ft.AlertDialog(
        modal=True,
        title=ft.Column(
            [
                ft.Text(
                    f"{titulo_mes} — {reunioes['host_nome']}",
                    size=20,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(linha_reunioes, size=13, color=TEXTO_SECUNDARIO),
            ],
            spacing=6,
            tight=True,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    alternador_abas,
                    ft.Container(height=16),
                    secao_recebidos,
                    secao_enviados,
                    secao_presidentes,
                    secao_especiais,
                ],
                spacing=0,
                tight=True,
                width=LARGURA_DIALOG_MES,
                scroll=ft.ScrollMode.AUTO,
            ),
            height=altura_conteudo,
            padding=ft.Padding.symmetric(horizontal=4, vertical=8),
        ),
        content_padding=ft.Padding.symmetric(horizontal=32, vertical=24),
        inset_padding=ft.Padding.all(40),
        actions=[
            _criar_rodape_dialog_mes(fechar, editar_arranjo, excluir_arranjo),
        ],
        actions_padding=ft.Padding.symmetric(horizontal=32, vertical=16),
    )
    preencher_listas()
    page.show_dialog(dialog_mes)
    page.update()


def abrir_dialog_arranjo(
    page: ft.Page,
    recarregar: Callable[[], None],
    arranjo_id: int | None = None,
    ano_padrao: int = ANO_PADRAO_ARRANJOS,
    mes_padrao: int | None = None,
) -> None:
    """Abre dialog para cadastrar ou editar um arranjo mensal."""
    dados = carregar_arranjo(arranjo_id) if arranjo_id else None
    editando = dados is not None

    mes_inicial = None
    if dados:
        mes_inicial = str(dados["mes_inicio"])
    elif mes_padrao:
        mes_inicial = str(mes_padrao)

    campo_ano = ft.TextField(
        label="Ano",
        value=str(dados["ano"] if dados else ano_padrao),
        width=120,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    campo_mes = ft.Dropdown(
        label="Mês",
        options=_opcoes_meses_arranjo(),
        value=mes_inicial,
        expand=True,
    )
    campo_congregacao = ft.Dropdown(
        label="Congregação anfitriã",
        options=carregar_congregacoes_opcoes(),
        value=dados["congregacao_host_id"] if dados else None,
        expand=True,
    )
    campo_responsavel = ft.TextField(
        label="Responsável / Contato",
        value=dados["responsavel"] if dados else "",
        expand=True,
    )
    campo_telefone = ft.TextField(
        label="Telefone",
        value=dados["telefone"] if dados else "",
        expand=True,
    )
    campo_dia = ft.TextField(
        label="Dia da reunião",
        hint_text="Ex: Domingo",
        value=dados["dia_semana"] if dados else "",
        expand=True,
    )
    campo_horario = ft.TextField(
        label="Horário",
        hint_text="Ex: 18:30",
        value=dados["horario"] if dados else "",
        expand=True,
    )
    campo_endereco = ft.TextField(
        label="Endereço",
        value=dados["endereco"] if dados else "",
        expand=True,
        min_lines=2,
        max_lines=3,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

    def preencher_da_congregacao(e):
        if not campo_congregacao.value:
            return
        cong = carregar_congregacao(int(campo_congregacao.value))
        if not cong:
            return
        if not (campo_responsavel.value or "").strip():
            campo_responsavel.value = cong["responsavel"]
        if not (campo_telefone.value or "").strip():
            campo_telefone.value = cong["telefone"]
        if not (campo_endereco.value or "").strip():
            campo_endereco.value = cong["endereco"]
        if not (campo_dia.value or "").strip():
            campo_dia.value = cong["dia_semana"]
        if not (campo_horario.value or "").strip():
            campo_horario.value = cong["horario"]
        page.update()

    campo_congregacao.on_select = preencher_da_congregacao

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        try:
            ano = int((campo_ano.value or "").strip())
            if ano < 2000 or ano > 2100:
                raise ValueError
        except ValueError:
            texto_erro.value = "Informe um ano válido."
            texto_erro.visible = True
            page.update()
            return

        if not campo_mes.value:
            texto_erro.value = "Selecione o mês."
            texto_erro.visible = True
            page.update()
            return

        mes = int(campo_mes.value)
        mes_inicio = mes_fim = mes
        if not campo_congregacao.value:
            texto_erro.value = "Selecione a congregação anfitriã."
            texto_erro.visible = True
            page.update()
            return

        try:
            salvar_arranjo(
                arranjo_id if editando else None,
                ano,
                mes_inicio,
                mes_fim,
                int(campo_congregacao.value),
                (campo_responsavel.value or "").strip(),
                (campo_telefone.value or "").strip(),
                (campo_endereco.value or "").strip(),
                (campo_dia.value or "").strip(),
                (campo_horario.value or "").strip(),
            )
        except Exception:
            texto_erro.value = (
                "Não foi possível salvar. Verifique se já existe arranjo para este mês."
            )
            texto_erro.visible = True
            page.update()
            return

        fechar()
        recarregar()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar arranjo" if editando else "Novo arranjo"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row([campo_ano, campo_mes], spacing=12),
                        campo_congregacao,
                        ft.Row([campo_responsavel, campo_telefone], spacing=12),
                        ft.Row([campo_dia, campo_horario], spacing=12),
                        campo_endereco,
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=520,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding.only(top=8),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Salvar", icon=ft.Icons.SAVE, on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def confirmar_exclusao_arranjo(
    page: ft.Page,
    recarregar: Callable[[], None],
    arranjo_id: int,
) -> None:
    """Exibe confirmação e exclui o arranjo se o usuário confirmar."""
    dados = carregar_arranjo(arranjo_id)
    if dados:
        rotulo = _rotulo_periodo_arranjo(dados["mes_inicio"], dados["mes_fim"])
        mensagem = f"Excluir o arranjo de {rotulo}/{dados['ano']}?"
    else:
        mensagem = "Excluir este arranjo?"

    def fechar(_=None):
        page.pop_dialog()

    def excluir(_=None):
        try:
            excluir_arranjo(arranjo_id)
            fechar()
            recarregar()
        except Exception:
            fechar()
            mostrar_aviso(page, "Não foi possível excluir", "Ocorreu um erro ao excluir o arranjo.")

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar exclusão"),
            content=ft.Text(mensagem),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Excluir", icon=ft.Icons.DELETE, on_click=excluir),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _criar_card_mes_programacao(
    rotulo: str,
    mes: int,
    arranjo: dict | None,
    resumo: dict,
    on_abrir: Callable[[dict], None],
    on_cadastrar: Callable[[int], None],
) -> ft.Container:
    """Card do mês com anfitriã, badge de status e progresso de semanas."""
    if not arranjo:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(rotulo, size=15, weight=ft.FontWeight.W_700, color=TEXTO_SECUNDARIO),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=16, color=TEXTO_SECUNDARIO),
                            ft.Text("Cadastrar arranjo", size=13, color=TEXTO_SECUNDARIO),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=0,
            ),
            padding=18,
            bgcolor=ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, BORDA_SUAVE),
            border_radius=14,
            expand=True,
            on_click=lambda e: on_cadastrar(mes),
            ink=True,
        )

    semanas = resumo["semanas"]
    cobertas = resumo["cobertas"]
    presidentes = resumo["presidentes"]
    if semanas and cobertas >= semanas and presidentes >= semanas:
        status, cor_status = "completo", COR_SUCESSO
    elif cobertas == 0:
        status, cor_status = "vazio", COR_ERRO
    else:
        status, cor_status = "parcial", COR_AVISO

    badge = ft.Container(
        content=ft.Text(status, size=11, weight=ft.FontWeight.W_600, color=cor_status),
        bgcolor=ft.Colors.with_opacity(0.14, cor_status),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
    )
    segmentos = ft.Row(
        [
            ft.Container(
                height=4,
                expand=True,
                border_radius=2,
                bgcolor=COR_DESTAQUE_CLARA if indice < cobertas else FUNDO_ELEVADO,
            )
            for indice in range(max(semanas, 1))
        ],
        spacing=4,
    )
    reuniao = f"{arranjo.get('dia_semana', '')} {arranjo.get('horario', '')}".strip()
    subtitulo = arranjo.get("congregacao") or "—"
    if reuniao:
        subtitulo += f" · {reuniao}"

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(rotulo, size=15, weight=ft.FontWeight.W_700, color=TEXTO_PRIMARIO, expand=True),
                        badge,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=4),
                ft.Text(subtitulo, size=12, color=TEXTO_SECUNDARIO, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(height=10),
                segmentos,
                ft.Container(height=8),
                ft.Text(
                    f"{resumo['recebidos']} recebidos · {resumo['enviados']} enviados · "
                    f"{presidentes} de {semanas} pres.",
                    size=11,
                    color=TEXTO_SECUNDARIO,
                ),
            ],
            spacing=0,
        ),
        padding=18,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(0.2),
        expand=True,
        on_click=lambda e: on_abrir(dict(arranjo)),
        ink=True,
        tooltip="Clique para abrir o mês",
    )


def tela_programacao(
    page: ft.Page,
    recarregar: Callable[[], None],
    file_picker: ft.FilePicker,
) -> ft.Control:
    """Programação anual: um card por mês com status, aberto num dialog com abas."""
    estado = {"ano": ANO_PADRAO_ARRANJOS}
    area_blocos = ft.Container(expand=True)
    texto_contagem = ft.Text(size=13, color=TEXTO_SECUNDARIO)

    def cadastrar_mes(mes: int):
        abrir_dialog_arranjo(
            page,
            recarregar_view,
            ano_padrao=estado["ano"],
            mes_padrao=mes,
        )

    def abrir_editar(arranjo_id: int):
        abrir_dialog_arranjo(page, recarregar_view, arranjo_id=arranjo_id)

    def abrir_excluir(arranjo_id: int):
        confirmar_exclusao_arranjo(page, recarregar_view, arranjo_id)

    def abrir_oradores_mes(arranjo: dict):
        abrir_dialog_oradores_mes(
            page,
            arranjo,
            on_editar_arranjo=abrir_editar,
            on_excluir_arranjo=abrir_excluir,
            file_picker=file_picker,
        )

    def montar_blocos():
        ano = estado["ano"]
        arranjos = carregar_arranjos_por_ano(ano)
        mapa = {int(item["mes_inicio"]): item for item in arranjos}
        recebidos = carregar_recebidos_por_ano(ano)
        presidentes = carregar_presidentes_por_ano(ano)
        contagens_ano = contar_designacoes_por_mes(ano)
        especiais = listar_datas_especiais_por_ano(ano)

        linhas: list[ft.Control] = []
        for indice in range(0, len(MESES_ANO), 2):
            par = MESES_ANO[indice : indice + 2]
            linhas.append(
                ft.Row(
                    [
                        _criar_card_mes_programacao(
                            rotulo,
                            numero_mes,
                            mapa.get(numero_mes),
                            _resumo_mes_programacao(
                                ano, numero_mes, recebidos, presidentes, contagens_ano, especiais
                            ),
                            on_abrir=abrir_oradores_mes,
                            on_cadastrar=cadastrar_mes,
                        )
                        for numero_mes, rotulo in par
                    ],
                    spacing=16,
                    expand=True,
                )
            )
            if indice + 2 < len(MESES_ANO):
                linhas.append(ft.Container(height=16))

        texto_contagem.value = (
            f"{len(arranjos)} de {len(MESES_ANO)} meses cadastrados em {ano}"
        )
        area_blocos.content = ft.Column(linhas, spacing=0, scroll=ft.ScrollMode.AUTO)

    def recarregar_view():
        montar_blocos()
        page.update()

    seletor_ano = ft.Dropdown(
        label="Ano",
        width=140,
        options=_opcoes_anos_arranjos(),
        value=str(estado["ano"]),
        border_color=BORDA_SUAVE,
        focused_border_color=COR_DESTAQUE,
    )

    def carregar_ano(_=None):
        try:
            estado["ano"] = int(seletor_ano.value)
            if estado["ano"] < 2000 or estado["ano"] > 2100:
                raise ValueError
        except (TypeError, ValueError):
            estado["ano"] = ANO_PADRAO_ARRANJOS
            seletor_ano.value = str(ANO_PADRAO_ARRANJOS)
        montar_blocos()
        page.update()

    seletor_ano.on_select = carregar_ano

    def ao_adicionar_ano(ano: int):
        seletor_ano.options = _opcoes_anos_arranjos()
        seletor_ano.value = str(ano)
        carregar_ano()

    def abrir_adicionar_ano(_=None):
        abrir_dialog_adicionar_ano(page, ao_adicionar_ano)

    montar_blocos()

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Programação",
                "Oradores, designações e presidentes de cada mês do circuito",
            ),
            ft.Container(height=24),
            ft.Row(
                [
                    seletor_ano,
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Adicionar ano",
                        on_click=abrir_adicionar_ano,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            ft.Container(height=12),
            texto_contagem,
            ft.Container(height=16),
            area_blocos,
        ],
        spacing=0,
        expand=True,
    )


def tela_ajustes(
    page: ft.Page,
    recarregar: Callable[[], None],
    file_picker: ft.FilePicker,
) -> ft.Control:
    """Formulário para cadastrar/editar as informações da congregação principal."""
    config = carregar_configuracao()

    campo_nome = ft.TextField(
        label="Nome da Congregação",
        hint_text="Ex: Jardim Primavera",
        value=config["nome_congregacao"],
        expand=True,
    )
    campo_endereco = ft.TextField(
        label="Endereço",
        hint_text="Ex: Av. das Flores, 100 - Centro",
        value=config["endereco"],
        expand=True,
    )
    campo_cidade = ft.TextField(
        label="Cidade / UF",
        hint_text="Ex: São Paulo, SP",
        value=config["cidade"],
        expand=True,
    )
    campo_cep = ft.TextField(
        label="CEP",
        value=config["cep"],
        expand=True,
    )
    campo_coordenador = ft.TextField(
        label="Coordenador de discursos públicos",
        value=config["coordenador_discursos"],
        expand=True,
    )
    campo_telefone = ft.TextField(
        label="Telefone do coordenador",
        value=config["telefone_coordenador"],
        expand=True,
    )
    campo_dia = ft.TextField(
        label="Dia da reunião de fim de semana",
        hint_text="Ex: Sábado",
        value=config["dia_reuniao"],
        expand=True,
    )
    campo_horario = ft.TextField(
        label="Horário da reunião",
        hint_text="Ex: 19:30",
        value=config["horario_reuniao"],
        expand=True,
    )
    campo_circuito = ft.TextField(
        label="Circuito",
        value=config["circuito"],
        expand=True,
    )
    texto_sucesso = ft.Text(
        "Informações salvas com sucesso.",
        color=COR_SUCESSO,
        size=13,
        visible=False,
    )

    def salvar(_=None):
        salvar_configuracao(
            {
                "nome_congregacao": (campo_nome.value or "").strip(),
                "endereco": (campo_endereco.value or "").strip(),
                "cidade": (campo_cidade.value or "").strip(),
                "cep": (campo_cep.value or "").strip(),
                "coordenador_discursos": (campo_coordenador.value or "").strip(),
                "telefone_coordenador": (campo_telefone.value or "").strip(),
                "dia_reuniao": (campo_dia.value or "").strip(),
                "horario_reuniao": (campo_horario.value or "").strip(),
                "circuito": (campo_circuito.value or "").strip(),
            }
        )
        texto_sucesso.visible = True
        page.update()

    formulario = ft.Container(
        content=ft.Column(
            [
                ft.Text("Minha congregação", size=16, weight=ft.FontWeight.W_600),
                ft.Container(height=4),
                ft.Text(
                    "Dados usados nos cabeçalhos dos PDFs e nas exportações.",
                    size=13,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Container(height=8),
                campo_nome,
                campo_endereco,
                ft.Row([campo_cidade, campo_cep], spacing=12),
                ft.Row([campo_coordenador, campo_telefone], spacing=12),
                ft.Row([campo_dia, campo_horario], spacing=12),
                campo_circuito,
                ft.Container(height=8),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Salvar",
                            icon=ft.Icons.SAVE,
                            on_click=salvar,
                        ),
                        texto_sucesso,
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=1, color=BORDA_SUAVE),
                ft.Text("Presidentes", size=14, weight=ft.FontWeight.W_600),
                ft.Text(
                    "Cadastro de quem pode presidir a reunião de fim de semana "
                    "(a atribuição semana a semana é feita na Programação).",
                    size=13,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Row(
                    [
                        ft.OutlinedButton(
                            "Gerenciar presidentes",
                            icon=ft.Icons.MANAGE_ACCOUNTS,
                            on_click=lambda _: abrir_dialog_gerenciar_presidentes(page, recarregar),
                        ),
                    ],
                ),
            ],
            spacing=16,
            tight=True,
        ),
        padding=28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=560,
    )

    def exportar_backup_click(_=None):
        try:
            caminho, contagens = exportar_backup()
        except Exception as exc:
            mostrar_aviso(page, "Erro ao exportar", f"Não foi possível gerar o backup: {exc}")
            return

        def fechar(_=None):
            page.pop_dialog()

        def abrir_pasta(_=None):
            abrir_pasta_do_arquivo(caminho)
            fechar()

        resumo_contagens = (
            f"• {contagens.get('congregacoes', 0)} congregação(ões)\n"
            f"• {contagens.get('oradores', 0)} orador(es) "
            f"({contagens.get('orador_temas', 0)} vínculos com temas)\n"
            f"• {contagens.get('temas', 0)} temas "
            f"({contagens.get('tema_uso_por_ano', 0)} datas de uso)\n"
            f"• {contagens.get('presidentes_cadastro', 0)} presidente(s) "
            f"({contagens.get('presidentes', 0)} semanas atribuídas)\n"
            f"• {contagens.get('arranjo_oradores', 0)} designações de arranjo, "
            f"{contagens.get('datas_especiais', 0)} data(s) especial(is)"
        )

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Backup exportado"),
                content=ft.Text(
                    f"Todos os dados do aplicativo foram salvos:\n\n{resumo_contagens}\n\n"
                    f"Arquivo:\n{caminho}\n\n"
                    "Guarde este arquivo em um local seguro (nuvem, pendrive). "
                    "Ele poderá ser importado neste aplicativo ou no futuro "
                    "aplicativo para smartphone.",
                    size=13,
                ),
                actions=[
                    ft.TextButton("Fechar", on_click=fechar),
                    ft.FilledButton("Abrir pasta", icon=ft.Icons.FOLDER_OPEN, on_click=abrir_pasta),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    async def restaurar_backup_click(_=None):
        arquivos = await file_picker.pick_files(
            dialog_title="Selecione o arquivo de backup",
            allowed_extensions=["json"],
            allow_multiple=False,
        )
        if not arquivos:
            return
        caminho = arquivos[0].path

        def fechar(_=None):
            page.pop_dialog()

        def confirmar(_=None):
            fechar()
            ok, mensagem = restaurar_backup(caminho)
            if ok:
                recarregar()
            mostrar_aviso(
                page,
                "Backup restaurado" if ok else "Não foi possível restaurar",
                mensagem,
            )

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Restaurar backup"),
                content=ft.Text(
                    "Os dados atuais serão substituídos pelos do arquivo selecionado.\n"
                    "Uma cópia de segurança do estado atual será salva antes.\n\n"
                    "Deseja continuar?",
                    size=13,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=fechar),
                    ft.FilledButton("Restaurar", icon=ft.Icons.RESTORE, on_click=confirmar),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def abrir_restaurar(_=None):
        page.run_task(restaurar_backup_click)

    def baixar_modelo_click(_=None):
        try:
            caminho = gerar_planilha_modelo()
        except Exception as exc:
            mostrar_aviso(page, "Erro ao gerar", f"Não foi possível criar a planilha: {exc}")
            return

        def fechar(_=None):
            page.pop_dialog()

        def abrir_pasta(_=None):
            abrir_pasta_do_arquivo(caminho)
            fechar()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Planilha-modelo gerada"),
                content=ft.Text(
                    f"A planilha foi salva em:\n{caminho}\n\n"
                    "Preencha as abas Congregações, Oradores e Presidentes "
                    "(a aba Leia-me explica cada coluna) e depois importe o "
                    "arquivo aqui em Ajustes.",
                    size=13,
                ),
                actions=[
                    ft.TextButton("Fechar", on_click=fechar),
                    ft.FilledButton("Abrir pasta", icon=ft.Icons.FOLDER_OPEN, on_click=abrir_pasta),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def _resumir_importacao_planilha(resumo: dict) -> str:
        linhas = [
            f"Congregações: {resumo['congregacoes']['novas']} nova(s), "
            f"{resumo['congregacoes']['ja_existiam']} já existia(m).",
            f"Oradores: {resumo['oradores']['novos']} novo(s), "
            f"{resumo['oradores']['ja_existiam']} já existia(m).",
            f"Presidentes: {resumo['presidentes']['novos']} novo(s), "
            f"{resumo['presidentes']['ja_existiam']} já existia(m).",
        ]
        avisos = resumo.get("avisos") or []
        if avisos:
            mostrados = avisos[:8]
            linhas.append("")
            linhas.append("Avisos:")
            linhas.extend(f"• {a}" for a in mostrados)
            if len(avisos) > len(mostrados):
                linhas.append(f"… e mais {len(avisos) - len(mostrados)} aviso(s).")
        return "\n".join(linhas)

    async def importar_planilha_click(_=None):
        arquivos = await file_picker.pick_files(
            dialog_title="Selecione a planilha de dados preenchida",
            allowed_extensions=["xlsx"],
            allow_multiple=False,
        )
        if not arquivos:
            return
        try:
            resumo = importar_planilha_dados(arquivos[0].path)
        except Exception as exc:
            mostrar_aviso(page, "Não foi possível importar", str(exc))
            return
        recarregar()
        mostrar_aviso(page, "Planilha importada", _resumir_importacao_planilha(resumo))

    def abrir_importar_planilha(_=None):
        page.run_task(importar_planilha_click)

    secao_planilha = ft.Container(
        content=ft.Column(
            [
                ft.Text("Carga inicial por planilha", size=16, weight=ft.FontWeight.W_600),
                ft.Container(height=4),
                ft.Text(
                    "Para começar num aplicativo vazio há dois caminhos: restaurar "
                    "um arquivo de backup (acima) ou preencher uma planilha com "
                    "congregações, oradores e presidentes e importá-la aqui. A "
                    "importação apenas adiciona dados — nada é apagado. Os temas "
                    "não entram na planilha: importe os formulários S-99/S-99a "
                    "diretamente na aba Temas.",
                    size=13,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Container(height=12),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Baixar planilha-modelo",
                            icon=ft.Icons.DOWNLOAD,
                            on_click=baixar_modelo_click,
                        ),
                        ft.OutlinedButton(
                            "Importar planilha preenchida",
                            icon=ft.Icons.UPLOAD_FILE,
                            on_click=abrir_importar_planilha,
                        ),
                    ],
                    spacing=12,
                ),
            ],
            spacing=0,
            tight=True,
        ),
        padding=28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=560,
    )

    secao_backup = ft.Container(
        content=ft.Column(
            [
                ft.Text("Backup dos dados", size=16, weight=ft.FontWeight.W_600),
                ft.Container(height=4),
                ft.Text(
                    "Exporte todos os dados do aplicativo — congregações, oradores, "
                    "temas (títulos, assuntos, observações e datas de uso por ano), "
                    "arranjos, designações, presidentes e datas especiais — para um "
                    "arquivo JSON portátil, o mesmo formato que será usado pelo "
                    "futuro aplicativo de smartphone.",
                    size=13,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Container(height=12),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Exportar backup",
                            icon=ft.Icons.BACKUP_OUTLINED,
                            on_click=exportar_backup_click,
                        ),
                        ft.OutlinedButton(
                            "Restaurar backup",
                            icon=ft.Icons.RESTORE,
                            on_click=abrir_restaurar,
                        ),
                    ],
                    spacing=12,
                ),
            ],
            spacing=0,
            tight=True,
        ),
        padding=28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=560,
    )

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Ajustes",
                "Dados da congregação, presidentes, backup e exportações",
            ),
            ft.Container(height=24),
            formulario,
            ft.Container(height=24),
            secao_backup,
            ft.Container(height=24),
            secao_planilha,
            ft.Container(height=24),
            criar_painel_informativo(
                "Uso nas exportações",
                "Estas informações serão utilizadas na geração do PDF de envio "
                "de discursos públicos ao superintendente de circuito.",
            ),
        ],
        spacing=0,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def tela_quadro_anuncios(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Prévia e exportação do quadro de anúncios (publicado de 2 em 2 meses)."""
    hoje = date.today()
    anos_disponiveis = {opcao.key for opcao in _opcoes_anos_arranjos()}
    estado = {
        "ano": hoje.year if str(hoje.year) in anos_disponiveis else ANO_PADRAO_ARRANJOS,
        "mes_inicial": par_meses_do_mes_quadro(hoje.month)[0],
    }
    area_preview = ft.Container(expand=True)

    opcoes_pares = [
        ft.dropdown.Option(
            key=str(inicio),
            text=f"{NOMES_MESES[inicio]}-{NOMES_MESES[fim]}",
        )
        for inicio, fim in PARES_MESES_QUADRO
    ]

    def montar_preview():
        config = carregar_configuracao()
        nome_congregacao = config.get("nome_congregacao") or "Minha congregação"
        inicio = estado["mes_inicial"]
        blocos = []
        for mes in (inicio, inicio + 1):
            dados = carregar_dados_mes_quadro(estado["ano"], mes)
            png_bytes = gerar_preview_quadro_mes(estado["ano"], mes, dados, nome_congregacao)
            blocos.append(
                ft.Container(
                    content=ft.Image(src=png_bytes, fit=ft.BoxFit.CONTAIN),
                    padding=ft.Padding.only(bottom=24),
                )
            )
        area_preview.content = ft.Column(blocos, scroll=ft.ScrollMode.AUTO, expand=True)

    def exportar(_=None):
        try:
            caminho, erro = gerar_quadro_anuncios(estado["ano"], estado["mes_inicial"])
            if erro:
                mostrar_aviso(page, "Erro ao gerar PDF", erro)
                return
            abrir_arquivo(caminho)
            mostrar_aviso(
                page,
                "PDF gerado com sucesso",
                f"O quadro de anúncios foi salvo em:\n{caminho}",
            )
        except Exception as exc:
            mostrar_aviso(page, "Erro", f"Não foi possível gerar o PDF: {exc}")

    def atualizar(_=None):
        try:
            estado["ano"] = int(seletor_ano.value)
        except (TypeError, ValueError):
            estado["ano"] = ANO_PADRAO_ARRANJOS
            seletor_ano.value = str(ANO_PADRAO_ARRANJOS)
        try:
            estado["mes_inicial"] = int(seletor_par.value)
        except (TypeError, ValueError):
            estado["mes_inicial"] = PARES_MESES_QUADRO[0][0]
        montar_preview()
        page.update()

    seletor_ano = ft.Dropdown(
        label="Ano",
        width=120,
        options=_opcoes_anos_arranjos(),
        value=str(estado["ano"]),
        border_color=BORDA_SUAVE,
        focused_border_color=COR_DESTAQUE,
    )
    seletor_par = ft.Dropdown(
        label="Meses",
        width=220,
        options=opcoes_pares,
        value=str(estado["mes_inicial"]),
        border_color=BORDA_SUAVE,
        focused_border_color=COR_DESTAQUE,
    )
    seletor_ano.on_select = atualizar
    seletor_par.on_select = atualizar

    def ao_adicionar_ano(ano: int):
        seletor_ano.options = _opcoes_anos_arranjos()
        seletor_ano.value = str(ano)
        atualizar()

    def abrir_adicionar_ano(_=None):
        abrir_dialog_adicionar_ano(page, ao_adicionar_ano)

    montar_preview()

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Quadro de Anúncios",
                "Prévia do quadro de conferência pública, publicado de 2 em 2 meses",
            ),
            ft.Container(height=24),
            ft.Row(
                [
                    seletor_ano,
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Adicionar ano",
                        on_click=abrir_adicionar_ano,
                    ),
                    seletor_par,
                    ft.Container(expand=True),
                    ft.FilledButton(
                        "Exportar PDF",
                        icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
                        on_click=exportar,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            ft.Container(height=16),
            area_preview,
        ],
        spacing=0,
        expand=True,
    )


def abrir_dialog_gerenciar_presidentes(
    page: ft.Page,
    ao_fechar: Callable[[], None],
) -> None:
    """Cadastro de presidentes: adicionar, editar, excluir e ordenar o rodízio."""
    estado_edicao: dict = {"id": None}
    cadastro: list[dict] = []
    lista_cadastro = ft.Column(spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, height=260)
    campo_nome = ft.TextField(label="Nome", expand=True)
    campo_categoria = ft.Dropdown(
        label="Privilégio",
        value="Ancião",
        options=[
            ft.dropdown.Option("Ancião"),
            ft.dropdown.Option("Servo Ministerial"),
        ],
        width=190,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)
    botao_salvar = ft.FilledButton("Adicionar", icon=ft.Icons.ADD)

    def limpar_formulario():
        estado_edicao["id"] = None
        campo_nome.value = ""
        campo_categoria.value = "Ancião"
        botao_salvar.content = "Adicionar"
        botao_salvar.icon = ft.Icons.ADD
        texto_erro.visible = False

    def preencher_lista():
        nonlocal cadastro
        cadastro = listar_presidentes_cadastro()
        if not cadastro:
            lista_cadastro.controls = [
                ft.Text(
                    "Nenhum presidente cadastrado ainda.",
                    size=13,
                    color=TEXTO_SECUNDARIO,
                    italic=True,
                )
            ]
            return

        def mover(indice: int, delta: int):
            nova = [item["id"] for item in cadastro]
            destino = indice + delta
            if 0 <= destino < len(nova):
                nova[indice], nova[destino] = nova[destino], nova[indice]
                salvar_ordem_presidentes(nova)
                preencher_lista()
                page.update()

        def linha_cadastro(indice: int, item: dict) -> ft.Control:
            def editar(_=None, item=item):
                estado_edicao["id"] = item["id"]
                campo_nome.value = item["nome"]
                campo_categoria.value = item["categoria"]
                botao_salvar.content = "Salvar"
                botao_salvar.icon = ft.Icons.SAVE
                texto_erro.visible = False
                page.update()

            def excluir(_=None, item=item):
                try:
                    excluir_presidente_cadastro(item["id"])
                except Exception:
                    texto_erro.value = "Não foi possível excluir este presidente."
                    texto_erro.visible = True
                    page.update()
                    return
                if estado_edicao["id"] == item["id"]:
                    limpar_formulario()
                preencher_lista()
                page.update()

            return ft.Row(
                [
                    ft.Text(f"{indice + 1}º", size=12, color=TEXTO_SECUNDARIO, width=30),
                    ft.Text(item["nome"], size=14, expand=True),
                    ft.Text(item["categoria"], size=13, color=TEXTO_SECUNDARIO, width=140),
                    ft.IconButton(
                        icon=ft.Icons.ARROW_UPWARD,
                        icon_size=16,
                        tooltip="Subir no rodízio",
                        disabled=indice == 0,
                        on_click=lambda e, i=indice: mover(i, -1),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ARROW_DOWNWARD,
                        icon_size=16,
                        tooltip="Descer no rodízio",
                        disabled=indice == len(cadastro) - 1,
                        on_click=lambda e, i=indice: mover(i, 1),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        icon_size=18,
                        tooltip="Editar",
                        on_click=editar,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        icon_color=COR_ERRO,
                        tooltip="Excluir (remove também as semanas atribuídas)",
                        on_click=excluir,
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        lista_cadastro.controls = [
            linha_cadastro(indice, item) for indice, item in enumerate(cadastro)
        ]

    def salvar(_=None):
        nome = (campo_nome.value or "").strip()
        if not nome:
            texto_erro.value = "O nome é obrigatório."
            texto_erro.visible = True
            page.update()
            return
        try:
            salvar_presidente_cadastro(
                nome,
                campo_categoria.value or "Ancião",
                cadastro_id=estado_edicao["id"],
            )
        except Exception:
            texto_erro.value = "Já existe um presidente com esse nome."
            texto_erro.visible = True
            page.update()
            return
        limpar_formulario()
        preencher_lista()
        page.update()

    botao_salvar.on_click = salvar

    def fechar(_=None):
        page.pop_dialog()
        ao_fechar()
        page.update()

    preencher_lista()
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Gerenciar presidentes"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [campo_nome, campo_categoria, botao_salvar],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        texto_erro,
                        ft.Container(height=8),
                        ft.Row(
                            [
                                ft.Text("Cadastrados", weight=ft.FontWeight.W_600, size=13, expand=True),
                                ft.Text(
                                    "A ordem define o rodízio automático",
                                    size=12,
                                    color=TEXTO_SECUNDARIO,
                                ),
                            ],
                        ),
                        lista_cadastro,
                    ],
                    spacing=12,
                    tight=True,
                    width=560,
                ),
                padding=ft.Padding.only(top=8),
            ),
            actions=[ft.TextButton("Fechar", on_click=fechar)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


# ---------------------------------------------------------------------------
# Layout principal
# ---------------------------------------------------------------------------

def _cor_fundo_item_menu(selecionado: bool):
    """Fundo suave e arredondado para o item selecionado."""
    if selecionado:
        return ft.Colors.with_opacity(0.14, COR_DESTAQUE_CLARA)
    return ft.Colors.TRANSPARENT


def atualizar_menu_lateral(itens_menu: list[dict], indice_ativo: int) -> None:
    """Atualiza destaque visual dos itens do menu lateral."""
    for i, item in enumerate(itens_menu):
        selecionado = i == indice_ativo
        item["container"].bgcolor = _cor_fundo_item_menu(selecionado)
        cor = COR_DESTAQUE_SUAVE if selecionado else TEXTO_SECUNDARIO
        item["icone"].color = cor
        item["rotulo"].color = cor
        item["rotulo"].weight = ft.FontWeight.W_600 if selecionado else ft.FontWeight.W_400


def criar_barra_lateral(
    on_navegar: Callable[[int], None],
    itens_menu_ref: list[dict],
) -> ft.Container:
    """Barra lateral com ícone + nome de cada seção."""
    itens_menu_ref.clear()
    itens_coluna: list[ft.Control] = [
        ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "GESTÃO DE ARRANJO",
                        size=11,
                        weight=ft.FontWeight.W_600,
                        color=TEXTO_SECUNDARIO,
                    ),
                    ft.Text(f"v{VERSAO_APP}", size=10, color=TEXTO_SECUNDARIO),
                ],
                spacing=2,
                tight=True,
            ),
            padding=ft.Padding.only(left=14, bottom=10),
        )
    ]

    for indice, secao in enumerate(SECOES):
        selecionado = indice == 0
        cor = COR_DESTAQUE_SUAVE if selecionado else TEXTO_SECUNDARIO
        icone = ft.Icon(secao["icone"], size=ICON_SIZE_MENU, color=cor)
        rotulo = ft.Text(
            secao["nome"],
            size=13,
            color=cor,
            weight=ft.FontWeight.W_600 if selecionado else ft.FontWeight.W_400,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        wrapper = ft.Container(
            content=ft.Row([icone, rotulo], spacing=10, tight=True),
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            border_radius=8,
            bgcolor=_cor_fundo_item_menu(selecionado),
            on_click=lambda e, i=indice: on_navegar(i),
            ink=True,
        )
        itens_menu_ref.append({"container": wrapper, "icone": icone, "rotulo": rotulo})
        itens_coluna.append(wrapper)

    return ft.Container(
        width=LARGURA_BARRA_LATERAL,
        bgcolor=FUNDO_SIDEBAR,
        border=ft.Border.only(right=ft.BorderSide(1, "#1E2942")),
        padding=ft.Padding.symmetric(vertical=20, horizontal=10),
        content=ft.Column(
            itens_coluna,
            spacing=4,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )


def main(page: ft.Page):
    """Configura a janela e monta o layout principal."""
    garantir_tabelas()

    page.title = "Gestão de Arranjo"
    aplicar_tema(page)
    page.padding = 0
    page.window.width = 1150
    page.window.height = 750
    page.window.min_width = 960
    page.window.min_height = 600

    area_conteudo = ft.Container(
        expand=True,
        padding=ft.Padding.all(28),
        bgcolor=FUNDO_APP,
    )
    estado = {"indice": 0}
    itens_menu: list[dict] = []

    def mostrar_inicio():
        area_conteudo.content = tela_inicio(page, recarregar, navegar)

    def mostrar_programacao():
        area_conteudo.content = tela_programacao(page, recarregar, file_picker)

    def mostrar_oradores():
        area_conteudo.content = tela_oradores(page, recarregar)

    def mostrar_congregacoes():
        area_conteudo.content = tela_congregacoes(page, recarregar)

    def mostrar_temas():
        area_conteudo.content = tela_temas(page, file_picker)

    def mostrar_quadro_anuncios():
        area_conteudo.content = tela_quadro_anuncios(page, recarregar)

    def mostrar_ajustes():
        area_conteudo.content = tela_ajustes(page, recarregar, file_picker)

    telas = [
        mostrar_inicio,
        mostrar_programacao,
        mostrar_oradores,
        mostrar_congregacoes,
        mostrar_temas,
        mostrar_quadro_anuncios,
        mostrar_ajustes,
    ]

    def navegar(indice: int):
        estado["indice"] = indice
        atualizar_menu_lateral(itens_menu, indice)
        telas[indice]()
        page.update()

    recarregar = lambda: navegar(estado["indice"])

    barra_lateral = criar_barra_lateral(navegar, itens_menu)

    page.add(
        ft.Container(
            content=ft.Row(
                [
                    barra_lateral,
                    area_conteudo,
                ],
                expand=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=True,
            bgcolor=FUNDO_APP,
        )
    )

    file_picker = ft.FilePicker()
    page.update()

    navegar(0)


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)