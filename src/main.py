"""
Gestão de Arranjo — aplicativo em Flet (Windows, Linux e Android).

Fonte única: os três sistemas compilam desta mesma pasta `src/`. As diferenças
de plataforma são resolvidas em tempo de execução (ver armazenamento.eh_mobile).

Execute com: python src/main.py
"""

from __future__ import annotations

import re
import sqlite3
import sys
import time
import webbrowser
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import flet as ft

import nuvem_drive
import tema as _tema  # apelidado: `tema` é usado como variável local (título) em várias telas
from agenda_ics import eventos_do_mes, gerar_ics
from armazenamento import (
    EXPORTS_DIR,
    FOTOS_DIR,
    definir_layout_mobile,
    eh_mobile,
    garantir_pastas,
)
from atualizacao import verificar_agora, verificar_na_abertura
from canticos import TOTAL_CANTICOS, rotulo_cantico, titulo_cantico
from contatos import (
    Contato,
    caminho_foto_contato,
    filtrar_contatos,
    formatar_telefone,
    iniciais_do_nome,
    ler_vcard,
    mascara_telefone,
    mudancas_de_contato,
    salvar_foto_contato,
)
from database import (
    adicionar_ano_coluna,
    adicionar_ano_planejamento,
    adicionar_orador_arranjo,
    adicionar_tipo_evento,
    alterado_em_local,
    atualizar_data_designacao,
    atualizar_orador_arranjo,
    atualizar_status_orador_arranjo,
    atualizar_telefone_por_contato,
    carregar_arranjo,
    carregar_arranjos_por_ano,
    carregar_dataframe_temas,
    carregar_designacoes_ano,
    carregar_enviados_por_ano,
    carregar_escala_fonte,
    carregar_oradores_arranjo,
    carregar_presidentes_por_ano,
    carregar_recebidos_por_ano,
    carregar_tema,
    carregar_temas_com_titulo_de_orador,
    carregar_temas_de_orador,
    carregar_todas_designacoes_presidente,
    contar_convites_sem_resposta,
    contar_designacoes_por_mes,
    contar_designacoes_por_status,
    create_tables,
    definir_presidente_data_especial,
    definir_tema_prioritario,
    definir_tipo_evento_tem_presidente,
    definir_visibilidade_ano_coluna,
    excluir_ano_coluna,
    excluir_arranjo,
    excluir_data_especial,
    excluir_orador,
    excluir_presidente,
    excluir_presidente_cadastro,
    excluir_reuniao_historico,
    excluir_tema,
    excluir_tipo_evento,
    exportar_backup,
    garantir_configuracao_inicial,
    get_connection,
    historico_presidentes_por_tipo_de_evento,
    importar_temas_pdf,
    listar_anos_arranjos,
    listar_anos_colunas,
    listar_anos_planejamento,
    listar_datas_especiais_por_ano,
    listar_presidentes_cadastro,
    listar_reuniao_historico,
    listar_tipos_evento,
    listar_vinculos_de_contato,
    oradores_com_temas_da_congregacao,
    realocar_uso_para_ano_da_data,
    registrar_convite_enviado,
    relatorio_frequencia_oradores,
    relatorio_presidencias,
    remover_orador_arranjo,
    restaurar_backup,
    resumo_backup,
    reuniao_em,
    salvar_arranjo,
    salvar_data_especial,
    salvar_escala_fonte,
    salvar_orador,
    salvar_ordem_presidentes,
    salvar_presidente,
    salvar_presidente_avulso,
    salvar_presidente_cadastro,
    salvar_reuniao_historico,
    salvar_tema,
    sincronizar_uso_temas,
    tipos_evento_sem_presidente,
    trocar_datas_designacoes,
    ultima_data_discurso_por_orador,
)
from log_app import configurar_log, logger
from pdf_quadro import (
    PARES_MESES as PARES_MESES_QUADRO,
)
from pdf_quadro import (
    abrir_arquivo,
    gerar_quadro_anuncios,
)
from pdf_quadro import (
    carregar_dados_mes as carregar_dados_mes_quadro,
)
from pdf_quadro import (
    par_meses_do_mes as par_meses_do_mes_quadro,
)
from pdf_relatorios import gerar_pdf_secoes
from planilha_dados import gerar_planilha_modelo, importar_planilha_dados
from png_oradores import (
    abrir_pasta_do_arquivo,
    copiar_imagem_para_area_transferencia,
    gerar_link_whatsapp,
    gerar_png_designacao_envio,
    gerar_png_oradores,
    gerar_preview_quadro_mes,
)
from servicos import (
    detectar_conflitos_oradores,
    escolher_rodizio_datas_especiais,
    escolher_rodizio_presidentes,
    meses_de_atencao,
    montar_mensagem_presidencia,
    oradores_mais_tempo_sem_discurso,
    sugerir_recebidos,
    weekdays_sugeridos,
)
from tabela import Tabela
from tabela import filtrar as filtrar_tabela
from telas.calendario import tela_calendario
from tema import (
    BORDA_SUAVE,
    COR_AVISO,
    COR_DESTAQUE,
    COR_DESTAQUE_CLARA,
    COR_DESTAQUE_SUAVE,
    COR_ERRO,
    COR_SUCESSO,
    ESPACO_COLUNAS_MES,
    FUNDO_APP,
    FUNDO_CARD,
    FUNDO_ELEVADO,
    FUNDO_SIDEBAR,
    LARGURA_DIALOG_MES,
    LARGURA_PREVIEW_BASE,
    TEXTO_PRIMARIO,
    TEXTO_SECUNDARIO,
    ZOOM_PREVIEW_MAX,
    ZOOM_PREVIEW_MIN,
    fonte,
)
from ui_comuns import (
    _cor_fundo_item_menu,
    _estilo_campo_busca,
    _icone_entrega,
    _largura_dialog,
    _rotulo_entrega,
    _sombra_card,
    abrir_url,
    aplicar_tema,
    criar_cabecalho_tela,
    criar_painel_informativo,
    criar_secao_titulo,
    executar_com_progresso,
    linha_campos,
    mostrar_aviso,
    mostrar_sucesso,
)

try:
    # Extensão local (extensoes/flet_contatos): seletor NATIVO de contatos.
    # Só entra no build do Android — o pacote Flutter por trás não existe para
    # Windows e Linux. No PC o import falha de propósito e o app usa o .vcf.
    from flet_contatos import Contatos as _ServicoContatosNativo
except ImportError:  # pragma: no cover — depende da plataforma compilada
    _ServicoContatosNativo = None
from util import (
    DIAS_SEM_RESPOSTA,
    NOMES_MESES,
    _datas_por_weekday_no_mes,
    _dia_semana_para_weekday,
    _formatar_data_arranjo,
    _formatar_data_exibicao,
    _normalizar_data_arranjo,
    _normalizar_texto_busca,
    _parse_data_arranjo,
    _rotulo_weekday,
    _weekday_mais_usado,
    aviso_backup_antigo,
    descrever_ultimo_envio,
    espera_de_resposta,
    formatar_data_hora_sao_paulo,
    nome_oradores,
    rotulo_de_prazo,
)
from versao import VERSAO_APP

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------


# Zoom "Ctrl + roda do mouse" na prévia do quadro. O ScrollEvent do Flet não
# traz os modificadores, então perguntamos ao sistema se o Ctrl está pressionado
# NO MOMENTO da rolagem. No Windows isso é exato (GetKeyState); no restante,
# caímos no rastreio por evento de teclado, que é o melhor que dá para fazer.
_TECLADO = {"ctrl_ate": 0.0}


def _registrar_teclado(e) -> None:
    """Marca o Ctrl como recém-visto (usado fora do Windows)."""
    if getattr(e, "ctrl", False):
        _TECLADO["ctrl_ate"] = time.monotonic() + 1.5


def _ctrl_pressionado() -> bool:
    """True se a tecla Ctrl está pressionada agora."""
    if sys.platform.startswith("win"):
        try:
            import ctypes

            # 0x11 = VK_CONTROL; bit alto ligado = tecla pressionada.
            return bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000)
        except (AttributeError, OSError):  # sem a API do sistema: usa o fallback
            logger.debug("GetKeyState indisponível; usando o Ctrl por tempo")
    return time.monotonic() < _TECLADO["ctrl_ate"]

SECOES = [
    {"nome": "Início", "icone": ft.Icons.HOME},
    {"nome": "Programação", "icone": ft.Icons.CALENDAR_MONTH},
    # Oradores não é uma aba: os da minha congregação moram em "Minha
    # congregação" (é lá que se monta a lista de envio) e os de fora ficam
    # dentro do cadastro de cada congregação, que é de onde eles vêm.
    {"nome": "Congregações", "icone": ft.Icons.LOCATION_CITY},
    {"nome": "Minha congregação", "icone": ft.Icons.HOME_WORK},
    {"nome": "Temas", "icone": ft.Icons.MENU_BOOK},
    {"nome": "Quadro de Anúncios", "icone": ft.Icons.CAMPAIGN},
    {"nome": "Calendário", "icone": ft.Icons.CALENDAR_TODAY},
    {"nome": "Relatórios", "icone": ft.Icons.INSIGHTS},
    {"nome": "Ajustes", "icone": ft.Icons.SETTINGS},
]

# Índices de navegação usados em botões/atalhos (mantidos junto de SECOES
# para não quebrarem quando a ordem das abas mudar).
INDICE_MINHA_CONGREGACAO = 3
INDICE_RELATORIOS = 7
INDICE_AJUSTES = 8

# Quantos meses à frente as Pendências do Início cobram. O arranjo se monta com
# poucos meses de antecedência: cobrar o ano todo enche a lista de meses que
# ainda nem começaram a ser feitos.
MESES_DE_ATENCAO = 3

# Serviços do Flet criados no main() e usados por funções soltas do módulo.
# Declarados aqui para quem lê antes de o app subir (testes) achar None em vez
# de NameError.
_file_picker_global: ft.FilePicker | None = None
_share_global: ft.Share | None = None
_clipboard_global: ft.Clipboard | None = None
_contatos_nativo_global = None

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
           COALESCE(o.aprovado_fora, 1) AS aprovado_fora,
           COALESCE(c.nome, '—') AS congregacao
    FROM oradores o
    LEFT JOIN congregacoes c ON o.congregacao_id = c.id
    WHERE COALESCE(o.ativo, 1) = 1
    ORDER BY o.categoria, o.nome
"""

# As mesmas colunas que a busca da tela de Oradores varre — a de Congregações
# reaproveita para achar a pessoa dentro do cartão da congregação dela.
COLUNAS_BUSCA_ORADORES = ["nome", "categoria", "telefone", "temas", "observacoes"]

SQL_CONGREGACOES = """
    SELECT id, nome, responsavel, telefone, endereco, dia_semana, horario, observacoes
    FROM congregacoes
    ORDER BY nome
"""

ANO_PADRAO_ARRANJOS = 2026
QUANTIDADE_DATAS_SUGERIDAS = 5


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
    # `prioritario` não vira coluna: aparece como estrela ao lado do título.
    "colunas_ocultas": [
        "data_limite_uso", "restrito", "tem_observacao", "ultimo_uso_chave", "prioritario",
    ],
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

def carregar_dados(query: str) -> Tabela:
    """Executa uma consulta SQL e retorna o resultado como Tabela."""
    conn = get_connection()
    try:
        return Tabela.de_consulta(conn, query)
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
    garantir_pastas()
    conn = get_connection()
    try:
        create_tables(conn)
        garantir_configuracao_inicial(conn)
        # Datas vindas da planilha/S-99 ficavam em colunas posicionais: põe
        # cada uma na coluna do seu próprio ano antes de somar os arranjos.
        realocar_uso_para_ano_da_data(conn)
        # Traz para o catálogo de Temas o uso dos arranjos já cadastrados
        # (quem instala uma versão nova já vê as datas preenchidas).
        sincronizar_uso_temas(conn)
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


def datas_sem_reuniao(ano: int) -> dict[str, str]:
    """Datas do ano em que não há reunião nenhuma: ``{data: tipo do evento}``.

    São as datas especiais cujo tipo está marcado como sem presidente local —
    assembleia, congresso. Nelas a congregação está fora do salão: não há
    presidente, não se recebe orador e não se manda ninguém para fora, porque
    a congregação de destino costuma estar no mesmo evento.
    """
    sem_presidente = tipos_evento_sem_presidente()
    return {
        data: registro["tipo"]
        for data, registro in listar_datas_especiais_por_ano(ano).items()
        if registro["tipo"] in sem_presidente
    }


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

    # Assembleia e congresso somem das sugestões: ninguém discursa nem viaja
    # nesse fim de semana, e oferecer a data só convida ao erro.
    ocupadas |= set(datas_sem_reuniao(ano))

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

    # Recebido = falará na minha congregação (meus dias de reunião);
    # enviado = falará na outra congregação (os dias dela).
    rotulos = {
        "minha": _rotulo_dia_congregacao(ita_nome, ita_dia, ita_horario),
        "host": _rotulo_dia_congregacao(host_nome, host_dia, host_horario),
        "padrao": "Padrão do mês",
    }
    candidatos = [
        (weekday, rotulos[origem])
        for weekday, origem in weekdays_sugeridos(
            tipo, ita_wd, host_wd, weekday_padrao
        )
    ]

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
    por_fila: bool = False,
) -> list[ft.dropdown.Option]:
    """Lista oradores com congregação para seletores de arranjo.

    Quem faz só o discurso local aparece aqui como qualquer outro: a restrição
    de "aprovado para discursar fora" vale para a lista de oradores que é
    oferecida a outra congregação, não para montar o arranjo do mês.

    ``por_fila`` ordena de quem está há mais tempo sem ser designado para quem
    discursou mais recentemente, em vez de alfabético: é a ordem em que a
    escolha costuma ser feita.
    """
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
    # Agrupado por congregação: procurar "quem é da Vila Nova" fica direto,
    # em vez de uma lista alfabética com todas as congregações misturadas.
    query += " ORDER BY COALESCE(c.nome, 'ZZZ'), o.nome"
    conn = get_connection()
    try:
        df = Tabela.de_consulta(conn, query, params or None)
    finally:
        conn.close()

    linhas = list(df.itertuples())
    if por_fila:
        ultima = ultima_data_discurso_por_orador()
        ordem = oradores_mais_tempo_sem_discurso([li.id for li in linhas], ultima)
        posicao = {oid: indice for indice, oid in enumerate(ordem)}
        linhas.sort(key=lambda li: posicao.get(li.id, 0))

    opcoes: list[ft.dropdown.Option] = []
    congregacao_atual = None
    # Agrupar por congregação só faz sentido na ordem alfabética por
    # congregação; na fila, a ordem é outra e os cabeçalhos atrapalhariam.
    mostrar_grupos = congregacao_id is None and not por_fila
    for row in linhas:
        if mostrar_grupos and row.congregacao != congregacao_atual:
            congregacao_atual = row.congregacao
            titulo = congregacao_atual or "Sem congregação"
            opcoes.append(
                ft.dropdown.Option(
                    key=f"__grupo__{titulo}",
                    content=ft.Text(
                        titulo.upper(),
                        size=fonte(11),
                        weight=ft.FontWeight.W_700,
                        color=COR_DESTAQUE_SUAVE,
                    ),
                    disabled=True,
                )
            )
        texto = row.nome
        if row.congregacao:
            texto = f"{row.nome} — {row.congregacao}"
        opcoes.append(ft.dropdown.Option(key=str(row.id), text=texto))
    return opcoes


def carregar_congregacao(congregacao_id: int) -> dict | None:
    """Carrega uma congregação pelo ID para edição."""
    conn = get_connection()
    try:
        df = Tabela.de_consulta(
            conn,
            "SELECT id, nome, responsavel, telefone, endereco, dia_semana, horario, observacoes "
            "FROM congregacoes WHERE id = ?",
            (congregacao_id,),
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
        df = Tabela.de_consulta(
            conn,
            "SELECT id, nome, telefone, categoria, congregacao_id, observacoes, "
            "COALESCE(contato_id, '') AS contato_id, "
            "COALESCE(aprovado_fora, 1) AS aprovado_fora FROM oradores WHERE id = ?",
            (orador_id,),
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
        "congregacao_id": (
            str(row["congregacao_id"]) if row["congregacao_id"] is not None else None
        ),
        "observacoes": row["observacoes"] or "",
        "contato_id": row["contato_id"] or "",
        "aprovado_fora": bool(row["aprovado_fora"]),
        "temas_nr": carregar_temas_de_orador(int(row["id"])),
    }


# ---------------------------------------------------------------------------
# Utilitários de dados
# ---------------------------------------------------------------------------

def formatar_valor(valor) -> str:
    """Converte um valor de célula para texto exibível."""
    if valor is None:
        return ""
    return str(valor)


def filtrar_dataframe(df: Tabela, termo: str, colunas: list[str]) -> Tabela:
    """Filtra a Tabela pelas colunas informadas (busca das telas)."""
    return filtrar_tabela(df, termo, colunas)


def alinhamento_celula(nome_coluna: str) -> ft.TextAlign:
    """Define alinhamento da célula conforme o tipo de dado."""
    if nome_coluna in COLUNAS_NUMERICAS:
        return ft.TextAlign.RIGHT
    return ft.TextAlign.LEFT


# ---------------------------------------------------------------------------
# Tema e componentes visuais reutilizáveis
# ---------------------------------------------------------------------------

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
    df: Tabela,
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

    colunas_exibir = [c for c in df.colunas if c not in colunas_ocultas]

    rotulo_acoes = config.get("rotulo_coluna_acoes", "Ações")

    colunas = []
    if habilitar_selecao:
        colunas.append(
            ft.DataColumn(
                ft.Text("Selecionar", weight=ft.FontWeight.W_600, size=fonte(12), color=TEXTO_PRIMARIO),
                numeric=False,
            )
        )
    colunas.extend(
            ft.DataColumn(
                ft.Text(
                    _rotulo_coluna(nome, config),
                    weight=ft.FontWeight.W_600,
                    text_align=alinhamento_celula(nome),
                    size=fonte(12),
                    color=TEXTO_PRIMARIO,
                )
            )
        for nome in colunas_exibir
    )
    if coluna_id in df.colunas:
        if acoes_separadas:
            if on_editar:
                colunas.append(
                    ft.DataColumn(
                        ft.Text("Editar", weight=ft.FontWeight.W_600, size=fonte(12), color=TEXTO_PRIMARIO)
                    )
                )
            if on_excluir:
                colunas.append(
                    ft.DataColumn(
                        ft.Text("Excluir", weight=ft.FontWeight.W_600, size=fonte(12), color=TEXTO_PRIMARIO)
                    )
                )
        elif on_editar:
            colunas.append(
                ft.DataColumn(
                    ft.Text(rotulo_acoes, weight=ft.FontWeight.W_600, size=fonte(12), color=TEXTO_PRIMARIO)
                )
            )

    linhas = []
    for indice, linha in enumerate(df.itertuples(index=False, name=None)):
        mapa = dict(zip(df.colunas, linha))
        if config.get("destacar_observacao") and int(mapa.get("tem_observacao", 0) or 0) == 1:
            cor_linha = ft.Colors.with_opacity(0.18, COR_DESTAQUE)
        elif config.get("destacar_restrito") and int(mapa.get("restrito", 0) or 0) == 1:
            cor_linha = ft.Colors.with_opacity(0.14, COR_AVISO)
        elif indice % 2 == 1:
            cor_linha = ft.Colors.with_opacity(cor_alternada, FUNDO_ELEVADO)
        else:
            cor_linha = None
        celulas = []
        registro_id = int(mapa[coluna_id]) if coluna_id in df.colunas else None

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
            controle_celula: ft.Control = ft.Text(
                texto,
                size=fonte(12),
                color=TEXTO_PRIMARIO,
                text_align=alinhamento_celula(nome),
                max_lines=max_linhas,
                overflow=ft.TextOverflow.ELLIPSIS,
                expand=nome == "titulo",
            )
            # Tema prioritário para a minha congregação: estrela junto do título
            # (em vez de expor a coluna 0/1 na tabela). Com `on_prioritario`
            # na config, a estrela vira botão e alterna direto na lista.
            if nome == "titulo" and "prioritario" in mapa:
                eh_prioritario = int(mapa.get("prioritario", 0) or 0) == 1
                ao_alternar = config.get("on_prioritario")
                estrela: ft.Control | None = None
                if ao_alternar and registro_id is not None:
                    estrela = ft.IconButton(
                        icon=ft.Icons.STAR if eh_prioritario else ft.Icons.STAR_BORDER,
                        icon_size=fonte(16),
                        icon_color=COR_AVISO if eh_prioritario else TEXTO_SECUNDARIO,
                        tooltip=(
                            "Tema prioritário — clique para desmarcar"
                            if eh_prioritario
                            else "Marcar como prioritário para a minha congregação"
                        ),
                        style=ft.ButtonStyle(padding=2),
                        on_click=lambda e, rid=registro_id, atual=eh_prioritario: (
                            ao_alternar(rid, not atual)
                        ),
                    )
                elif eh_prioritario:
                    estrela = ft.Icon(
                        ft.Icons.STAR,
                        size=fonte(14),
                        color=COR_AVISO,
                        tooltip="Tema prioritário para a minha congregação",
                    )
                if estrela is not None:
                    controle_celula = ft.Row(
                        [estrela, controle_celula],
                        spacing=4,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
            celulas.append(ft.DataCell(controle_celula))
        if registro_id is not None:
            if acoes_separadas:
                if on_editar:
                    celulas.append(
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                icon_size=fonte(18),
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
                                icon_size=fonte(18),
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
                            icon_size=fonte(18),
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
    df: Tabela,
    on_editar: Callable[[int], None] | None = None,
    on_excluir: Callable[[int], None] | None = None,
    config: dict | None = None,
    coluna_id: str = "id",
) -> ft.Container:
    """Envolve a tabela em container com scroll horizontal e vertical."""
    config = config or {}
    if "coluna_id" not in config:
        config = {**config, "coluna_id": coluna_id}
    tabela = criar_tabela(df, on_editar=on_editar, on_excluir=on_excluir, config=config)
    if eh_mobile():
        # A tabela é mais larga que a tela do celular: rolagem horizontal
        # (arrastar para o lado) além da vertical.
        conteudo = ft.Row([tabela], scroll=ft.ScrollMode.AUTO, tight=True)
    else:
        conteudo = tabela
    return ft.Container(
        content=ft.Column(
            [conteudo],
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
    df: Tabela | Callable[[], Tabela],
    colunas_filtro: list[str],
    barra_acoes: list[ft.Control] | None = None,
    on_editar: Callable[[int], None] | None = None,
    on_excluir: Callable[[int], None] | None = None,
    config_tabela: dict | None = None,
    controles_filtro: list[ft.Control] | None = None,
    on_atualizar_disponivel: Callable[[Callable[[str], None]], None] | None = None,
    renderizador_tabela: Callable[[Tabela, str], ft.Control] | None = None,
    mostrar_cabecalho: bool = True,
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
    DataFrame já filtrado pela busca. Recebe também o termo digitado, para
    quem precisa destacar dentro do cartão o que casou com a busca.
    """
    area_tabela = ft.Container(expand=True)
    texto_contagem = ft.Text(size=fonte(13), color=TEXTO_SECUNDARIO)

    def atualizar_view(termo_busca: str = ""):
        df_atual = df() if callable(df) else df
        df_filtrado = filtrar_dataframe(df_atual, termo_busca, colunas_filtro)
        if renderizador_tabela:
            area_tabela.content = renderizador_tabela(df_filtrado, termo_busca)
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

    if eh_mobile():
        # Celular: cabeçalho enxuto (sem o título de seção "Dados" nem os
        # espaçadores largos) para a lista ocupar o máximo da tela.
        linhas_filtro = []
        if controles_filtro:
            linhas_filtro = [
                ft.Column(
                    controles_filtro,
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                ft.Container(height=8),
            ]
        barra = ft.Column(
            [
                ft.Row([campo_busca]),
                *([ft.Row(barra_acoes, spacing=8, wrap=True)] if barra_acoes else []),
            ],
            spacing=8,
        )
        return ft.Column(
            [
                *(
                    [criar_cabecalho_tela(titulo, descricao), ft.Container(height=8)]
                    if mostrar_cabecalho else []
                ),
                *linhas_filtro,
                barra,
                ft.Container(height=6),
                texto_contagem,
                ft.Container(height=6),
                area_tabela,
            ],
            spacing=0,
            expand=True,
        )

    linhas_filtro = []
    if controles_filtro:
        linhas_filtro = [
            ft.Row(controles_filtro, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=12),
        ]
    barra = ft.Row(itens_barra, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    return ft.Column(
        [
            *(
                [
                    criar_cabecalho_tela(titulo, descricao),
                    ft.Container(height=28),
                    criar_secao_titulo("Dados"),
                    ft.Container(height=12),
                ]
                if mostrar_cabecalho else []
            ),
            *linhas_filtro,
            barra,
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

# Agenda lida do .vcf, guardada só enquanto o app está aberto: assim o
# coordenador escolhe o arquivo uma vez e associa vários nomes na sequência,
# sem que a agenda dele fique gravada em lugar nenhum.
_contatos_da_sessao: list[Contato] = []


def _avatar_contato(nome: str, contato_id: str = "", tamanho: int = 38) -> ft.Control:
    """Foto do contato vinculado; sem foto, as iniciais num círculo.

    A foto vem da agenda do aparelho (a mesma que o WhatsApp costuma
    sincronizar nos contatos) e fica em cache na área do app.
    """
    caminho = caminho_foto_contato(contato_id, FOTOS_DIR) if contato_id else None
    if caminho:
        return ft.Container(
            content=ft.Image(
                src=str(caminho),
                width=tamanho,
                height=tamanho,
                fit=ft.BoxFit.COVER,
                border_radius=tamanho // 2,
            ),
            width=tamanho,
            height=tamanho,
            border_radius=tamanho // 2,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
    return ft.Container(
        content=ft.Text(
            iniciais_do_nome(nome),
            size=fonte(13),
            weight=ft.FontWeight.W_700,
            color=COR_DESTAQUE_SUAVE,
        ),
        width=tamanho,
        height=tamanho,
        border_radius=tamanho // 2,
        bgcolor=ft.Colors.with_opacity(0.16, COR_DESTAQUE),
        alignment=ft.Alignment.CENTER,
    )


def sincronizar_contatos_vinculados(page: ft.Page, ao_terminar=None) -> None:
    """Relê na agenda os contatos vinculados e atualiza os telefones salvos.

    Roda em silêncio na abertura do app: quem trocou de número no celular
    aparece com o número novo aqui, sem ninguém precisar reeditar o cadastro.
    Só existe no celular — no PC não há agenda para consultar.
    """
    if _contatos_nativo_global is None:
        return
    vinculos = listar_vinculos_de_contato()
    if not vinculos:
        return

    async def _sincronizar() -> None:
        try:
            lidos = await _contatos_nativo_global.reler(
                [v["contato_id"] for v in vinculos]
            )
        except Exception:  # noqa: BLE001 — sem permissão/agenda: segue como está
            logger.exception("Não foi possível reler os contatos vinculados")
            return

        # As fotos são atualizadas sempre; o telefone, só quando mudou.
        for contato in lidos:
            salvar_foto_contato(contato.get("id", ""), contato.get("foto"), FOTOS_DIR)

        mudancas = mudancas_de_contato(vinculos, lidos)
        alterados = 0
        for mudanca in mudancas:
            alterados += atualizar_telefone_por_contato(
                mudanca["tabela"], mudanca["id"], mudanca["telefone"]
            )
        # Sem aviso na tela: isto roda toda vez que o app abre, e um pop-up a
        # cada abertura vira incômodo. Quem quiser conferir vê o número no
        # cadastro; o log guarda o que mudou.
        if alterados:
            logger.info("Contatos: %d telefone(s) atualizados pela agenda", alterados)
        if ao_terminar is not None:
            ao_terminar()

    page.run_task(_sincronizar)


def _campo_telefone(rotulo: str = "Telefone", valor: str = "", **extras) -> ft.TextField:
    """Campo de telefone que se formata sozinho enquanto é digitado.

    Guardar o número já formatado não atrapalha nada: quem monta o link do
    WhatsApp tira a pontuação de qualquer jeito.
    """
    campo = ft.TextField(
        label=rotulo,
        value=mascara_telefone(valor),
        keyboard_type=ft.KeyboardType.PHONE,
        **extras,
    )

    def formatar(e=None):
        formatado = mascara_telefone(campo.value or "")
        if formatado != campo.value:
            campo.value = formatado
            campo.update()

    campo.on_change = formatar
    return campo


def _botao_buscar_contato(
    page: ft.Page,
    campo_telefone: ft.TextField,
    campo_nome: ft.TextField | None = None,
    estado_vinculo: dict | None = None,
) -> ft.Control:
    """Botão que associa a pessoa a um contato do celular.

    No celular abre a agenda do próprio sistema (extensão ``flet_contatos``).
    No computador — onde o pacote nativo não existe — e sempre que o seletor
    não estiver disponível, cai no arquivo ``.vcf`` exportado do aparelho.

    ``estado_vinculo`` recebe o ``contato_id`` do escolhido: é o que faz o
    telefone acompanhar sozinho o que mudar na agenda depois.
    """

    def escolher(contato: Contato):
        # Número vindo pronto da agenda: sem inventar DDD se ele não tiver.
        campo_telefone.value = mascara_telefone(contato.telefone, digitando=False)
        if campo_nome is not None and not (campo_nome.value or "").strip():
            campo_nome.value = contato.nome
        page.update()

    async def abrir_nativo() -> None:
        try:
            escolhido = await _contatos_nativo_global.escolher()
        except Exception:  # noqa: BLE001 — sem agenda/plugin: usa o .vcf
            logger.exception("Seletor nativo de contatos indisponível")
            abrir_dialog_escolher_contato(page, escolher)
            return
        if escolhido is None:
            # Cancelou ou negou a permissão: não force o outro caminho.
            return
        telefones = [
            numero
            for numero in (formatar_telefone(t) for t in escolhido.get("telefones", []))
            if numero
        ]
        if not telefones:
            mostrar_aviso(
                page,
                "Contato sem telefone",
                f"{escolhido.get('nome') or 'O contato'} não tem número salvo.",
            )
            return
        contato_id = escolhido.get("id") or ""
        if estado_vinculo is not None:
            estado_vinculo["contato_id"] = contato_id
        salvar_foto_contato(contato_id, escolhido.get("foto"), FOTOS_DIR)
        escolher(Contato(escolhido.get("nome") or "", telefones))

    def ao_clicar(_=None):
        if _contatos_nativo_global is not None:
            page.run_task(abrir_nativo)
        else:
            abrir_dialog_escolher_contato(page, escolher)

    return ft.TextButton(
        content="Buscar nos contatos",
        icon=ft.Icons.CONTACT_PHONE_OUTLINED,
        tooltip="Preencher o telefone a partir dos contatos do celular",
        on_click=ao_clicar,
    )


def abrir_dialog_escolher_contato(
    page: ft.Page, ao_escolher: Callable[[Contato], None]
) -> None:
    """Lista os contatos do .vcf para o usuário escolher um."""
    campo_busca = ft.TextField(
        label="Buscar por nome ou número",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
    )
    lista = ft.Column(spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, height=280)
    aviso = ft.Text("", size=fonte(12), color=TEXTO_SECUNDARIO)

    def fechar(_=None):
        page.pop_dialog()

    def preencher(_=None):
        encontrados = filtrar_contatos(_contatos_da_sessao, campo_busca.value or "")
        aviso.value = (
            f"{len(encontrados)} de {len(_contatos_da_sessao)} contato(s)"
            if _contatos_da_sessao
            else ""
        )
        if not _contatos_da_sessao:
            lista.controls = [
                ft.Text(
                    "Nenhuma agenda carregada ainda. Exporte seus contatos no "
                    "celular (Contatos → Configurações → Exportar) e abra o "
                    "arquivo .vcf aqui.",
                    size=fonte(13),
                    color=TEXTO_SECUNDARIO,
                    italic=True,
                )
            ]
        elif not encontrados:
            lista.controls = [
                ft.Text("Nenhum contato com esse nome ou número.",
                        size=fonte(13), color=TEXTO_SECUNDARIO, italic=True)
            ]
        else:
            lista.controls = [
                ft.ListTile(
                    dense=True,
                    leading=ft.Icon(ft.Icons.PERSON_OUTLINE, size=fonte(18),
                                    color=COR_DESTAQUE),
                    title=ft.Text(contato.nome, size=fonte(13)),
                    subtitle=ft.Text(" · ".join(contato.telefones), size=fonte(12)),
                    on_click=lambda e, c=contato: (fechar(), ao_escolher(c)),
                )
                for contato in encontrados[:300]
            ]
        page.update()

    campo_busca.on_change = preencher

    async def carregar_arquivo(_=None):
        picker = _file_picker_global
        if picker is None:
            mostrar_aviso(page, "Indisponível", "Seletor de arquivos indisponível.")
            return
        arquivos = await picker.pick_files(
            dialog_title="Selecione o arquivo de contatos (.vcf)",
            allowed_extensions=["vcf", "vcard"],
            allow_multiple=False,
        )
        if not arquivos:
            return
        try:
            texto = Path(arquivos[0].path).read_text(encoding="utf-8", errors="replace")
            lidos = ler_vcard(texto)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao ler o arquivo de contatos")
            mostrar_aviso(page, "Não foi possível ler", f"Detalhes: {exc}")
            return
        if not lidos:
            mostrar_aviso(
                page,
                "Nenhum contato com telefone",
                "O arquivo foi lido, mas não tem contatos com número.",
            )
            return
        _contatos_da_sessao.clear()
        _contatos_da_sessao.extend(lidos)
        preencher()

    preencher()
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Contatos do celular"),
            content=ft.Container(
                width=_largura_dialog(page, 460),
                content=ft.Column(
                    [
                        ft.Text(
                            "Exporte a agenda no celular (Contatos → "
                            "Configurações → Exportar) e abra o arquivo .vcf "
                            "aqui. Só o número escolhido é salvo.",
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Container(height=8),
                        ft.Row(
                            [
                                ft.OutlinedButton(
                                    content="Abrir arquivo .vcf",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    on_click=lambda _: page.run_task(carregar_arquivo),
                                )
                            ],
                            wrap=True,
                        ),
                        ft.Container(height=8),
                        campo_busca,
                        aviso,
                        lista,
                    ],
                    spacing=4,
                    tight=True,
                ),
            ),
            actions=[ft.TextButton("Fechar", on_click=fechar)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


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
    campo_telefone = _campo_telefone(valor=dados["telefone"] if dados else "", expand=True)
    # Guarda a que contato da agenda este orador está amarrado.
    vinculo_orador = {"contato_id": (dados or {}).get("contato_id", "")}
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
    # Quem faz só o discurso local fica de fora da lista de oradores que é
    # oferecida a outra congregação — mandar quem não pode ir só dá trabalho.
    campo_aprovado_fora = ft.Checkbox(
        label="Aprovado para discursar em outras congregações",
        value=dados.get("aprovado_fora", True) if dados else True,
        tooltip=(
            "Desmarque para quem faz apenas o discurso local: ele fica de "
            "fora da lista de oradores enviada a outras congregações. No "
            "arranjo do mês ele continua disponível normalmente."
        ),
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
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

    temas_selecionados: set[int] = set(dados["temas_nr"]) if dados else set()
    df_temas = carregar_dados("SELECT nr, titulo FROM temas ORDER BY nr")
    lista_temas = ft.Column(spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, height=220)
    texto_contagem_temas = ft.Text(size=fonte(12), color=TEXTO_SECUNDARIO)
    texto_qualquer_tema = ft.Text(
        "Este orador pode fazer qualquer tema. Não é preciso selecionar.",
        size=fonte(12),
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
            rotulo = f"{row.nr} - {row.titulo}"
            if filtro and filtro not in rotulo.lower():
                continue
            # Checkbox sem label + texto com quebra: o label nativo não
            # quebra linha e era cortado na borda do dialog no celular.
            caixa = ft.Checkbox(
                value=row.nr in temas_selecionados,
                on_change=lambda e, nr=row.nr: alternar_tema(nr, e.control.value),
            )

            def alternar_pelo_texto(e, nr=row.nr, caixa=caixa):
                caixa.value = not caixa.value
                alternar_tema(nr, caixa.value)

            linhas.append(
                ft.Container(
                    content=ft.Row(
                        [
                            caixa,
                            ft.Text(
                                rotulo,
                                size=fonte(13),
                                expand=True,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    on_click=alternar_pelo_texto,
                    padding=ft.Padding.symmetric(vertical=2),
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
        try:
            salvar_orador(
                nome,
                campo_telefone.value.strip(),
                campo_categoria.value,
                congregacao_id,
                observacoes_final,
                temas_selecionados,
                orador_id=orador_id if editando else None,
                contato_id=vinculo_orador["contato_id"],
                aprovado_fora=bool(campo_aprovado_fora.value),
            )
        except sqlite3.IntegrityError:
            # O banco não aceita dois oradores com o mesmo nome na mesma
            # congregação; sem este aviso o erro subia e derrubava o app.
            texto_erro.value = (
                f'Já existe um orador chamado "{nome}" nessa congregação.'
            )
            texto_erro.visible = True
            page.update()
            return
        except Exception:  # noqa: BLE001 — o formulário não pode derrubar o app
            logger.exception("Falha ao salvar orador")
            texto_erro.value = "Não foi possível salvar este orador."
            texto_erro.visible = True
            page.update()
            return

        fechar()
        recarregar()

    # Enter no campo de nome salva o formulário.
    campo_nome.on_submit = salvar

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Editar orador" if editando else "Novo orador"),
        content=ft.Container(
            content=ft.Column(
                [
                    campo_nome,
                    campo_telefone,
                    ft.Row(
                        [_botao_buscar_contato(
                            page, campo_telefone, campo_nome, vinculo_orador
                        )],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                    linha_campos(campo_categoria, campo_congregacao),
                    campo_aprovado_fora,
                    campo_observacoes,
                    texto_erro,
                    ft.Container(height=4),
                    campo_qualquer_tema,
                    ft.Text("Temas que pode fazer", weight=ft.FontWeight.W_600, size=fonte(13)),
                    texto_qualquer_tema,
                    campo_busca_temas,
                    lista_temas,
                    texto_contagem_temas,
                ],
                spacing=12,
                tight=True,
                width=_largura_dialog(page, 480),
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
            logger.exception("Falha ao excluir orador")
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
    campo_telefone = _campo_telefone(valor=dados["telefone"] if dados else "", expand=True)
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
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

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
        except sqlite3.IntegrityError:
            texto_erro.value = "Já existe uma congregação com esse nome."
            texto_erro.visible = True
            page.update()
            return
        except Exception:
            logger.exception("Falha ao salvar congregação")
            texto_erro.value = "Não foi possível salvar a congregação."
            texto_erro.visible = True
            page.update()
            return

        fechar()
        recarregar()

    # Enter no campo de nome salva o formulário.
    campo_nome.on_submit = salvar

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar congregação" if editando else "Nova congregação"),
            content=ft.Container(
                content=ft.Column(
                    [
                        campo_nome,
                        linha_campos(campo_responsavel, campo_telefone),
                        campo_endereco,
                        linha_campos(campo_dia, campo_horario),
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=_largura_dialog(page, 480),
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
            logger.exception("Falha ao excluir congregação")
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

def copiar_texto(page: ft.Page, texto: str, mensagem: str = "Copiado.") -> None:
    """Copia texto para a área de transferência.

    O Flet 0.86 removeu o antigo método de clipboard da Page e pôs no lugar o
    serviço ``Clipboard``, que é assíncrono — a chamada antiga derrubava o app
    inteiro no Android com ``AttributeError``. O serviço vem do ``main()``,
    onde é criado junto com os demais (Share, FilePicker).
    """
    servico = _clipboard_global
    if servico is None:
        mostrar_aviso(
            page,
            "Não foi possível copiar",
            "A área de transferência não está disponível neste aparelho.",
        )
        return

    async def _copiar() -> None:
        try:
            await servico.set(texto)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao copiar para a área de transferência")
            mostrar_aviso(page, "Não foi possível copiar", str(exc))
            return
        if mensagem:
            mostrar_sucesso(page, mensagem)

    page.run_task(_copiar)


def entregar_arquivo(page: ft.Page, caminho, abrir_desktop) -> None:
    """Entrega ao usuário um arquivo já gerado em `exports/`.

    No PC executa `abrir_desktop(caminho)` (abre o arquivo ou a pasta, como
    antes). No celular abre o diálogo "salvar em..." do sistema, para o arquivo
    sair da área privada do app (Downloads, Drive, WhatsApp, etc.).
    """
    caminho = str(caminho)
    if not eh_mobile():
        abrir_desktop(caminho)
        return

    async def _salvar():
        from pathlib import Path as _P

        picker = _file_picker_global
        if picker is None:
            mostrar_aviso(page, "Não foi possível salvar",
                          "Seletor de arquivos indisponível.")
            return
        try:
            await picker.save_file(
                dialog_title="Salvar arquivo",
                file_name=_P(caminho).name,
                src_bytes=_P(caminho).read_bytes(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao salvar o arquivo no aparelho")
            mostrar_aviso(page, "Não foi possível salvar o arquivo",
                          f"Detalhes: {exc}")

    page.run_task(_salvar)


def exportar_relatorio_pdf(
    page: ft.Page,
    montar_secoes: Callable[[], list[dict]],
    titulo: str,
    nome_arquivo: str,
) -> None:
    """Gera e entrega o relatório em PDF de uma tela.

    ``montar_secoes`` só é chamada aqui dentro (e não pelo chamador) para a
    leitura do banco acontecer junto com o anel de progresso — em ano cheio,
    montar a programação inteira demora o bastante para a tela travar sem ele.
    """
    from relatorios import identificacao_congregacao

    congregacao, contato = identificacao_congregacao()
    try:
        caminho, erro = executar_com_progresso(
            page,
            "Gerando PDF...",
            lambda: gerar_pdf_secoes(
                montar_secoes(),
                titulo,
                congregacao=congregacao,
                contato=contato,
                nome_arquivo=nome_arquivo,
            ),
        )
        if erro:
            mostrar_aviso(page, "Não foi possível exportar", erro)
            return
        entregar_arquivo(page, caminho, abrir_arquivo)
        if not eh_mobile():
            mostrar_sucesso(page, f"Relatório gerado: {caminho}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao gerar relatório em PDF")
        mostrar_aviso(page, "Erro", f"Não foi possível gerar o PDF: {exc}")


def botao_relatorio_tela(on_click: Callable) -> ft.Control:
    """Botão padrão de 'Relatório' usado no topo de cada tela."""
    return ft.OutlinedButton(
        content="Relatório",
        icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
        tooltip="Exportar em PDF o que esta tela mostra",
        on_click=on_click,
    )


def somente_discurso_local(orador_ids) -> set[int]:
    """Dos ids informados, quais fazem apenas o discurso local."""
    ids = [int(i) for i in orador_ids]
    if not ids:
        return set()
    marcadores = ",".join("?" * len(ids))
    conn = get_connection()
    try:
        return {
            int(linha[0])
            for linha in conn.execute(
                f"SELECT id FROM oradores WHERE id IN ({marcadores}) "  # noqa: S608
                "AND COALESCE(aprovado_fora, 1) = 0",
                ids,
            )
        }
    finally:
        conn.close()


def acionar_geracao_pdf_envio(page: ft.Page, orador_ids: set[int]) -> None:
    """Gera o PDF de envio de oradores selecionados ou exibe aviso."""
    if not orador_ids:
        mostrar_aviso(
            page,
            "Nenhum orador selecionado",
            "Marque pelo menos um orador na coluna \"Selecionar\" antes de gerar o PDF.",
        )
        return

    # Segunda tranca: a lista trava o checkbox de quem faz só o discurso
    # local, mas a marcação pode ter sido feita ANTES de o cadastro mudar.
    # Este PDF é o que vai para outra congregação — não pode oferecer quem
    # não pode ir.
    orador_ids = set(orador_ids) - somente_discurso_local(orador_ids)
    if not orador_ids:
        mostrar_aviso(
            page,
            "Nenhum orador disponível",
            "Os oradores marcados fazem apenas o discurso local e não podem "
            "ser oferecidos a outra congregação.",
        )
        return

    try:
        from pdf_envio import gerar_pdf_envio  # importado sob demanda (desktop)

        caminho, erro = executar_com_progresso(
            page, "Gerando PDF...", lambda: gerar_pdf_envio(list(orador_ids))
        )
        if erro:
            mostrar_aviso(page, "Não foi possível gerar o PDF", erro)
            return

        entregar_arquivo(page, caminho, abrir_arquivo)
        if not eh_mobile():
            mostrar_aviso(
                page,
                "PDF gerado com sucesso",
                f"A lista de oradores para envio foi salva em:\n{caminho}",
            )
    except Exception as exc:
        logger.exception("Falha ao gerar o PDF da lista de envio")
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
    """Datas de reunião de fim de semana da minha congregação num mês.

    O dia vem da linha do tempo: a congregação muda de dia de tempos em
    tempos, e usar sempre o dia de hoje fazia a Programação de 2021 (domingo)
    procurar sábados — as semanas apareciam vazias com tudo gravado.
    Sem registro para aquele mês, vale a configuração atual.
    """
    periodo = reuniao_em(ano, mes)
    dia = periodo["dia_semana"] if periodo else carregar_configuracao().get("dia_reuniao", "")
    weekday = _dia_semana_para_weekday(dia)
    if weekday is None:
        weekday = 5
    return _datas_por_weekday_no_mes(ano, mes, weekday)


# Cor de cada nível de urgência devolvido por rotulo_de_prazo.
CORES_PRAZO = {
    "vencido": COR_ERRO,
    "urgente": COR_ERRO,
    "atencao": COR_AVISO,
    "tranquilo": TEXTO_SECUNDARIO,
    "": TEXTO_SECUNDARIO,
}


def _linha_pendencia(data_pendencia, texto: str, hoje: date) -> ft.Control:
    """Uma pendência do Início: o que falta e para quando."""
    prazo, nivel = rotulo_de_prazo(data_pendencia, hoje)
    cor = CORES_PRAZO.get(nivel, TEXTO_SECUNDARIO)
    conteudo: list[ft.Control] = [
        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=fonte(15), color=cor),
        ft.Text(texto, size=fonte(12), color=TEXTO_PRIMARIO, expand=True, max_lines=2),
    ]
    if prazo:
        conteudo.append(
            ft.Text(prazo, size=fonte(11), color=cor, weight=ft.FontWeight.W_600)
        )
    return ft.Row(
        [c for c in conteudo],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


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
    # A primeira data que ainda está sem: é dela que sai o prazo mostrado nas
    # pendências do Início. Contar quantas faltam não diz se corre ou espera.
    def _primeira_sem(preenchidas: dict) -> date | None:
        for data_semana in semanas:
            chave = _formatar_data_arranjo(data_semana)
            if chave not in preenchidas and chave not in especiais:
                return data_semana
        return None

    return {
        "semanas": len(semanas),
        "cobertas": cobertas,
        "presidentes": pres_definidos,
        "recebidos": contagens["recebidos"],
        "enviados": contagens["enviados"],
        "primeira_sem_orador": _primeira_sem(recebidos),
        "primeira_sem_presidente": _primeira_sem(presidentes),
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
    chip_data = ft.Container(
        content=ft.Text(
            data_ref.strftime("%d/%m"),
            size=fonte(12),
            weight=ft.FontWeight.W_600,
            color=COR_AVISO,
        ),
        bgcolor=ft.Colors.with_opacity(0.14, COR_AVISO),
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )
    chip_tipo = ft.Container(
        content=ft.Text(
            especial.get("tipo", "Data especial"),
            size=fonte(12),
            weight=ft.FontWeight.W_600,
            color=COR_AVISO,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        bgcolor=ft.Colors.with_opacity(0.10, COR_AVISO),
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )

    if eh_mobile():
        # Empilhado, como as demais linhas da agenda no celular.
        corpo = [chip_tipo]
        if detalhes:
            corpo.append(
                ft.Text(detalhes, size=fonte(12), color=TEXTO_SECUNDARIO,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
            )
        if presidente:
            corpo.append(
                ft.Text(f"Pres.: {presidente}", size=fonte(12), color=TEXTO_SECUNDARIO,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
            )
        return ft.Row(
            [
                chip_data,
                ft.Column(corpo, spacing=2, tight=True, expand=True,
                          horizontal_alignment=ft.CrossAxisAlignment.START),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    return ft.Row(
        [
            chip_data,
            chip_tipo,
            ft.Text(
                detalhes,
                size=fonte(12),
                color=TEXTO_SECUNDARIO,
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                f"Pres.: {presidente}" if presidente else "",
                size=fonte(12),
                color=TEXTO_SECUNDARIO,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _botao_mensagem_presidencia(
    on_mensagem: Callable[[date], None] | None,
    data_ref: date,
    tem_presidente: bool,
) -> ft.Control | None:
    """Botão que abre a mensagem da presidência daquela data (WhatsApp).

    Só aparece com presidente definido — sem ele não há para quem mandar.
    """
    if not on_mensagem or not tem_presidente:
        return None
    return ft.IconButton(
        icon=ft.Icons.CHAT_OUTLINED,
        icon_size=fonte(18),
        icon_color="#34D399",
        tooltip="Mandar a mensagem da presidência (WhatsApp)",
        style=ft.ButtonStyle(padding=4),
        on_click=lambda e, d=data_ref: on_mensagem(d),
    )


def _linha_agenda_inicio(
    data_ref: date,
    recebidos: dict[str, dict],
    presidentes: dict[str, dict],
    especiais: dict[str, dict] | None = None,
    on_mensagem: Callable[[date], None] | None = None,
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

    chip_data = ft.Container(
        content=ft.Text(
            data_ref.strftime("%d/%m"),
            size=fonte(12),
            weight=ft.FontWeight.W_600,
            color=COR_DESTAQUE_SUAVE,
        ),
        bgcolor=ft.Colors.with_opacity(0.14, COR_DESTAQUE_CLARA),
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )
    texto_presidente = ft.Text(
        f"Pres.: {presidente['nome']}" if presidente else "sem presidente",
        size=fonte(12),
        color=TEXTO_SECUNDARIO if presidente else COR_ERRO,
        max_lines=1,
        no_wrap=True,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    botao_mensagem = _botao_mensagem_presidencia(
        on_mensagem, data_ref, bool(presidente)
    )

    if eh_mobile():
        # Item empilhado: orador, tema e presidente cada um em sua linha,
        # todos limitados pela largura da coluna — nada é cortado.
        return ft.Row(
            [
                chip_data,
                ft.Column(
                    [
                        ft.Text(
                            orador,
                            size=fonte(13),
                            weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO if info else TEXTO_SECUNDARIO,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        *(
                            [
                                ft.Text(
                                    tema or ("sem orador definido" if not info else "sem tema"),
                                    size=fonte(12),
                                    color=TEXTO_SECUNDARIO,
                                    italic=not tema,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                )
                            ]
                        ),
                        texto_presidente,
                    ],
                    spacing=2,
                    tight=True,
                    expand=True,
                ),
                *([botao_mensagem] if botao_mensagem else []),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    return ft.Row(
        [
            chip_data,
            ft.Text(
                orador,
                size=fonte(13),
                weight=ft.FontWeight.W_600,
                color=TEXTO_PRIMARIO if info else TEXTO_SECUNDARIO,
                width=150,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                tema or ("sem orador definido" if not info else "sem tema"),
                size=fonte(12),
                color=TEXTO_SECUNDARIO,
                italic=not tema,
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            texto_presidente,
            *([botao_mensagem] if botao_mensagem else []),
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
    mobile = eh_mobile()
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(icone or ft.Icons.INSIGHTS, size=fonte(20), color=cor_valor),
                    bgcolor=ft.Colors.with_opacity(0.12, cor_valor),
                    border_radius=10,
                    padding=8 if mobile else 10,
                ),
                # expand + elipse: no celular o card é estreito e o texto era
                # cortado sem aviso.
                ft.Column(
                    [
                        ft.Text(
                            rotulo,
                            size=fonte(11) if mobile else fonte(12),
                            color=TEXTO_SECUNDARIO,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            [
                                ft.Text(valor, size=fonte(22), weight=ft.FontWeight.W_700, color=cor_valor),
                                ft.Text(
                                    detalhe,
                                    size=fonte(11) if mobile else fonte(12),
                                    color=TEXTO_SECUNDARIO,
                                    expand=True,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                    ],
                    spacing=2,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=10 if mobile else 12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=12 if mobile else 16, vertical=12 if mobile else 14),
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
    on_mensagem: Callable[[date], None] | None = None,
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
                    size=fonte(30),
                    weight=ft.FontWeight.W_700,
                    color=COR_DESTAQUE_SUAVE if not especial else COR_AVISO,
                ),
                ft.Text(
                    NOMES_MESES[data_ref.month][:3].upper(),
                    size=fonte(12),
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

    dia_semana = DIAS_SEMANA_EXTENSO[data_ref.weekday()]
    if eh_mobile():
        # No celular o dia da semana entra no próprio chip ("Em 6 dias ·
        # Sábado") — como texto solto ele era espremido para "S…".
        rotulo_quando = f"{quando} · {dia_semana}"
        itens_cabecalho = [
            ft.Text(
                "PRÓXIMA REUNIÃO",
                size=fonte(11),
                weight=ft.FontWeight.W_700,
                color=TEXTO_SECUNDARIO,
            ),
            ft.Container(
                content=ft.Text(rotulo_quando, size=fonte(11), weight=ft.FontWeight.W_600, color=cor_borda),
                bgcolor=ft.Colors.with_opacity(0.12, cor_borda),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            ),
        ]
        cabecalho_card = ft.Row(
            itens_cabecalho,
            spacing=8,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    else:
        cabecalho_card = ft.Row(
            [
                ft.Text(
                    "PRÓXIMA REUNIÃO",
                    size=fonte(11),
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Container(
                    content=ft.Text(quando, size=fonte(11), weight=ft.FontWeight.W_600, color=cor_borda),
                    bgcolor=ft.Colors.with_opacity(0.12, cor_borda),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                ),
                ft.Text(
                    dia_semana,
                    size=fonte(11),
                    color=TEXTO_SECUNDARIO,
                    expand=True,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    detalhes: list[ft.Control] = [
        cabecalho_card,
        ft.Text(
            titulo_principal,
            size=fonte(18),
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
                size=fonte(13),
                color=TEXTO_SECUNDARIO,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )
    detalhes.append(
        ft.Text(
            f"Presidente: {rotulo_presidente}" if rotulo_presidente else "Presidente: a definir",
            size=fonte(12),
            color=TEXTO_SECUNDARIO if rotulo_presidente else COR_ERRO,
        )
    )
    # A mensagem da presidência é da reunião normal: numa assembleia/congresso
    # não há o que anunciar, então o botão não aparece.
    if on_mensagem and presidente and not especial:
        detalhes.append(
            ft.Row(
                [
                    ft.OutlinedButton(
                        content="Mensagem da presidência",
                        icon=ft.Icons.CHAT_OUTLINED,
                        on_click=lambda e, d=data_ref: on_mensagem(d),
                    )
                ],
                wrap=True,
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
    assunto = mapa.get("assunto") if mapa.get("assunto") not in (None, "—") else ""
    colunas = [
        ft.Container(
            content=ft.Text(
                str(mapa["nr"]),
                size=fonte(12),
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
            size=fonte(13),
            color=TEXTO_PRIMARIO,
            expand=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    ]
    # A coluna de assunto rouba largura no celular e empurra o "Nunca" para
    # fora da tela; mostra só no desktop.
    if not eh_mobile():
        colunas.append(
            ft.Text(
                assunto,
                size=fonte(11),
                color=TEXTO_SECUNDARIO,
                width=180,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )
    colunas.append(
        ft.Container(
            content=ft.Text(
                ultimo,
                size=fonte(11),
                weight=ft.FontWeight.W_600,
                color=COR_AVISO if ultimo == "Nunca" else TEXTO_SECUNDARIO,
                no_wrap=True,
            ),
            width=64,
            alignment=ft.Alignment.CENTER_RIGHT,
        )
    )
    return ft.Row(
        colunas,
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

    _cards_kpi = [
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
    ]
    if eh_mobile():
        kpis = ft.Column(
            [
                ft.Row(_cards_kpi[:2], spacing=10),
                ft.Row(_cards_kpi[2:], spacing=10),
            ],
            spacing=10,
        )
    else:
        kpis = ft.Row(_cards_kpi, spacing=12)

    def mensagem_presidencia(data_ref: date):
        """Mensagem que o coordenador manda ao presidente daquela reunião."""
        data_str = _formatar_data_arranjo(data_ref)
        info = recebidos.get(data_str) or {}
        abrir_dialog_mensagem_presidencia(
            page,
            data_str,
            presidentes.get(data_str) or {},
            orador=info.get("orador", ""),
            congregacao=info.get("congregacao", ""),
            tema=info.get("tema", ""),
        )

    proximas = _proximas_datas_reuniao(5)
    card_destaque = (
        _card_proxima_reuniao(
            proximas[0], recebidos, presidentes, especiais, mensagem_presidencia
        )
        if proximas
        else None
    )
    linhas_agenda = [
        _linha_agenda_inicio(
            data_ref, recebidos, presidentes, especiais, mensagem_presidencia
        )
        for data_ref in proximas[1:]
    ]
    card_agenda = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Semanas seguintes", size=fonte(14), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
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

    # (data da falha, texto). A data ordena a lista e vira o prazo na tela;
    # None é pendência sem data marcada, como as que esperam resposta.
    pendencias: list[tuple[date | None, str]] = []
    # Cache por ano: a janela de atenção pode cruzar a virada (nov → jan).
    dados_por_ano: dict[int, dict] = {
        ano: {
            "arranjos": arranjos,
            "recebidos": recebidos,
            "presidentes": presidentes,
            "especiais": especiais,
            "contagens": contar_designacoes_por_mes(ano),
        }
    }

    def dados_ano(ano_ref: int) -> dict:
        if ano_ref not in dados_por_ano:
            dados_por_ano[ano_ref] = {
                "arranjos": {a["mes_inicio"]: a for a in carregar_arranjos_por_ano(ano_ref)},
                "recebidos": carregar_recebidos_por_ano(ano_ref),
                "presidentes": carregar_presidentes_por_ano(ano_ref),
                "especiais": listar_datas_especiais_por_ano(ano_ref),
                "contagens": contar_designacoes_por_mes(ano_ref),
            }
        return dados_por_ano[ano_ref]

    for ano_ref, mes_ref in meses_de_atencao(ano, mes, MESES_DE_ATENCAO):
        dados = dados_ano(ano_ref)
        if mes_ref not in dados["arranjos"]:
            continue
        r = _resumo_mes_programacao(
            ano_ref, mes_ref, dados["recebidos"], dados["presidentes"],
            dados["contagens"], dados["especiais"],
        )
        nome_mes = NOMES_MESES[mes_ref]
        if ano_ref != ano:
            nome_mes = f"{nome_mes}/{ano_ref}"
        if r["semanas"] and r["cobertas"] == 0:
            pendencias.append(
                (r["primeira_sem_orador"], f"{nome_mes}: nenhuma semana com orador")
            )
        elif r["cobertas"] < r["semanas"]:
            pendencias.append((
                r["primeira_sem_orador"],
                f"{nome_mes}: só {r['cobertas']} de {r['semanas']} semanas com orador",
            ))
        if r["cobertas"] and r["presidentes"] < r["semanas"]:
            faltam = r["semanas"] - r["presidentes"]
            pendencias.append((
                r["primeira_sem_presidente"],
                f"{nome_mes}: {faltam} semana(s) sem presidente",
            ))

    # Designações aguardando confirmação do orador (status "pendente").
    # Ordem por proximidade: o que acontece antes cobra antes. Sem data (as
    # que esperam resposta) fica no fim do bloco datado.
    pendencias.sort(key=lambda item: item[0] or date.max)

    aguardando = contar_designacoes_por_status(ano).get("pendente", 0)
    if aguardando:
        texto_aguardando = f"{aguardando} designação(ões) aguardando confirmação"
        parados = contar_convites_sem_resposta(ano, DIAS_SEM_RESPOSTA)
        if parados:
            texto_aguardando += (
                f" · {parados} sem resposta há {DIAS_SEM_RESPOSTA}+ dias"
            )
        pendencias.insert(0, (None, texto_aguardando))

    # Conflitos (mesmo orador na mesma data) vêm primeiro — são os mais críticos.
    conflitos = detectar_conflitos_oradores(carregar_designacoes_ano(ano))
    for conflito in reversed(conflitos[:3]):
        nome = conflito["orador_nome"] or "Orador"
        pendencias.insert(0, (
            _parse_data_arranjo(conflito["data"]),
            f"Conflito: {nome} em {conflito['data']} ({conflito['ocorrencias']}×)",
        ))

    if len(pendencias) > 6:
        restante = len(pendencias) - 6
        pendencias = pendencias[:6] + [(None, f"… e mais {restante} pendência(s)")]

    linhas_pendencias: list[ft.Control] = [
        _linha_pendencia(data_pendencia, texto, hoje)
        for data_pendencia, texto in pendencias
    ] or [
        ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=fonte(15), color=COR_SUCESSO),
                ft.Text("Tudo em dia até o fim do ano.", size=fonte(12), color=TEXTO_PRIMARIO),
            ],
            spacing=8,
        )
    ]

    def exportar_quadro_atual(_=None):
        try:
            caminho, erro = executar_com_progresso(
                page, "Gerando PDF...", lambda: gerar_quadro_anuncios(ano, mes)
            )
            if erro:
                mostrar_aviso(page, "Não foi possível exportar", erro)
                return
            entregar_arquivo(page, caminho, abrir_arquivo)
            if not eh_mobile():
                mostrar_sucesso(page, f"Quadro exportado: {caminho}")
        except Exception as exc:
            logger.exception("Falha ao exportar o quadro do mês")
            mostrar_aviso(page, "Erro", f"Não foi possível gerar o PDF: {exc}")

    par_inicio, par_fim = par_meses_do_mes_quadro(mes)
    card_pendencias = ft.Container(
        content=ft.Column(
            [
                ft.Text("Pendências", size=fonte(14), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
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
                ft.Text("Ações rápidas", size=fonte(14), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
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
                    "Temas",
                    icon=ft.Icons.MENU_BOOK_OUTLINED,
                    on_click=lambda _: ir_para(5),
                ),
                ft.OutlinedButton(
                    "Relatórios",
                    icon=ft.Icons.ASSESSMENT_OUTLINED,
                    on_click=lambda _: ir_para(INDICE_RELATORIOS),
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
    df_sugestoes = df_temas[df_temas["titulo"].nao_comeca_com("(")]
    df_sugestoes = df_sugestoes.sort_values(["ultimo_uso_chave", "nr"]).head(6)
    linhas_sugestoes = [
        _linha_sugestao_tema(dict(linha)) for linha in df_sugestoes
    ]
    card_sugestoes = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=fonte(16), color=COR_AVISO),
                        ft.Text(
                            "Sugestões de temas — há mais tempo sem fazer",
                            size=fonte(14),
                            weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO,
                            expand=True,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.TextButton(
                            "Ver temas",
                            icon=ft.Icons.ARROW_FORWARD,
                            on_click=lambda _: ir_para(5),
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
                        ft.Icon(ft.Icons.LOOKS_ONE_OUTLINED, size=fonte(18), color=COR_DESTAQUE_SUAVE),
                        ft.Text(
                            "Importe os formulários S-99/S-99a (PDF) na aba Temas.",
                            size=fonte(13), color=TEXTO_PRIMARIO, expand=True,
                        ),
                        ft.TextButton("Abrir Temas", on_click=lambda _: ir_para(5)),
                    ],
                    spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        if total_oradores == 0:
            passos.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LOOKS_TWO_OUTLINED, size=fonte(18), color=COR_DESTAQUE_SUAVE),
                        ft.Text(
                            "Cadastre congregações, oradores e presidentes pela planilha-modelo "
                            "em Ajustes, ou restaure um backup.",
                            size=fonte(13), color=TEXTO_PRIMARIO, expand=True,
                        ),
                        ft.TextButton("Abrir Ajustes", on_click=lambda _: ir_para(INDICE_AJUSTES)),
                    ],
                    spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        card_primeiros_passos = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Primeiros passos", size=fonte(14), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
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
        criar_cabecalho_tela(f"{NOMES_MESES[mes]} de {ano}", subtitulo, subtitulo_no_celular=True),
        ft.Container(height=20),
    ]
    if card_primeiros_passos is not None:
        blocos += [card_primeiros_passos, ft.Container(height=12)]
    if eh_mobile():
        secao_colunas = ft.Column(
            [c for c in (card_destaque, card_agenda, card_pendencias, card_acoes) if c is not None],
            spacing=12,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    else:
        # As colunas ficam da mesma altura e o card da agenda estica para
        # preencher — sem faixa vazia entre a agenda e as sugestões quando a
        # coluna lateral (pendências + ações) é mais alta.
        card_agenda.expand = True
        coluna_principal.tight = False
        secao_colunas = ft.Row(
            [coluna_principal, coluna_lateral],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    blocos += [
        kpis,
        ft.Container(height=12),
        secao_colunas,
    ]
    if card_sugestoes is not None:
        blocos += [ft.Container(height=12), card_sugestoes]

    return ft.Column(
        blocos,
        spacing=0,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH if eh_mobile() else ft.CrossAxisAlignment.START,
    )


def _iniciais_nome(nome: str) -> str:
    partes = [p for p in (nome or "").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def abrir_dialog_temas_do_orador(page: ft.Page, orador_id: int, nome: str) -> None:
    """Mostra os temas que o orador tem preparados, com número e título."""
    temas = carregar_temas_com_titulo_de_orador(orador_id)

    if temas:
        corpo: list[ft.Control] = [
            ft.Text(
                f"{nr} — {titulo}" if titulo else f"{nr}",
                size=fonte(13),
                color=TEXTO_PRIMARIO,
            )
            for nr, titulo in temas
        ]
    else:
        corpo = [
            ft.Text(
                "Nenhum tema marcado no cadastro dele. Se ele faz qualquer "
                "tema, marque essa opção ao editar.",
                size=fonte(13),
                color=TEXTO_SECUNDARIO,
                italic=True,
            )
        ]

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Temas de {nome}", size=fonte(16)),
            content=ft.Container(
                width=_largura_dialog(page, 460),
                content=ft.Column(
                    [
                        ft.Text(
                            f"{len(temas)} tema(s) preparado(s)",
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Container(height=6),
                        *corpo,
                    ],
                    spacing=6,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[ft.TextButton("Fechar", on_click=lambda _: page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


def _rotulo_ultima_saida(ultima_saida: dict[int, str], orador_id: int) -> str:
    """Quando o orador discursou fora pela última vez — vazio se não há dados."""
    if not ultima_saida:
        return ""
    data = ultima_saida.get(orador_id)
    return f"último envio: {data}" if data else "nunca foi enviado"


def _menu_acoes_mobile(acoes: list[tuple[str, str, Callable]]) -> ft.Control:
    """Menu "⋮" com as ações da linha — só no celular.

    Cada IconButton come uns 48dp de largura no telefone, e três deles não
    deixavam sobrar nada para o nome: "Danilo Reis" saía quebrado em duas
    linhas, "Joci / ar B…". Editar e excluir saem da linha e viram menu — o
    nome fica com a largura, e excluir por engano num toque fica mais difícil.

    ``acoes`` é uma lista de ``(rótulo, ícone, ao_clicar)``.
    """
    return ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT,
        icon_size=fonte(18),
        icon_color=TEXTO_SECUNDARIO,
        tooltip="Mais ações",
        items=[
            ft.PopupMenuItem(content=rotulo, icon=icone, on_click=ao_clicar)
            for rotulo, icone, ao_clicar in acoes
        ],
    )


def _criar_lista_oradores(
    df: Tabela,
    estado_selecao: dict,
    on_editar: Callable[[int], None],
    on_excluir: Callable[[int], None],
    on_conversar: Callable[[int], None] | None = None,
    ultima_saida: dict[int, str] | None = None,
    on_temas: Callable[[int, str], None] | None = None,
    expandir: bool = True,
) -> ft.Container:
    """Lista de oradores com iniciais, privilégio, telefone e chip de temas.

    ``ultima_saida`` ({orador_id: data}) mostra em cada linha quando a pessoa
    discursou fora pela última vez — é o que se olha ao marcar quem vai na
    próxima lista de envio.
    """
    ultima_saida = ultima_saida or {}
    if df.empty:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.PERSON_SEARCH, size=fonte(36), color=TEXTO_SECUNDARIO),
                    ft.Text("Nenhum orador encontrado.", size=fonte(13), color=TEXTO_SECUNDARIO),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=32,
            alignment=ft.Alignment.CENTER,
        )

    linhas: list[ft.Control] = []
    registros = list(df.itertuples(index=False, name=None))
    colunas = list(df.colunas)
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

        def selo(texto: str, cor: str, ao_clicar=None) -> ft.Control:
            return ft.Container(
                content=ft.Text(texto, size=fonte(11), weight=ft.FontWeight.W_600, color=cor),
                bgcolor=ft.Colors.with_opacity(0.13, cor),
                border_radius=9,
                padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                ink=ao_clicar is not None,
                tooltip="Ver os temas preparados" if ao_clicar else None,
                on_click=ao_clicar,
            )

        # O selo de temas abre a lista: o número sozinho não diz se a pessoa
        # pode fazer o discurso que se está tentando encaixar.
        selos = [
            selo(
                chip_texto,
                chip_cor,
                (lambda e, rid=orador_id, n=nome: on_temas(rid, n)) if on_temas else None,
            )
        ]
        # Quem faz só o discurso local não vai na lista mandada para outra
        # congregação: o selo explica, e o checkbox fica travado.
        so_local = not mapa.get("aprovado_fora", 1)
        if so_local:
            selos.append(selo("só local", COR_AVISO))
            # Se já estava marcado quando o cadastro mudou, desmarca: senão
            # ele entraria no PDF sem aparecer marcado na tela.
            estado_selecao["ids"].discard(orador_id)
        chip = selos[0] if len(selos) == 1 else ft.Row(selos, spacing=6, tight=True)
        avatar = ft.Container(
            content=ft.Text(
                _iniciais_nome(nome),
                size=fonte(12),
                weight=ft.FontWeight.W_600,
                color=COR_DESTAQUE_SUAVE,
            ),
            width=36,
            height=36,
            border_radius=18,
            bgcolor=ft.Colors.with_opacity(0.16, COR_DESTAQUE_CLARA),
            alignment=ft.Alignment.CENTER,
        )
        checkbox = ft.Checkbox(
            value=orador_id in estado_selecao["ids"],
            on_change=alternar_selecao,
            disabled=so_local,
            tooltip=(
                "Faz apenas o discurso local. Não entra no PDF de envio"
                if so_local
                else "Selecionar para o PDF de envio"
            ),
        )
        # Conversar só aparece com telefone: sem número não há para onde ir.
        tem_telefone = bool(formatar_valor(mapa.get("telefone")).strip())
        botao_conversar = (
            ft.IconButton(
                icon=ft.Icons.CHAT_OUTLINED,
                icon_size=fonte(17),
                tooltip="Conversar no WhatsApp",
                icon_color="#34D399",
                on_click=lambda e, rid=orador_id: on_conversar(rid),
            )
            if on_conversar and tem_telefone
            else None
        )
        botao_editar = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            icon_size=fonte(17),
            tooltip="Editar",
            icon_color=TEXTO_SECUNDARIO,
            on_click=lambda e, rid=orador_id: on_editar(rid),
        )
        botao_excluir = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_size=fonte(17),
            tooltip="Excluir",
            icon_color=COR_ERRO,
            on_click=lambda e, rid=orador_id: on_excluir(rid),
        )
        borda_linha = ft.Border(
            ft.BorderSide(0, BORDA_SUAVE),
            ft.BorderSide(0, BORDA_SUAVE),
            ft.BorderSide(1 if indice < len(registros) - 1 else 0, BORDA_SUAVE),
            ft.BorderSide(0, BORDA_SUAVE),
        )

        if eh_mobile():
            # Card empilhado: nome com linha inteira garantida (a categoria ao
            # lado roubava a largura e o nome sumia), detalhes abaixo.
            detalhes = " · ".join(p for p in (categoria, telefone) if p)
            conteudo = ft.Column(
                [
                    ft.Row(
                        [
                            checkbox,
                            avatar,
                            ft.Text(
                                nome,
                                size=fonte(14),
                                weight=ft.FontWeight.W_600,
                                color=TEXTO_PRIMARIO,
                                expand=True,
                                # Uma linha só: com o nome em duas, o cartão
                                # crescia e cabiam três oradores na tela.
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            *([botao_conversar] if botao_conversar else []),
                            _menu_acoes_mobile(
                                [
                                    (
                                        "Editar",
                                        ft.Icons.EDIT_OUTLINED,
                                        lambda e, rid=orador_id: on_editar(rid),
                                    ),
                                    (
                                        "Excluir",
                                        ft.Icons.DELETE_OUTLINE,
                                        lambda e, rid=orador_id: on_excluir(rid),
                                    ),
                                ]
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                _rotulo_ultima_saida(ultima_saida, orador_id) or detalhes,
                                size=fonte(12),
                                color=TEXTO_SECUNDARIO,
                                expand=True,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            chip,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=6,
                tight=True,
            )
            linhas.append(
                ft.Container(
                    content=conteudo,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border=borda_linha,
                )
            )
            continue

        info_orador = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            nome, size=fonte(14), weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO, no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS, expand=True,
                        ),
                        ft.Text(
                            f"· {categoria}" if categoria else "", size=fonte(12),
                            color=TEXTO_SECUNDARIO, no_wrap=True,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    [
                        ft.Text(
                            telefone, size=fonte(12), color=TEXTO_SECUNDARIO,
                            no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            _rotulo_ultima_saida(ultima_saida, orador_id),
                            size=fonte(11),
                            color=(
                                COR_AVISO if orador_id not in ultima_saida
                                else TEXTO_SECUNDARIO
                            ),
                            no_wrap=True,
                        ),
                    ],
                    spacing=8,
                ),
            ],
            spacing=2,
            expand=True,
        )
        linhas.append(
            ft.Container(
                content=ft.Row(
                    [
                        checkbox,
                        avatar,
                        info_orador,
                        chip,
                        *([botao_conversar] if botao_conversar else []),
                        botao_editar,
                        botao_excluir,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                border=borda_linha,
            )
        )

    return ft.Container(
        content=ft.Column(
            linhas,
            spacing=0,
            tight=True,
            scroll=ft.ScrollMode.AUTO if expandir else None,
        ),
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        bgcolor=FUNDO_CARD,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        # Dentro de um ExpansionTile não há altura para esticar: com `expand`
        # a lista renderiza vazia, como já aconteceu na aba Presidentes.
        expand=expandir,
    )


def _secao_oradores(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Oradores da MINHA congregação: é aqui que se monta a lista de envio.

    Deixou de ser uma aba própria: os de fora moram no cadastro de cada
    congregação (em Congregações), que é de onde eles vêm.
    """
    df_completo = carregar_dados(SQL_ORADORES)
    id_minha_congregacao = obter_id_minha_congregacao()
    estado_selecao = {"ids": set()}
    estado_filtro = {"ordem": "nome"}
    referencia_atualizar: dict[str, Callable[[str], None]] = {}

    def _ordenar_pela_fila(tabela: Tabela) -> Tabela:
        """Há mais tempo sem discursar primeiro — a ordem de quem escolher."""
        ultima = ultima_data_discurso_por_orador()
        ordem = oradores_mais_tempo_sem_discurso(
            [int(li["id"]) for li in tabela], ultima
        )
        posicao = {oid: indice for indice, oid in enumerate(ordem)}
        return Tabela(
            sorted(tabela.linhas, key=lambda li: posicao.get(int(li["id"]), 0)),
            tabela.colunas,
        )

    def df_filtrado_congregacao() -> Tabela:
        meus = df_completo
        if id_minha_congregacao:
            meus = df_completo[
                df_completo["congregacao_id"] == int(id_minha_congregacao)
            ]
        return _ordenar_pela_fila(meus) if estado_filtro["ordem"] == "fila" else meus

    def abrir_novo(_=None):
        abrir_dialog_orador(page, recarregar)

    def abrir_editar(orador_id: int):
        abrir_dialog_orador(page, recarregar, orador_id=orador_id)

    def abrir_excluir(orador_id: int):
        confirmar_exclusao_orador(page, recarregar, orador_id)

    def conversar_com_orador(orador_id: int):
        """Abre o WhatsApp do orador direto da lista."""
        orador = carregar_orador(orador_id) or {}
        telefone = (orador.get("telefone") or "").strip()
        if not telefone:
            mostrar_aviso(
                page,
                "Sem telefone",
                f"{orador.get('nome') or 'Este orador'} não tem telefone cadastrado.",
            )
            return
        abrir_url(page, gerar_link_whatsapp(telefone, ""))

    def ver_temas(orador_id: int, nome: str):
        abrir_dialog_temas_do_orador(page, orador_id, nome)

    def gerar_pdf_envio(_=None):
        acionar_geracao_pdf_envio(page, estado_selecao["ids"])

    def registrar_atualizar(fn: Callable[[str], None]) -> None:
        referencia_atualizar["fn"] = fn

    def ao_mudar_ordem(e=None):
        estado_filtro["ordem"] = seletor_ordem.value or "nome"
        if "fn" in referencia_atualizar:
            referencia_atualizar["fn"]("")

    seletor_ordem = ft.Dropdown(
        label="Ordenar por",
        value="nome",
        options=[
            ft.dropdown.Option(key="nome", text="Nome"),
            ft.dropdown.Option(key="fila", text="Há mais tempo sem discursar"),
        ],
        width=None if eh_mobile() else 250,
    )
    seletor_ordem.on_select = ao_mudar_ordem

    def renderizar_oradores(df_filtrado: Tabela, termo: str = "") -> ft.Control:
        return _criar_lista_oradores(
            df_filtrado, estado_selecao, abrir_editar, abrir_excluir,
            conversar_com_orador,
            ultima_saida={
                int(k): v for k, v in ultima_data_discurso_por_orador().items()
            },
            on_temas=ver_temas,
        )

    def exportar_relatorio(_=None):
        from relatorios import secoes_oradores

        registros = df_filtrado_congregacao().to_dict("records")
        exportar_relatorio_pdf(
            page,
            lambda: secoes_oradores(registros),
            "Oradores da minha congregação",
            "Oradores",
        )

    return criar_tela_padrao(
        page=page,
        titulo="Oradores",
        descricao="Oradores da minha congregação e temas que podem apresentar",
        mostrar_cabecalho=False,
        df=df_filtrado_congregacao,
        colunas_filtro=COLUNAS_BUSCA_ORADORES,
        controles_filtro=[seletor_ordem],
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
            botao_relatorio_tela(exportar_relatorio),
        ],
        on_editar=abrir_editar,
        on_excluir=abrir_excluir,
    )


def _colunas_filtro_temas() -> list[str]:
    anos = [str(item["ano"]) for item in listar_anos_colunas(apenas_visiveis=True)]
    return ["nr", "titulo", "assunto", *anos, "ultimo_uso", "restricoes"]


def _validar_mes_ano(valor: str, ano_esperado: int | None = None) -> bool:
    """Aceita vazio ou data MM/AAAA; com ``ano_esperado``, o ano precisa bater.

    Cada coluna é um ano, então gravar 04/2025 embaixo de 2023 esconde o uso
    quando essa coluna é ocultada — foi o que aconteceu com a carga da
    planilha. A validação impede que volte a acontecer na mão.
    """
    texto = (valor or "").strip()
    if not texto or texto == "—":
        return True
    partes = texto.split("/")
    if len(partes) != 2:
        return False
    try:
        mes = int(partes[0])
        ano = int(partes[1])
    except ValueError:
        return False
    if not (1 <= mes <= 12 and 2000 <= ano <= 2100):
        return False
    return ano_esperado is None or ano == ano_esperado


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
    campo_prioritario = ft.Checkbox(
        label="Tema prioritário para a minha congregação",
        value=bool(dados.get("prioritario")),
        tooltip="Sobe para o topo na escolha assistida de oradores recebidos",
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

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
            hint_text=f"MM/{ano}",
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
            if not _validar_mes_ano(campo.value or "", ano):
                texto_erro.value = (
                    f"Data inválida em {ano}. Use MM/{ano}: a coluna guarda "
                    f"o uso daquele ano."
                )
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
            definir_tema_prioritario(tema_nr, bool(campo_prioritario.value))
        except Exception:
            logger.exception("Falha ao salvar tema")
            texto_erro.value = "Não foi possível salvar o tema."
            texto_erro.visible = True
            page.update()
            return

        fechar()
        recarregar()

    conteudo_anos = []
    if linhas_anos:
        conteudo_anos = [
            ft.Text("Datas de uso por ano", weight=ft.FontWeight.W_600, size=fonte(13)),
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
                        campo_prioritario,
                        *conteudo_anos,
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=_largura_dialog(page, 520),
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
            logger.exception("Falha ao excluir tema")
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
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

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
                                size=fonte(12),
                                color=TEXTO_SECUNDARIO if visivel else COR_AVISO,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.VISIBILITY if visivel else ft.Icons.VISIBILITY_OFF,
                                tooltip="Ocultar coluna" if visivel else "Exibir coluna",
                                icon_size=fonte(20),
                                on_click=alternar_visibilidade,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip="Excluir ano e seus dados",
                                icon_size=fonte(20),
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
                            size=fonte(13),
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
                    width=_largura_dialog(page, 420),
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
    texto_contagem = ft.Text(size=fonte(13), color=TEXTO_SECUNDARIO)

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

    # Cache do dataframe: consultas ao banco só quando os dados mudam de fato
    estado_temas: dict = {"df": None, "montado": False}

    # Sem paginação: todos os temas numa lista só, é só rolar.
    if eh_mobile():
        texto_contagem.size = fonte(12)
        texto_contagem.max_lines = 1
        texto_contagem.overflow = ft.TextOverflow.ELLIPSIS
    linha_paginacao = ft.Row(
        [texto_contagem],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
    )

    def _df_temas() -> Tabela:
        if estado_temas["df"] is None:
            estado_temas["df"] = carregar_dataframe_temas(apenas_anos_visiveis=True)
        return estado_temas["df"]

    def alternar_prioritario(tema_nr: int, novo: bool):
        """Marca/desmarca o tema como prioritário direto na lista."""
        definir_tema_prioritario(tema_nr, novo)
        df_cache = estado_temas.get("df")
        if df_cache is not None:
            # Atualiza o cache em memória em vez de recarregar todos os temas.
            df_cache.definir(df_cache["nr"] == tema_nr, "prioritario", 1 if novo else 0)
        atualizar_view()

    def atualizar_view(_=None):
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
        area_tabela.content = criar_area_tabela(
            df_filtrado,
            on_editar=abrir_editar,
            on_excluir=abrir_excluir,
            config={**CONFIG_TABELA_TEMAS, "on_prioritario": alternar_prioritario},
        )
        if total == len(df):
            texto_contagem.value = f"{total} tema(s)"
        else:
            texto_contagem.value = f"{total} de {len(df)} tema(s)"
        if estado_temas["montado"]:
            # Atualiza só os controles afetados — bem mais rápido que page.update()
            area_tabela.update()
            linha_paginacao.update()

    filtro_assunto.on_select = atualizar_view
    filtro_uso.on_select = atualizar_view
    filtro_ordem.on_select = atualizar_view

    def recarregar():
        estado_temas["df"] = None  # dados mudaram: invalida o cache
        atualizar_view()

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
                resultado = executar_com_progresso(
                    page, "Lendo PDF...", lambda: importar_temas_pdf(arquivo.path)
                )
            except Exception as exc:
                logger.exception("Falha ao importar temas do PDF")
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

    botao_importar = ft.FilledButton(
        "Importar S-99/S-99a",
        icon=ft.Icons.UPLOAD_FILE,
        on_click=abrir_importar,
        tooltip="Preenche os temas a partir dos formulários oficiais em PDF",
    )
    botao_gerenciar = ft.OutlinedButton(
        "Gerenciar",
        icon=ft.Icons.CALENDAR_MONTH,
        on_click=abrir_anos,
    )

    def exportar_relatorio(_=None):
        from relatorios import secoes_temas

        exportar_relatorio_pdf(page, secoes_temas, "Temas", "Temas")

    botao_relatorio = botao_relatorio_tela(exportar_relatorio)

    if eh_mobile():
        # Celular: busca em cima; botões e filtros dentro de um painel
        # recolhido — sobra altura para a tabela, que ficava minúscula.
        for filtro in (filtro_assunto, filtro_uso, filtro_ordem):
            filtro.width = None
        controles_topo = [
            ft.Row([campo_busca]),
            ft.Container(height=8),
            ft.ExpansionTile(
                title=ft.Text("Ações e filtros", size=fonte(13), weight=ft.FontWeight.W_600),
                leading=ft.Icon(ft.Icons.TUNE, size=fonte(18), color=COR_DESTAQUE_SUAVE),
                tile_padding=ft.Padding.symmetric(horizontal=8),
                controls_padding=ft.Padding.only(left=8, right=8, bottom=12),
                controls=[
                    ft.Row([botao_importar, botao_gerenciar, botao_relatorio], spacing=8, wrap=True),
                    ft.Container(height=12),
                    ft.Column(
                        [filtro_assunto, filtro_uso, filtro_ordem],
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                ],
            ),
        ]
    else:
        controles_topo = [
            ft.Row(
                [campo_busca, botao_importar, botao_gerenciar, botao_relatorio],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=12),
            ft.Row(
                [filtro_assunto, filtro_uso, filtro_ordem],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]

    if eh_mobile():
        return ft.Column(
            [
                criar_cabecalho_tela("Temas"),
                ft.Container(height=8),
                *controles_topo,
                ft.Container(height=4),
                linha_paginacao,
                ft.Container(height=4),
                area_tabela,
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Temas",
                "Colunas por ano conforme a planilha. Temas com observações aparecem em azul",
            ),
            ft.Container(height=28),
            criar_secao_titulo("Catálogo"),
            ft.Container(height=12),
            *controles_topo,
            ft.Container(height=8),
            linha_paginacao,
            ft.Container(height=8),
            area_tabela,
        ],
        spacing=0,
        expand=True,
    )


def _criar_lista_congregacoes(
    df: Tabela,
    on_editar: Callable[[int], None],
    on_excluir: Callable[[int], None],
    on_conversar: Callable[[int], None] | None = None,
    oradores_de: Callable[[int], ft.Control] | None = None,
    abertas: set[int] | None = None,
) -> ft.Control:
    """Congregações em cards, cada uma abrindo os oradores dela.

    Era uma tabela no computador e cards no celular. Virou card nos dois:
    os oradores de fora saíram da aba própria e passaram a morar aqui, no
    cadastro da congregação de onde eles vêm — e tabela não expande.

    ``abertas`` são as congregações que já nascem expandidas: quando a busca
    casou com o nome de um orador, o cartão precisa abrir sozinho — senão a
    pessoa procurada fica escondida atrás do clique.
    """
    abertas = abertas or set()
    if df.empty:
        return ft.Container(
            content=ft.Text("Nenhuma congregação encontrada.", size=fonte(13), color=TEXTO_SECUNDARIO),
            padding=32,
            alignment=ft.Alignment.CENTER,
        )

    linhas: list[ft.Control] = []
    registros = list(df.itertuples(index=False, name=None))
    colunas = list(df.colunas)
    for indice, linha in enumerate(registros):
        mapa = dict(zip(colunas, linha))
        cong_id = int(mapa["id"])
        nome = formatar_valor(mapa.get("nome"))
        responsavel = formatar_valor(mapa.get("responsavel"))
        telefone = formatar_valor(mapa.get("telefone"))
        endereco = formatar_valor(mapa.get("endereco"))
        reuniao = " ".join(
            p for p in (formatar_valor(mapa.get("dia_semana")), formatar_valor(mapa.get("horario"))) if p
        )

        detalhes: list[ft.Control] = []
        telefone = mascara_telefone(telefone)
        contato = " · ".join(p for p in (responsavel, telefone) if p)
        if contato:
            # Falar com o responsável é a ação mais comum aqui: fica ao lado
            # do nome dele, não escondida atrás de editar.
            detalhes.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PERSON_OUTLINE, size=fonte(13),
                                color=TEXTO_SECUNDARIO),
                        ft.Text(contato, size=fonte(12), color=TEXTO_SECUNDARIO,
                                expand=True, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        *(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.CHAT_OUTLINED,
                                    icon_size=fonte(17),
                                    icon_color="#34D399",
                                    tooltip=f"Falar com {responsavel or 'o responsável'}",
                                    style=ft.ButtonStyle(padding=2),
                                    on_click=lambda e, rid=cong_id: on_conversar(rid),
                                )
                            ]
                            if on_conversar and telefone
                            else []
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        else:
            detalhes.append(
                ft.Text("Sem responsável cadastrado", size=fonte(12),
                        color=TEXTO_SECUNDARIO, italic=True)
            )
        if reuniao:
            detalhes.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SCHEDULE, size=fonte(13), color=TEXTO_SECUNDARIO),
                        ft.Text(reuniao, size=fonte(12), color=TEXTO_SECUNDARIO,
                                expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=6,
                )
            )
        if endereco:
            detalhes.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PLACE_OUTLINED, size=fonte(13), color=TEXTO_SECUNDARIO),
                        ft.Text(endereco, size=fonte(12), color=TEXTO_SECUNDARIO,
                                expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )

        cabecalho_card = ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    nome, size=fonte(14), weight=ft.FontWeight.W_600,
                                    color=TEXTO_PRIMARIO, expand=True,
                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.EDIT_OUTLINED,
                                    icon_size=fonte(17),
                                    tooltip="Editar",
                                    icon_color=TEXTO_SECUNDARIO,
                                    on_click=lambda e, rid=cong_id: on_editar(rid),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_size=fonte(17),
                                    tooltip="Excluir",
                                    icon_color=COR_ERRO,
                                    on_click=lambda e, rid=cong_id: on_excluir(rid),
                                ),
                            ],
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        *detalhes,
                    ],
                    spacing=4,
                    tight=True,
        )
        borda = ft.Border(
            ft.BorderSide(0, BORDA_SUAVE),
            ft.BorderSide(0, BORDA_SUAVE),
            ft.BorderSide(1 if indice < len(registros) - 1 else 0, BORDA_SUAVE),
            ft.BorderSide(0, BORDA_SUAVE),
        )
        if oradores_de is None:
            linhas.append(
                ft.Container(
                    content=cabecalho_card,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border=borda,
                )
            )
            continue
        linhas.append(
            ft.Container(
                content=ft.ExpansionTile(
                    title=cabecalho_card,
                    tile_padding=ft.Padding.symmetric(horizontal=12, vertical=2),
                    controls_padding=ft.Padding.only(left=8, right=8, bottom=10),
                    controls=[oradores_de(cong_id)],
                    expanded=cong_id in abertas,
                ),
                border=borda,
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


def _oradores_por_congregacao(oradores: Tabela) -> dict[int, list[dict]]:
    """Agrupa os oradores pelo id da congregação (sem congregação fica de fora)."""
    grupos: dict[int, list[dict]] = {}
    for linha in oradores.linhas:
        cong_id = linha.get("congregacao_id")
        if cong_id is not None:
            grupos.setdefault(int(cong_id), []).append(linha)
    return grupos


def _congregacoes_com_oradores(congregacoes: Tabela, oradores: Tabela) -> Tabela:
    """Anexa a cada congregação os oradores dela, em texto, só para a busca.

    Quem procura "Henrique Dias" na tela de Congregações quer a congregação
    dele, não decorar em qual das 70 ele está. A coluna não é exibida: os
    cartões continuam mostrando nome, responsável e reunião.
    """
    por_congregacao = _oradores_por_congregacao(oradores)
    linhas = []
    for linha in congregacoes.linhas:
        nova = dict(linha)
        nova["oradores"] = " · ".join(
            str(o.get("nome") or "") for o in por_congregacao.get(int(linha["id"]), [])
        )
        linhas.append(nova)
    return Tabela(linhas, [*congregacoes.colunas, "oradores"])


def _congregacoes_com_orador_buscado(oradores: Tabela, termo: str) -> set[int]:
    """Congregações em que a busca casou com algum orador (o cartão abre nelas)."""
    if not termo.strip():
        return set()
    casaram = filtrar_dataframe(oradores, termo, COLUNAS_BUSCA_ORADORES)
    return {
        int(linha["congregacao_id"])
        for linha in casaram.linhas
        if linha.get("congregacao_id") is not None
    }


def tela_congregacoes(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Lista congregações com busca, cadastro, edição e exclusão."""

    def abrir_nova(_=None):
        abrir_dialog_congregacao(page, recarregar)

    def abrir_editar(congregacao_id: int):
        abrir_dialog_congregacao(page, recarregar, congregacao_id=congregacao_id)

    def abrir_excluir(congregacao_id: int):
        confirmar_exclusao_congregacao(page, recarregar, congregacao_id)

    def conversar_com_responsavel(congregacao_id: int):
        """Abre o WhatsApp do irmão responsável pela congregação."""
        cong = carregar_congregacao(congregacao_id) or {}
        telefone = (cong.get("telefone") or "").strip()
        if not telefone:
            mostrar_aviso(
                page,
                "Sem telefone",
                f"A congregação {cong.get('nome') or ''} não tem telefone "
                "cadastrado.".replace("  ", " "),
            )
            return
        config = carregar_configuracao()
        responsavel = (cong.get("responsavel") or "").strip()
        mensagem = (
            f"Olá{', ' + responsavel.split()[0] if responsavel else ''}! Aqui é "
            f"{config.get('coordenador_discursos') or 'o coordenador'} de discursos "
            f"da {config.get('nome_congregacao') or 'nossa congregação'}."
        )
        abrir_url(page, gerar_link_whatsapp(telefone, mensagem))

    oradores_por_congregacao = carregar_dados(SQL_ORADORES)
    estado_selecao_cong = {"ids": set()}

    def abrir_editar_orador(orador_id: int):
        abrir_dialog_orador(page, recarregar, orador_id=orador_id)

    def abrir_excluir_orador(orador_id: int):
        confirmar_exclusao_orador(page, recarregar, orador_id)

    def conversar_com_orador(orador_id: int):
        orador = carregar_orador(orador_id) or {}
        telefone = (orador.get("telefone") or "").strip()
        if not telefone:
            mostrar_aviso(
                page,
                "Sem telefone",
                f"{orador.get('nome') or 'Este orador'} não tem telefone cadastrado.",
            )
            return
        abrir_url(page, gerar_link_whatsapp(telefone, ""))

    def ver_temas_orador(orador_id: int, nome: str):
        abrir_dialog_temas_do_orador(page, orador_id, nome)

    def oradores_da_congregacao(cong_id: int, termo: str = "") -> ft.Control:
        """Os oradores daquela congregação, dentro do cartão dela.

        Buscar pelo nome de um orador reduz o cartão aos oradores que casaram
        — abrir a congregação certa e ainda ter de achar a pessoa no meio da
        lista seria metade do trabalho.
        """
        do_grupo = oradores_por_congregacao[
            oradores_por_congregacao["congregacao_id"] == cong_id
        ]
        casaram = filtrar_dataframe(do_grupo, termo, COLUNAS_BUSCA_ORADORES)
        if termo.strip() and not casaram.empty:
            do_grupo = casaram

        def adicionar_aqui(_=None, cid=cong_id):
            abrir_dialog_orador(page, recarregar, congregacao_padrao=cid)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            f"{len(do_grupo)} orador(es)",
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                            expand=True,
                        ),
                        ft.OutlinedButton(
                            content="Adicionar orador",
                            icon=ft.Icons.PERSON_ADD_ALT,
                            on_click=adicionar_aqui,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=6),
                _criar_lista_oradores(
                    do_grupo,
                    estado_selecao_cong,
                    abrir_editar_orador,
                    abrir_excluir_orador,
                    conversar_com_orador,
                    on_temas=ver_temas_orador,
                    expandir=False,
                ),
            ],
            spacing=0,
            tight=True,
        )

    def renderizador(df_filtrado: Tabela, termo: str = "") -> ft.Control:
        return _criar_lista_congregacoes(
            df_filtrado,
            abrir_editar,
            abrir_excluir,
            conversar_com_responsavel,
            oradores_de=lambda cid: oradores_da_congregacao(cid, termo),
            abertas=_congregacoes_com_orador_buscado(oradores_por_congregacao, termo),
        )

    def exportar_relatorio(_=None):
        from relatorios import secoes_congregacoes

        exportar_relatorio_pdf(
            page,
            lambda: secoes_congregacoes(
                carregar_dados(SQL_CONGREGACOES).to_dict("records")
            ),
            "Congregações",
            "Congregacoes",
        )

    return criar_tela_padrao(
        page=page,
        titulo="Congregações",
        descricao="As congregações cadastradas, com os oradores de cada uma",
        df=_congregacoes_com_oradores(
            carregar_dados(SQL_CONGREGACOES), oradores_por_congregacao
        ),
        colunas_filtro=[
            "nome", "responsavel", "endereco", "dia_semana", "telefone", "oradores",
        ],
        barra_acoes=[
            ft.FilledButton(
                "Nova congregação",
                icon=ft.Icons.ADD,
                on_click=abrir_nova,
            ),
            botao_relatorio_tela(exportar_relatorio),
        ],
        on_editar=abrir_editar,
        on_excluir=abrir_excluir,
        config_tabela=CONFIG_TABELA_CONGREGACOES,
        renderizador_tabela=renderizador,
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
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

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
                    ft.Icon(icone, size=fonte(16), color=COR_DESTAQUE),
                    ft.Text(rotulo, size=fonte(12), weight=ft.FontWeight.W_600, color=TEXTO_SECUNDARIO),
                ],
                spacing=6,
            ),
            ft.Text(texto, size=fonte(14), color=TEXTO_PRIMARIO),
        ],
        spacing=4,
    )


def _resumir_texto_tabela(texto: str, limite: int = 42) -> str:
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto or "—"
    return texto[: limite - 3] + "..."


STATUS_DESIGNACAO_INFO = {
    "pendente": (ft.Icons.SCHEDULE, COR_AVISO, "Pendente"),
    "confirmado": (ft.Icons.CHECK_CIRCLE, COR_SUCESSO, "Confirmado"),
    "recusado": (ft.Icons.CANCEL, COR_ERRO, "Recusado"),
}
PROXIMO_STATUS_DESIGNACAO = {
    "pendente": "confirmado",
    "confirmado": "recusado",
    "recusado": "pendente",
}


def _selo_status_designacao(registro: dict, on_status: Callable[[int, str], None]):
    """Selo clicável de status; um toque cicla pendente → confirmado → recusado."""
    status = registro.get("status") or "pendente"
    icone, cor, rotulo = STATUS_DESIGNACAO_INFO.get(
        status, STATUS_DESIGNACAO_INFO["pendente"]
    )
    # Convite mandado e sem resposta: o selo passa a cobrar sozinho.
    espera, nivel = ("", "")
    if status == "pendente":
        espera, nivel = espera_de_resposta(registro.get("convidado_em"))
    if nivel == "atencao":
        cor = COR_AVISO
    dica = f"{rotulo} — toque para alterar"
    if espera:
        dica = f"{rotulo} ({espera}) — toque para alterar"
    return ft.IconButton(
        icon=icone,
        icon_size=fonte(17),
        icon_color=cor,
        tooltip=dica,
        style=ft.ButtonStyle(padding=4),
        on_click=lambda e, rid=int(registro["id"]), atual=status: on_status(
            rid, PROXIMO_STATUS_DESIGNACAO.get(atual, "confirmado")
        ),
    )


def _criar_cabecalho_tabela_oradores() -> ft.Container:
    """Cabeçalho da tabela: Data | Orador | Tema | Ações."""
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.06, COR_DESTAQUE),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            [
                ft.Text(
                    "Data",
                    width=_tema.LARGURA_COL_DATA_MES,
                    size=fonte(12),
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    "Orador",
                    width=_tema.LARGURA_COL_ORADOR_MES,
                    size=fonte(12),
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    "Tema",
                    width=_tema.LARGURA_COL_TEMA_MES if eh_mobile() else None,
                    expand=None if eh_mobile() else True,
                    size=fonte(12),
                    weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Text(
                    "Ações",
                    width=_tema.LARGURA_COL_ACOES_MES,
                    size=fonte(12),
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
    on_status: Callable[[int, str], None] | None = None,
    on_mover: Callable[[dict], None] | None = None,
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
                    width=_tema.LARGURA_COL_DATA_MES,
                    size=fonte(13),
                    weight=ft.FontWeight.W_600,
                    color=TEXTO_PRIMARIO,
                ),
                ft.Text(
                    nome_oradores(registro),
                    size=fonte(13),
                    color=TEXTO_PRIMARIO,
                    width=_tema.LARGURA_COL_ORADOR_MES,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    tema,
                    size=fonte(13),
                    color=TEXTO_SECUNDARIO,
                    width=_tema.LARGURA_COL_TEMA_MES if eh_mobile() else None,
                    expand=None if eh_mobile() else True,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Row(
                    [
                        *(
                            [_selo_status_designacao(registro, on_status)]
                            if on_status
                            else []
                        ),
                        *(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.CHAT_OUTLINED,
                                    icon_size=fonte(17),
                                    tooltip="Enviar ao orador (WhatsApp)",
                                    icon_color="#34D399",
                                    style=ft.ButtonStyle(padding=4),
                                    on_click=lambda e, item=dict(registro): on_whatsapp(item),
                                )
                            ]
                            if on_whatsapp
                            else []
                        ),
                        *(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.EVENT_REPEAT_OUTLINED,
                                    icon_size=fonte(17),
                                    tooltip="Trocar/mover a data",
                                    icon_color=COR_DESTAQUE_SUAVE,
                                    style=ft.ButtonStyle(padding=4),
                                    on_click=lambda e, item=dict(registro): on_mover(item),
                                )
                            ]
                            if on_mover
                            else []
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_size=fonte(17),
                            tooltip="Editar",
                            icon_color=COR_DESTAQUE,
                            style=ft.ButtonStyle(padding=4),
                            on_click=lambda e, item=dict(registro): on_editar(item),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=fonte(17),
                            tooltip="Remover",
                            icon_color=COR_ERRO,
                            style=ft.ButtonStyle(padding=4),
                            on_click=lambda e, rid=int(registro["id"]): on_remover(rid),
                        ),
                    ],
                    spacing=0,
                    width=_tema.LARGURA_COL_ACOES_MES
                    + (34 if on_whatsapp else 0)
                    + (34 if on_status else 0)
                    + (34 if on_mover else 0),
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
    return _tema.ALTURA_CONTEUDO_DIALOG_MES


def _criar_rodape_dialog_mes(
    on_fechar: Callable,
    on_editar: Callable,
    on_excluir: Callable,
    on_falar_responsavel: Callable | None = None,
    on_agenda: Callable | None = None,
) -> ft.Container:
    """Barra fixa de ações na parte inferior do dialog."""
    mobile = eh_mobile()
    botoes = [
        ft.TextButton("Fechar", on_click=on_fechar),
        *(
            [
                ft.OutlinedButton(
                    content="Responsável" if mobile else "Falar com o responsável",
                    icon=ft.Icons.CHAT_OUTLINED,
                    style=ft.ButtonStyle(color="#34D399"),
                    on_click=on_falar_responsavel,
                )
            ]
            if on_falar_responsavel
            else []
        ),
        *(
            [
                ft.OutlinedButton(
                    content="Agenda" if mobile else "Exportar para a agenda",
                    icon=ft.Icons.EVENT_OUTLINED,
                    tooltip="Gera um arquivo .ics com os compromissos do mês "
                            "para importar na agenda do celular",
                    on_click=on_agenda,
                )
            ]
            if on_agenda
            else []
        ),
        ft.OutlinedButton(
            # Rótulos curtos no celular para os três botões caberem
            content="Editar" if mobile else "Editar arranjo",
            icon=ft.Icons.EDIT_OUTLINED,
            on_click=on_editar,
        ),
        ft.OutlinedButton(
            content="Excluir" if mobile else "Excluir arranjo",
            icon=ft.Icons.DELETE_OUTLINE,
            on_click=on_excluir,
        ),
    ]
    return ft.Container(
        content=ft.Row(
            botoes,
            alignment=ft.MainAxisAlignment.START if mobile else ft.MainAxisAlignment.END,
            spacing=8 if mobile else 12,
            wrap=mobile,
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
    on_status: Callable[[int, str], None] | None = None,
    on_mover: Callable[[dict], None] | None = None,
) -> list[ft.Control]:
    """Monta tabela simples com cabeçalho e linhas."""
    if not registros:
        return [
            ft.Text(
                mensagem_vazia,
                size=fonte(13),
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
            on_status=on_status,
            on_mover=on_mover,
        )
        for indice, item in enumerate(registros)
    ]
    tabela = ft.Container(
        content=ft.Column(
            [_criar_cabecalho_tabela_oradores(), *linhas],
            spacing=0,
            tight=True,
        ),
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=8,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
    if eh_mobile():
        # No celular as colunas têm largura fixa; a tabela rola na horizontal
        # para o texto não ser espremido.
        return [ft.Row([tabela], scroll=ft.ScrollMode.AUTO, tight=True)]
    return [tabela]


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
        hint_text="Digite o número ou parte do título",
        options=carregar_temas_opcoes(incluir_sem_tema=True),
        value=tema_atual,
        expand=True,
        editable=True,
        enable_filter=True,
        enable_search=True,
        menu_height=320,
    )
    campo_congregacao = ft.Dropdown(
        label=f"Congregação ({rotulo_cong.lower()})",
        options=carregar_congregacoes_opcoes(),
        value=str(registro["congregacao_id"]) if registro.get("congregacao_id") else None,
        expand=True,
        editable=True,
        enable_filter=True,
        enable_search=True,
    )
    # Simpósio: dá para transformar um discurso comum em simpósio (e voltar)
    # sem apagar e recadastrar — o segundo orador vem da minha congregação.
    eh_recebido = tipo == "recebido"
    id_minha = obter_id_minha_congregacao()
    campo_orador_2 = ft.Dropdown(
        label="Segundo orador (simpósio)",
        options=carregar_oradores_com_congregacao_opcoes(
            int(id_minha) if id_minha else None
        ),
        value=str(registro["orador_2_id"]) if registro.get("orador_2_id") else None,
        expand=True,
        visible=eh_recebido and bool(registro.get("orador_2_id")),
    )
    campo_simposio = ft.Checkbox(
        label="Simpósio (dois oradores no mesmo discurso)",
        value=bool(registro.get("orador_2_id")),
        visible=eh_recebido,
    )

    def alternar_simposio(_=None):
        campo_orador_2.visible = bool(campo_simposio.value)
        if not campo_simposio.value:
            campo_orador_2.value = None
        page.update()

    campo_simposio.on_change = alternar_simposio
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

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
            orador_2_id = None
            if eh_recebido and campo_simposio.value:
                if not campo_orador_2.value:
                    texto_erro.value = "Selecione o segundo orador do simpósio."
                    texto_erro.visible = True
                    page.update()
                    return
                orador_2_id = int(campo_orador_2.value)
                if orador_2_id == registro.get("orador_id"):
                    texto_erro.value = "O simpósio precisa de dois oradores diferentes."
                    texto_erro.visible = True
                    page.update()
                    return
            atualizar_orador_arranjo(
                registro_id, tema_nr, congregacao_id, data_norm, orador_2_id
            )
        except Exception:
            logger.exception("Falha ao salvar alterações da designação")
            texto_erro.value = "Não foi possível salvar as alterações."
            texto_erro.visible = True
            page.update()
            return
        fechar()
        atualizar_listas()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Editar — {nome_oradores(registro)}"),
            content=ft.Container(
                content=ft.Column(
                    [
                        campo_data,
                        campo_tema,
                        campo_congregacao,
                        campo_simposio,
                        campo_orador_2,
                        texto_erro,
                    ],
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

    # Listas longas (todos os oradores, 194 temas): digitar filtra a lista.
    campo_orador = ft.Dropdown(
        label="Orador",
        hint_text="Digite para buscar pelo nome",
        # Ao ENVIAR: só quem é da minha congregação, na ordem de quem está há
        # mais tempo sem ser designado — que é a ordem em que a escolha é
        # feita na prática. Quem faz só o discurso local continua na lista:
        # ele também entra no arranjo do mês (é a lista de envio a outra
        # congregação que o exclui).
        options=carregar_oradores_com_congregacao_opcoes(
            congregacao_filtro,
            por_fila=not eh_oradores,
        ),
        expand=True,
        editable=True,
        enable_filter=True,
        enable_search=True,
        menu_height=320,
    )
    campo_data_manual = ft.TextField(
        label="Data manual (opcional)",
        hint_text="DD/MM/AAAA",
        expand=True,
    )
    campo_tema = ft.Dropdown(
        label="Tema",
        hint_text="Digite o número ou parte do título",
        options=carregar_temas_opcoes(incluir_sem_tema=eh_oradores),
        expand=True,
        editable=True,
        enable_filter=True,
        enable_search=True,
        menu_height=320,
    )
    area_sugestoes = ft.Column(spacing=6, tight=True)
    texto_sugestoes = ft.Text(
        "Selecione o orador para ver as datas sugeridas.",
        size=fonte(12),
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
    # Simpósio: o mesmo discurso dividido entre dois oradores DA MINHA
    # congregação. Só faz sentido em "Oradores recebidos" (quem discursa aqui).
    campo_orador_2 = ft.Dropdown(
        label="Segundo orador (simpósio)",
        options=carregar_oradores_com_congregacao_opcoes(
            int(id_minha_congregacao) if id_minha_congregacao else None
        ),
        expand=True,
        visible=False,
    )
    campo_simposio = ft.Checkbox(
        label="Simpósio (dois oradores no mesmo discurso)",
        value=False,
        visible=eh_oradores,
    )

    def alternar_simposio(_=None):
        campo_orador_2.visible = bool(campo_simposio.value)
        if not campo_simposio.value:
            campo_orador_2.value = None
        page.update()

    campo_simposio.on_change = alternar_simposio

    area_existente = ft.Column(
        [campo_orador, campo_simposio, campo_orador_2], spacing=12, tight=True
    )
    area_novo = ft.Column(
        [
            campo_nome_novo,
            linha_campos(campo_categoria_novo, campo_congregacao_novo),
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
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

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
                    size=fonte(12),
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

    # Sugestão de oradores da minha congregação há mais tempo sem discursar
    # (só ao designar um envio; recebidos vêm de outras congregações).
    area_sugestoes_orador = ft.Column(spacing=6, tight=True, visible=False)

    def montar_sugestoes_orador():
        if eh_oradores:
            return
        # As opções incluem cabeçalhos de congregação (chave __grupo__): fora.
        reais = [o for o in campo_orador.options if not str(o.key).startswith("__grupo__")]
        ids = [int(o.key) for o in reais]
        if not ids:
            return
        nomes = {int(o.key): (o.text or "").split(" — ")[0] for o in reais}
        ultima = ultima_data_discurso_por_orador()
        ordem = oradores_mais_tempo_sem_discurso(ids, ultima)

        def escolher(orador_id: int):
            campo_orador.value = str(orador_id)
            atualizar_sugestoes_datas()
            page.update()

        chips = []
        for oid in ordem[:5]:
            u = ultima.get(oid)
            sub = f"última: {u}" if u else "nunca discursou"
            chips.append(
                ft.OutlinedButton(
                    content=ft.Column(
                        [
                            ft.Text(nomes.get(oid, str(oid)), size=fonte(12),
                                    weight=ft.FontWeight.W_600),
                            ft.Text(sub, size=fonte(10), color=TEXTO_SECUNDARIO),
                        ],
                        spacing=0,
                        tight=True,
                    ),
                    on_click=lambda e, oid=oid: escolher(oid),
                )
            )
        area_sugestoes_orador.controls = [
            ft.Text(
                "Sugestões — há mais tempo sem discursar",
                size=fonte(12),
                color=TEXTO_SECUNDARIO,
                weight=ft.FontWeight.W_600,
            ),
            ft.Row(chips, wrap=True, spacing=8, run_spacing=8),
        ]
        area_sugestoes_orador.visible = True

    montar_sugestoes_orador()

    def abrir_escolha_assistida(_=None):
        """Ranqueia orador+tema por prioridade e tempo sem uso.

        Começa pela congregação anfitriã do arranjo, mas dá para trocar: às
        vezes o orador convidado é de outra congregação, e os temas que ELE tem
        preparados também precisam entrar na conta.
        """
        opcoes_cong = carregar_congregacoes_opcoes()
        if not opcoes_cong:
            mostrar_aviso(page, "Sem congregações",
                          "Cadastre as congregações para usar a escolha assistida.")
            return
        host_id = dados_arranjo.get("congregacao_host_id")
        inicial = str(host_id) if host_id else opcoes_cong[0].key

        df = carregar_dataframe_temas()
        prioritarios = {int(nr) for nr, p in zip(df["nr"], df["prioritario"]) if p}
        uso = {int(nr): (c or "") for nr, c in zip(df["nr"], df["ultimo_uso_chave"])}
        titulos = {int(nr): (t or "") for nr, t in zip(df["nr"], df["titulo"])}
        ultimos = {int(nr): (u or "") for nr, u in zip(df["nr"], df["ultimo_uso"])}
        # "restricoes" já traz a observação do tema ou o limite de uso; o "—"
        # é o texto que o catálogo usa para "sem nada anotado".
        observacoes_tema = {
            int(nr): (o or "").strip()
            for nr, o in zip(df["nr"], df["restricoes"])
            if (o or "").strip() not in ("", "—")
        }
        # Quem já está no mês não deve ser sugerido de novo.
        ja_no_mes = {
            int(r["orador_id"])
            for r in carregar_oradores_arranjo(arranjo_id)
            if r.get("orador_id") and r["tipo"] == tipo
        }

        lista = ft.Column(spacing=2, tight=True, scroll=ft.ScrollMode.AUTO,
                          expand=True)

        def escolher_sugestao(s: dict):
            campo_orador.value = str(s["orador_id"])
            campo_tema.value = str(s["tema_nr"])
            page.pop_dialog()
            atualizar_sugestoes_datas()
            page.update()

        def subtitulo_sugestao(s: dict) -> str:
            nr = s["tema_nr"]
            titulo = _resumir_texto_tabela(titulos.get(nr, ""), 52)
            if s["nunca_feito"]:
                uso_txt = "nunca feito na sua congregação"
            else:
                uso_txt = f"último uso: {ultimos.get(nr) or '—'}"
            linhas = [f"{nr} - {titulo}", uso_txt]
            # A observação do tema (uso restrito, limite de data, recado do
            # catálogo) precisa aparecer na hora de escolher, não só na aba
            # Temas — é ali que ela muda a decisão.
            observacao = observacoes_tema.get(nr)
            if observacao:
                linhas.append(f"⚠ {_resumir_texto_tabela(observacao, 64)}")
            return "\n".join(linhas)

        def montar(cong_id: str, orador_id: str | None = None):
            oradores = [
                o
                for o in oradores_com_temas_da_congregacao(int(cong_id))
                if int(o["id"]) not in ja_no_mes
            ]
            for orador in oradores:
                orador["qualquer_tema"] = obs_tem_qualquer_tema(
                    orador.get("observacoes", "")
                )
            # Com um orador escolhido, mostra TODOS os temas dele em ordem de
            # prioridade — é o que responde "o que ele pode fazer agora?".
            # Sem escolha, mistura os melhores pares da congregação inteira.
            se_um = [o for o in oradores if str(o["id"]) == str(orador_id)]
            if se_um:
                sugestoes = sugerir_recebidos(
                    se_um, prioritarios, uso, limite=300, max_por_orador=300
                )
            else:
                sugestoes = sugerir_recebidos(oradores, prioritarios, uso, limite=15)

            if not sugestoes:
                if se_um:
                    vazio = (
                        f"{se_um[0]['nome']} não tem temas cadastrados. Cadastre "
                        "os temas dele em Oradores."
                    )
                elif ja_no_mes:
                    vazio = (
                        "Todos os oradores desta congregação com temas cadastrados "
                        "já estão neste mês. Escolha outra congregação."
                    )
                else:
                    vazio = (
                        "Nenhum orador desta congregação tem temas cadastrados. "
                        "Cadastre os temas de cada orador em Oradores."
                    )
                lista.controls = [
                    ft.Container(
                        content=ft.Text(
                            vazio, size=fonte(12), color=TEXTO_SECUNDARIO, italic=True
                        ),
                        padding=12,
                    )
                ]
                return

            def titulo_linha(posicao: int, s: dict) -> str:
                if se_um:
                    # O nome já está no seletor: aqui vale a ordem.
                    return f"{posicao}º" + ("  ·  prioritário" if s["prioritario"] else "")
                return s["orador_nome"] + ("  ·  tema prioritário" if s["prioritario"] else "")

            lista.controls = [
                ft.ListTile(
                    dense=True,
                    leading=ft.Icon(
                        ft.Icons.STAR if s["prioritario"] else ft.Icons.MENU_BOOK_OUTLINED,
                        size=fonte(20),
                        color=COR_AVISO if s["prioritario"] else TEXTO_SECUNDARIO,
                    ),
                    title=ft.Text(
                        titulo_linha(posicao, s),
                        size=fonte(13), weight=ft.FontWeight.W_600,
                    ),
                    subtitle=ft.Text(subtitulo_sugestao(s), size=fonte(12)),
                    on_click=lambda e, s=dict(s): escolher_sugestao(s),
                )
                for posicao, s in enumerate(sugestoes, start=1)
            ]

        def opcoes_de_orador(cong_id: str) -> list[ft.dropdown.Option]:
            """Oradores da congregação, sem quem já está no mês."""
            return [ft.dropdown.Option(key="", text="Todos os oradores")] + [
                ft.dropdown.Option(key=str(o["id"]), text=o["nome"])
                for o in oradores_com_temas_da_congregacao(int(cong_id))
                if int(o["id"]) not in ja_no_mes
            ]

        seletor_cong = ft.Dropdown(
            label="Oradores da congregação",
            options=opcoes_cong,
            value=inicial,
            expand=True,
            editable=True,
            enable_filter=True,
        )

        seletor_orador = ft.Dropdown(
            label="Orador (opcional)",
            options=opcoes_de_orador(inicial),
            value="",
            expand=True,
            editable=True,
            enable_filter=True,
        )

        def trocar_congregacao(_=None):
            if seletor_cong.value:
                # Trocar de congregação zera o orador: ele era de outra lista.
                seletor_orador.options = opcoes_de_orador(seletor_cong.value)
                seletor_orador.value = ""
                montar(seletor_cong.value)
                page.update()

        def trocar_orador(_=None):
            if seletor_cong.value:
                montar(seletor_cong.value, seletor_orador.value or None)
                page.update()

        seletor_cong.on_select = trocar_congregacao
        seletor_orador.on_select = trocar_orador
        montar(inicial)

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(
                    "Escolha assistida",
                    size=fonte(15), weight=ft.FontWeight.W_600,
                ),
                content=ft.Container(
                    width=_largura_dialog(page, 520),
                    height=460,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Começa pelos temas que você marcou como "
                                "prioritários (★) e pelos há mais tempo sem fazer. "
                                "Escolha um orador para ver todos os temas dele em "
                                "ordem; sem escolher, mistura a congregação inteira. "
                                "Toque para preencher.",
                                size=fonte(12), color=TEXTO_SECUNDARIO,
                            ),
                            ft.Container(height=8),
                            seletor_cong,
                            ft.Container(height=8),
                            seletor_orador,
                            ft.Container(height=4),
                            lista,
                        ],
                        spacing=0,
                        tight=True,
                    ),
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: page.pop_dialog())
                ],
            )
        )


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
        # As sugestões já pulam assembleia e congresso; a data manual não passa
        # por elas, e é justamente por ali que a data errada entraria.
        bloqueadas = datas_sem_reuniao(int(dados_arranjo.get("ano", ANO_PADRAO_ARRANJOS)))
        conflito = next((d for d in datas_selecionadas if d in bloqueadas), None)
        if conflito:
            texto_erro.value = (
                f"{conflito} é {bloqueadas[conflito]}: a congregação não se reúne "
                "nesse dia, então não há orador nem designação."
            )
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

            orador_2_id = None
            if eh_oradores and campo_simposio.value:
                if not campo_orador_2.value:
                    texto_erro.value = "Selecione o segundo orador do simpósio."
                    texto_erro.visible = True
                    page.update()
                    return
                orador_2_id = int(campo_orador_2.value)
                if orador_2_id == orador_id:
                    texto_erro.value = "O simpósio precisa de dois oradores diferentes."
                    texto_erro.visible = True
                    page.update()
                    return

            tema_nr = int(campo_tema.value) if campo_tema.value else None
            for data_norm in datas_selecionadas:
                adicionar_orador_arranjo(
                    arranjo_id,
                    tipo,
                    orador_id,
                    tema_nr,
                    data=data_norm,
                    orador_2_id=orador_2_id,
                )
        except sqlite3.IntegrityError:
            texto_erro.value = "Já existe um registro deste orador nesta data."
            texto_erro.visible = True
            page.update()
            return
        except Exception:
            logger.exception("Falha ao adicionar designação ao arranjo")
            texto_erro.value = "Não foi possível adicionar a designação."
            texto_erro.visible = True
            page.update()
            return
        fechar()
        atualizar_listas()

    conteudo = (
        [
            alternador_modo,
            ft.OutlinedButton(
                content="Escolha assistida (prioridades e temas parados)",
                icon=ft.Icons.AUTO_AWESOME,
                on_click=abrir_escolha_assistida,
            ),
        ]
        if eh_oradores
        else []
    )
    conteudo.extend(
        [
            area_existente,
            area_sugestoes_orador,
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
                title=ft.Text(titulo_dialog, size=fonte(18), weight=ft.FontWeight.W_600),
                content=ft.Container(
                    content=ft.Column(
                        conteudo,
                        spacing=12,
                        tight=True,
                        width=_largura_dialog(page, 560),
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
        logger.exception("Falha ao abrir o seletor de oradores")
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
        nome = nome_oradores(registro) or "—"
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
                                size=fonte(14),
                                weight=ft.FontWeight.W_600,
                                color=TEXTO_PRIMARIO,
                            ),
                            ft.Text(
                                f"{data} · {tema}",
                                size=fonte(12),
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
    texto_erro = ft.Text("", color=COR_ERRO, size=fonte(13), visible=False)

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
            if eh_mobile():
                pasta = None  # gera em exports/ e depois oferece "salvar em..."
            else:
                pasta = await file_picker.get_directory_path(
                    dialog_title="Escolha a pasta para salvar a imagem",
                    initial_directory=str(EXPORTS_DIR.resolve()),
                )
                if not pasta:
                    return

            caminho, erro = executar_com_progresso(
                page,
                "Gerando imagem...",
                lambda: gerar_png_oradores(
                    arranjo,
                    reunioes,
                    selecionados,
                    pasta_destino=pasta,
                    titulo_secao=titulo_secao,
                    prefixo_arquivo=prefixo_arquivo,
                ),
            )
            if erro:
                texto_erro.value = erro
                texto_erro.visible = True
                page.update()
                return

            fechar()
            entregar_arquivo(page, caminho, abrir_pasta_do_arquivo)
            if not eh_mobile():
                mostrar_aviso(
                    page,
                    "Imagem exportada",
                    f"A imagem foi salva em:\n{caminho}",
                )
        except Exception as exc:
            logger.exception("Falha ao gerar a imagem da lista")
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
                            size=fonte(13),
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
                    width=_largura_dialog(page, 520),
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


# Chaves internas do seletor de presidente (não são IDs de cadastro).
CHAVE_PRESIDENTE_AVULSO = "__avulso__"
CHAVE_PRESIDENTE_AVULSO_ATUAL = "__avulso_atual__"


def abrir_dialog_presidente_avulso(
    page: ft.Page,
    data_str: str,
    ao_concluir: Callable[[], None],
    nome_atual: str = "",
) -> None:
    """Digita o nome de quem vai presidir sem estar no cadastro.

    É o caso do irmão que saiu da congregação: a semana dele precisa continuar
    aparecendo preenchida na programação e no quadro, mas ele não está mais na
    escala — então o nome fica FORA do revezamento.
    """
    campo_nome = ft.TextField(
        label="Nome de quem vai presidir",
        hint_text="Ex: Otávio Vilela",
        value=nome_atual,
        autofocus=True,
        expand=True,
    )
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        nome = (campo_nome.value or "").strip()
        if not nome:
            texto_erro.value = "Digite o nome de quem vai presidir."
            texto_erro.visible = True
            page.update()
            return
        salvar_presidente_avulso(data_str, nome)
        fechar()
        ao_concluir()
        mostrar_sucesso(page, f"{nome} ficou como presidente de {data_str[:5]}.")

    campo_nome.on_submit = salvar

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Presidente fora do rodízio"),
            content=ft.Container(
                width=_largura_dialog(page, 420),
                content=ft.Column(
                    [
                        ft.Text(
                            f"Sábado {data_str[:5]}, para quem não está no "
                            "cadastro de presidentes (por exemplo, o irmão que "
                            "saiu da congregação).",
                            size=fonte(13),
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Container(height=8),
                        campo_nome,
                        texto_erro,
                        ft.Container(height=4),
                        ft.Text(
                            "Este nome não entra no revezamento: não conta como "
                            "presidência para ninguém e não muda a ordem do rodízio.",
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                            italic=True,
                        ),
                    ],
                    spacing=0,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Salvar", icon=ft.Icons.CHECK, on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


def preencher_presidentes_rodizio(ano: int, mes: int) -> int:
    """Preenche as semanas sem presidente do mês por rodízio justo.

    Carrega o cadastro, as datas especiais e o histórico, delega a decisão para
    ``servicos.escolher_rodizio_presidentes`` (lógica pura, testada) e persiste
    as escolhas. Retorna quantas semanas foram preenchidas.
    """
    cadastro = listar_presidentes_cadastro(escala="normais")
    if not cadastro:
        return 0

    datas = _semanas_reuniao_mes(ano, mes)
    if not datas:
        return 0

    especiais = set(listar_datas_especiais_por_ano(ano))
    designacoes = carregar_todas_designacoes_presidente()
    datas_alvo = [_formatar_data_arranjo(data_ref) for data_ref in datas]

    escolhas = escolher_rodizio_presidentes(
        [item["id"] for item in cadastro],
        datas_alvo,
        especiais,
        designacoes,
        # Evita dois anciãos ou dois servos seguidos, quando dá.
        categorias={item["id"]: item["categoria"] for item in cadastro},
    )
    for data_str, presidente_id in escolhas:
        salvar_presidente(data_str, presidente_id)
    return len(escolhas)


def preencher_presidentes_especiais_rodizio(ano: int, mes: int) -> int:
    """Preenche por rodízio os presidentes das datas especiais do mês.

    Cada TIPO de evento tem a sua fila: uma para a Celebração, outra para a
    visita do superintendente, outra para o discurso especial. Elas não se
    misturam — presidir a Celebração deste ano não faz ninguém perder a vez na
    visita do superintendente, que é o que uma fila só faria.

    Entram só os marcados como presidentes de datas especiais — escala à parte
    da semanal, que o usuário define no cadastro —, e só as datas cujo tipo
    pede presidente local (a Assembleia não tem reunião no salão para
    presidir). Cada fila é medida contra as datas daquele tipo em TODOS os
    anos, não só as do mês: são uma ou duas por ano, e olhar um mês de cada
    vez daria sempre o primeiro do cadastro.

    Retorna quantas datas foram preenchidas.
    """
    elegiveis = [item["id"] for item in listar_presidentes_cadastro(escala="especiais")]
    if not elegiveis:
        return 0

    sem_presidente = tipos_evento_sem_presidente()
    especiais = listar_datas_especiais_por_ano(ano)
    historico_por_tipo = historico_presidentes_por_tipo_de_evento()

    # Agrupa por tipo: cada um roda o seu rodízio, com a sua memória.
    por_tipo: dict[str, list[str]] = {}
    for registro in especiais.values():
        data_str = registro["data"]
        if (
            len(data_str) == 10
            and int(data_str[3:5]) == mes
            and not registro.get("presidente_id")
            # Nome digitado à mão também é presidente definido: o rodízio não
            # pode passar por cima de quem já está registrado ali.
            and not registro.get("presidente_avulso")
            and registro["tipo"] not in sem_presidente
        ):
            por_tipo.setdefault(registro["tipo"], []).append(data_str)

    # Só desempata: entre quem nunca fez ESTE tipo, vai quem está há mais
    # tempo sem qualquer data especial.
    historico_geral = {
        data: pid
        for datas in historico_por_tipo.values()
        for data, pid in datas.items()
    }

    preenchidas = 0
    for tipo, datas in por_tipo.items():
        # Todas do mesmo mês e ano: DD/MM/AAAA já ordena por dia como texto
        # (é o mesmo critério que a lista da tela usa).
        escolhas = escolher_rodizio_datas_especiais(
            elegiveis, sorted(datas), historico_por_tipo.get(tipo, {}), historico_geral
        )
        for data_str, presidente_id in escolhas:
            definir_presidente_data_especial(especiais[data_str]["id"], presidente_id)
            # O tipo seguinte precisa enxergar o que este acabou de decidir:
            # com Celebração e discurso especial no mesmo mês, os dois cairiam
            # no mesmo irmão olhando a mesma foto antiga.
            historico_geral[data_str] = presidente_id
        preenchidas += len(escolhas)
    return preenchidas


def abrir_dialog_gerenciar_tipos_evento(
    page: ft.Page,
    ao_fechar: Callable[[], None],
) -> None:
    """Adicionar, remover e marcar quais tipos pedem presidente local."""
    lista = ft.Column(spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, height=260)
    campo_nome = ft.TextField(label="Novo tipo", hint_text="Ex: Escola de Pioneiros", expand=True)
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

    def preencher():
        tipos = listar_tipos_evento()
        if not tipos:
            lista.controls = [
                ft.Text("Nenhum tipo cadastrado.", size=fonte(13), color=TEXTO_SECUNDARIO, italic=True)
            ]
            return

        def linha_tipo(item: dict) -> ft.Control:
            def excluir(_=None, item=item):
                excluir_tipo_evento(item["id"])
                preencher()
                page.update()

            def alternar_presidente(e, item=item):
                definir_tipo_evento_tem_presidente(item["id"], bool(e.control.value))

            return ft.Row(
                [
                    ft.Text(item["nome"], size=fonte(14), expand=True),
                    # Numa Assembleia a congregação está fora do salão: não há
                    # o que presidir, e o rodízio não pode gastar a vez de um
                    # ancião ali. Quem sabe disso é quem monta o arranjo.
                    ft.Checkbox(
                        label="Presidente",
                        value=item.get("tem_presidente", True),
                        tooltip="Marque se esse evento tem reunião no salão, com "
                                "presidente. Só os marcados entram no rodízio "
                                "das datas especiais.",
                        on_change=alternar_presidente,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=fonte(18),
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
                    width=_largura_dialog(page, 420),
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
    fora_do_fim_de_semana = editando and registro["data"] not in datas_mes
    if fora_do_fim_de_semana:
        datas_mes.insert(0, registro["data"])

    campo_data = ft.Dropdown(
        label="Data",
        options=[ft.dropdown.Option(d) for d in datas_mes],
        value=registro["data"] if editando else None,
        expand=True,
    )
    # Nem toda data especial cai no fim de semana: a Celebração é sempre em
    # 14 de nisã e anda pelos dias da semana (em 2026 foi numa quinta). Sem
    # este campo ela não tinha como ser cadastrada, e é uma data que precisa
    # de orador e presidente como qualquer outra.
    campo_data_livre = ft.TextField(
        label="Outra data (dia de semana)",
        hint_text="DD/MM/AAAA — ex.: a Celebração",
        value=registro["data"] if fora_do_fim_de_semana else "",
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

    # Quem presidiu sem estar no cadastro (saiu da congregação, ou nunca
    # entrou na escala) precisa caber aqui: era o furo que fazia a Celebração
    # de anos passados aparecer sem presidente no relatório.
    CHAVE_AVULSO = "__avulso__"
    avulso_atual = (registro.get("presidente_avulso") or "") if editando else ""
    campo_presidente = ft.Dropdown(
        label="Presidente (opcional)",
        options=[
            ft.dropdown.Option(key="", text="— Sem presidente"),
            *[
                ft.dropdown.Option(
                    key=str(item["id"]),
                    text=f"{item['nome']} ({item['categoria']})",
                )
                for item in listar_presidentes_cadastro(escala="especiais")
            ],
            ft.dropdown.Option(key=CHAVE_AVULSO, text="Outro (fora do cadastro)…"),
        ],
        value=(
            str(registro["presidente_id"]) if editando and registro.get("presidente_id")
            else (CHAVE_AVULSO if avulso_atual else "")
        ),
        expand=True,
    )
    campo_presidente_avulso = ft.TextField(
        label="Nome de quem presidiu",
        hint_text="Fica fora do rodízio",
        value=avulso_atual,
        expand=True,
        visible=bool(avulso_atual),
    )

    def alternar_avulso(e=None):
        campo_presidente_avulso.visible = campo_presidente.value == CHAVE_AVULSO
        if not campo_presidente_avulso.visible:
            campo_presidente_avulso.value = ""
        page.update()

    campo_presidente.on_select = alternar_avulso
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

    def fechar(_=None):
        page.pop_dialog()

    def salvar(_=None):
        # A data digitada manda: quem preencheu "outra data" quer aquele dia,
        # não o que ficou selecionado no seletor de fins de semana.
        data_livre = (campo_data_livre.value or "").strip()
        data_final = _normalizar_data_arranjo(data_livre) if data_livre else campo_data.value
        if data_livre and not data_final:
            texto_erro.value = "A outra data precisa estar no formato DD/MM/AAAA."
            texto_erro.visible = True
            page.update()
            return
        if not data_final:
            texto_erro.value = "Selecione a data ou informe outra."
            texto_erro.visible = True
            page.update()
            return
        # A lista de datas especiais é por mês: gravar fora dele faria o
        # registro sumir da tela logo depois de salvo.
        if int(data_final[3:5]) != mes or int(data_final[6:10]) != ano:
            texto_erro.value = (
                f"Esta aba é de {NOMES_MESES[mes]} de {ano}. Abra o mês da data "
                "para cadastrá-la lá."
            )
            texto_erro.visible = True
            page.update()
            return
        try:
            salvar_data_especial(
                data_final,
                campo_tipo.value or (campo_tipo.options[0].key if campo_tipo.options else "Evento"),
                (campo_orador.value or "").strip(),
                (campo_tema.value or "").strip(),
                (
                    int(campo_presidente.value)
                    if campo_presidente.value and campo_presidente.value != CHAVE_AVULSO
                    else None
                ),
                registro_id=registro["id"] if editando else None,
                congregacao_id=int(campo_congregacao.value) if campo_congregacao.value else None,
                presidente_avulso=(
                    (campo_presidente_avulso.value or "").strip()
                    if campo_presidente.value == CHAVE_AVULSO else ""
                ),
            )
        except Exception:
            logger.exception("Falha ao salvar data especial")
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
                        # No celular, Data e Tipo empilhados (lado a lado com o
                        # botão de engrenagem sobrava só um filete para o valor).
                        *(
                            [
                                campo_data,
                                campo_data_livre,
                                ft.Row(
                                    [
                                        campo_tipo,
                                        ft.IconButton(
                                            icon=ft.Icons.SETTINGS_OUTLINED,
                                            tooltip="Gerenciar tipos de evento",
                                            on_click=abrir_gerenciar_tipos,
                                        ),
                                    ],
                                    spacing=4,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ]
                            if eh_mobile()
                            else [
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
                                campo_data_livre,
                            ]
                        ),
                        campo_orador,
                        campo_tema,
                        campo_congregacao,
                        campo_presidente,
                        campo_presidente_avulso,
                        ft.Text(
                            "Sem orador nem tema, o tipo do evento aparece no lugar do "
                            "orador no Quadro de Anúncios. Com discurso, mostra o orador, "
                            "o tema e a congregação escolhida.",
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                        ),
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=_largura_dialog(page, 520),
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


async def _dialog_whatsapp_designacao_envio(
    page: ft.Page,
    designacao: dict,
    telefone_destino: str = "",
    ao_enviar: Callable[[], None] | None = None,
):
    """Oferece salvar ou enviar por WhatsApp a imagem da designação.

    No celular a imagem só é gerada quando o usuário escolhe uma ação — sem
    diálogo intermediário mostrando o caminho interno do arquivo.

    ``telefone_destino`` abre a conversa já com esse número (usado na
    designação avulsa, que vai direto para o orador); sem ele o PC cai no
    telefone do coordenador, como antes.
    """
    if eh_mobile():
        def fechar_dialog(_=None):
            page.pop_dialog()

        async def _salvar():
            caminho, erro = gerar_png_designacao_envio(designacao)
            if erro:
                mostrar_aviso(page, "Erro ao gerar imagem", erro)
                return
            fechar_dialog()
            entregar_arquivo(page, caminho, abrir_pasta_do_arquivo)

        async def _enviar_whatsapp():
            caminho, erro = gerar_png_designacao_envio(designacao)
            if erro:
                mostrar_aviso(page, "Erro ao gerar imagem", erro)
                return
            fechar_dialog()
            if _share_global is not None:
                try:
                    await _share_global.share_files([ft.ShareFile.from_path(caminho)])
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Falha ao compartilhar o arquivo")
                    mostrar_aviso(page, "Não foi possível compartilhar", f"Detalhes: {exc}")
                    return
                if ao_enviar:
                    ao_enviar()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Enviar designação"),
                content=ft.Text(
                    "Gere a imagem da designação para salvar ou enviar pelo WhatsApp.",
                    size=fonte(13),
                    color=TEXTO_SECUNDARIO,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=fechar_dialog),
                    ft.OutlinedButton(
                        "Salvar arquivo",
                        icon=ft.Icons.SAVE_ALT,
                        on_click=lambda _: page.run_task(_salvar),
                    ),
                    ft.FilledButton(
                        "Enviar pelo WhatsApp",
                        icon=ft.Icons.CHAT,
                        style=ft.ButtonStyle(bgcolor="#25D366", color="#FFFFFF"),
                        on_click=lambda _: page.run_task(_enviar_whatsapp),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )
        page.update()
        return

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
            # No celular: compartilhamento nativo somente com a IMAGEM —
            # sem texto junto (a imagem já traz todas as informações).
            if eh_mobile() and _share_global is not None:
                async def _compartilhar():
                    try:
                        await _share_global.share_files(
                            [ft.ShareFile.from_path(caminho)],
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Falha ao compartilhar a imagem")
                        mostrar_aviso(page, "Não foi possível compartilhar",
                                      f"Detalhes: {exc}")

                page.run_task(_compartilhar)
                fechar_dialog()
                if ao_enviar:
                    ao_enviar()
                return

            # No PC: não existe um jeito programático de anexar arquivo num
            # link do WhatsApp Web, então copia a IMAGEM para a área de
            # transferência (Windows) — falta só colar (Ctrl+V) na conversa e
            # enviar, do mesmo jeito que o celular manda só a imagem. Sem
            # esse recurso (Linux, ou sem pywin32), cai no texto de antes,
            # pré-preenchido no WhatsApp Web, com a imagem anexada à parte.
            config = carregar_configuracao()
            tel = telefone_destino.strip() or config.get("telefone_coordenador", "")
            imagem_copiada = copiar_imagem_para_area_transferencia(caminho)
            if tel:
                webbrowser.open(gerar_link_whatsapp(tel, "" if imagem_copiada else mensagem))
                if imagem_copiada:
                    mostrar_sucesso(
                        page, "Imagem copiada. Cole (Ctrl+V) na conversa que abriu e envie."
                    )
            elif imagem_copiada:
                mostrar_sucesso(
                    page,
                    "Imagem copiada. Abra o WhatsApp, cole (Ctrl+V) na conversa e envie.",
                )
            else:
                copiar_texto(
                    page, mensagem,
                    "Mensagem copiada. Cole no WhatsApp e anexe a imagem.",
                )
            fechar_dialog()
            if ao_enviar:
                ao_enviar()

        def abrir_pasta(_=None):
            entregar_arquivo(page, caminho, abrir_pasta_do_arquivo)
            fechar_dialog()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Imagem gerada"),
                content=ft.Text(f"A imagem foi salva em:\n{caminho}", size=fonte(13), color=TEXTO_SECUNDARIO),
                actions=[
                    ft.TextButton("Fechar", on_click=fechar_dialog),
                    ft.OutlinedButton(_rotulo_entrega(), icon=_icone_entrega(), on_click=abrir_pasta),
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
        logger.exception("Falha ao gerar a imagem para o WhatsApp")
        mostrar_aviso(page, "Erro", f"Não foi possível gerar a imagem: {exc}")


def _abrir_whatsapp_designacao_envio(
    page: ft.Page, registro: dict, ao_enviar: Callable[[], None] | None = None
) -> None:
    """Prepara os dados da designação enviada (com a congregação de destino)."""
    cong = None
    if registro.get("congregacao_id"):
        cong = carregar_congregacao(int(registro["congregacao_id"]))
    cong = cong or {}
    designacao = {
        "data": registro.get("data") or "",
        "orador": nome_oradores(registro),
        "tema": _rotulo_tema_orador_arranjo(registro),
        "congregacao": cong.get("nome") or registro.get("congregacao_nome", ""),
        "dia_semana": cong.get("dia_semana", ""),
        "horario": cong.get("horario", ""),
        "endereco": cong.get("endereco", ""),
        "responsavel": cong.get("responsavel", ""),
        "telefone": cong.get("telefone", ""),
    }
    page.run_task(_dialog_whatsapp_designacao_envio, page, designacao, "", ao_enviar)


def _abrir_whatsapp_designacao_recebida(
    page: ft.Page, registro: dict, arranjo: dict
) -> None:
    """Designação avulsa de um orador RECEBIDO, para mandar direto a ele.

    Serve para o arranjo feito pessoalmente com o orador (fora do combinado com
    a congregação anfitriã do mês): o destino é a MINHA congregação, que é onde
    o recebido vem discursar, com o meu contato de coordenador.
    """
    reunioes = _obter_reunioes_dialog(arranjo)
    config = carregar_configuracao()

    endereco = ""
    minha_id = obter_id_minha_congregacao()
    if minha_id:
        minha_cong = carregar_congregacao(int(minha_id)) or {}
        endereco = (minha_cong.get("endereco") or "").strip()
    if not endereco:
        endereco = " - ".join(
            parte for parte in (config.get("endereco"), config.get("cidade")) if parte
        )

    telefone_orador = ""
    if registro.get("orador_id"):
        orador = carregar_orador(int(registro["orador_id"])) or {}
        telefone_orador = (orador.get("telefone") or "").strip()

    designacao = {
        "data": registro.get("data") or "",
        "orador": nome_oradores(registro),
        "tema": _rotulo_tema_orador_arranjo(registro),
        "congregacao": reunioes["ita_nome"],
        "dia_semana": reunioes["ita_dia"],
        "horario": reunioes["ita_horario"],
        "endereco": endereco,
        "responsavel": config.get("coordenador_discursos", ""),
        "telefone": config.get("telefone_coordenador", ""),
    }
    page.run_task(
        _dialog_whatsapp_designacao_envio, page, designacao, telefone_orador
    )


def abrir_dialog_mensagem_presidencia(
    page: ft.Page,
    data_str: str,
    presidente: dict,
    orador: str = "",
    congregacao: str = "",
    tema: str = "",
) -> None:
    """Monta e envia ao presidente do dia a mensagem com os dados da reunião.

    O coordenador só digita o número do cântico — orador, congregação e tema
    chegam prontos de quem chama (o que já está programado para a data).
    """
    campo_cantico = ft.TextField(
        label="Número do cântico",
        hint_text=f"1 a {TOTAL_CANTICOS}",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
        width=None if eh_mobile() else 200,
    )
    texto_cantico = ft.Text("", size=fonte(12), color=TEXTO_SECUNDARIO)
    previa = ft.Text("", size=fonte(13), color=TEXTO_PRIMARIO, selectable=True)

    def mensagem_atual() -> str:
        return montar_mensagem_presidencia(
            rotulo_cantico(campo_cantico.value), orador, congregacao, tema
        )

    def atualizar_previa(_=None):
        numero = (campo_cantico.value or "").strip()
        titulo = titulo_cantico(numero)
        if not numero:
            texto_cantico.value = ""
            texto_cantico.color = TEXTO_SECUNDARIO
        elif titulo:
            texto_cantico.value = titulo
            texto_cantico.color = COR_SUCESSO
        else:
            texto_cantico.value = (
                f"Não existe cântico com esse número (1 a {TOTAL_CANTICOS})."
            )
            texto_cantico.color = COR_ERRO
        previa.value = mensagem_atual()
        page.update()

    campo_cantico.on_change = atualizar_previa
    atualizar_previa()

    def fechar(_=None):
        page.pop_dialog()

    def copiar(_=None):
        texto = mensagem_atual()
        fechar()
        copiar_texto(page, texto, "Mensagem copiada.")

    def enviar(_=None):
        telefone = (presidente.get("telefone") or "").strip()
        if not telefone:
            copiar_texto(page, mensagem_atual(), "")
            fechar()
            mostrar_aviso(
                page,
                "Sem telefone cadastrado",
                f"{presidente.get('nome', 'O presidente')} não tem telefone no "
                "cadastro (Minha congregação → Presidentes). A mensagem foi "
                "copiada — cole no WhatsApp.",
            )
            return
        abrir_url(page, gerar_link_whatsapp(telefone, mensagem_atual()))
        fechar()

    aviso_sem_programacao = ft.Text(
        "Ainda não há orador programado para esta data. Confira antes de enviar.",
        size=fonte(12),
        color=COR_AVISO,
        italic=True,
        visible=not orador.strip(),
    )

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Column(
                [
                    ft.Text("Mensagem da presidência", size=fonte(18),
                            weight=ft.FontWeight.W_600),
                    ft.Text(
                        f"{_formatar_data_exibicao(data_str)} — "
                        f"{presidente.get('nome', '')}",
                        size=fonte(13),
                        color=TEXTO_SECUNDARIO,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
            content=ft.Container(
                width=_largura_dialog(page, 460),
                content=ft.Column(
                    [
                        campo_cantico,
                        texto_cantico,
                        aviso_sem_programacao,
                        ft.Container(height=4),
                        ft.Text("Prévia", size=fonte(12), weight=ft.FontWeight.W_700,
                                color=TEXTO_SECUNDARIO),
                        ft.Container(
                            content=previa,
                            bgcolor=FUNDO_ELEVADO,
                            border_radius=8,
                            padding=ft.Padding.all(12),
                        ),
                    ],
                    spacing=8,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.OutlinedButton("Copiar", icon=ft.Icons.CONTENT_COPY, on_click=copiar),
                ft.FilledButton(
                    "Enviar pelo WhatsApp",
                    icon=ft.Icons.CHAT,
                    style=ft.ButtonStyle(bgcolor="#25D366", color="#FFFFFF"),
                    on_click=enviar,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


def abrir_dialog_falar_responsavel(page: ft.Page, arranjo: dict) -> None:
    """Fala com o irmão responsável pela congregação anfitriã daquele mês.

    É com ele que o arranjo do mês é combinado, então o contato fica à mão no
    próprio diálogo do mês, em vez de ter que procurar em Congregações.
    """
    cong = {}
    if arranjo.get("congregacao_host_id"):
        cong = carregar_congregacao(int(arranjo["congregacao_host_id"])) or {}
    nome_cong = (cong.get("nome") or arranjo.get("congregacao") or "").strip()
    responsavel = (cong.get("responsavel") or "").strip()
    telefone = (cong.get("telefone") or "").strip()

    def fechar(_=None):
        page.pop_dialog()

    if not telefone:
        mostrar_aviso(
            page,
            "Sem telefone cadastrado",
            f"A congregação {nome_cong or 'anfitriã'} não tem telefone em "
            "Congregações. Cadastre lá para falar com o responsável por aqui.",
        )
        return

    mes = int(arranjo.get("mes_inicio", 1))
    ano = int(arranjo.get("ano", date.today().year))
    config = carregar_configuracao()
    mensagem = (
        f"Olá{', ' + responsavel.split()[0] if responsavel else ''}! "
        f"Aqui é {config.get('coordenador_discursos') or 'o coordenador'}, "
        f"da {config.get('nome_congregacao') or 'nossa congregação'}. "
        f"Estou organizando o arranjo de {NOMES_MESES[mes]} de {ano} com a "
        f"{nome_cong or 'sua congregação'}."
    )

    campo_mensagem = ft.TextField(
        label="Mensagem",
        value=mensagem,
        multiline=True,
        min_lines=3,
        max_lines=6,
    )

    def abrir_whatsapp(_=None):
        abrir_url(page, gerar_link_whatsapp(telefone, campo_mensagem.value or ""))
        fechar()

    def copiar(_=None):
        texto = campo_mensagem.value or ""
        fechar()
        copiar_texto(page, texto, "Mensagem copiada.")

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Column(
                [
                    ft.Text("Falar com o responsável", size=fonte(18),
                            weight=ft.FontWeight.W_600),
                    ft.Text(
                        " · ".join(
                            parte
                            for parte in (nome_cong, responsavel, mascara_telefone(telefone))
                            if parte
                        ),
                        size=fonte(13),
                        color=TEXTO_SECUNDARIO,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
            content=ft.Container(
                width=_largura_dialog(page, 460),
                content=ft.Column([campo_mensagem], spacing=8, tight=True),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.OutlinedButton("Copiar", icon=ft.Icons.CONTENT_COPY, on_click=copiar),
                ft.FilledButton(
                    "Abrir WhatsApp",
                    icon=ft.Icons.CHAT,
                    style=ft.ButtonStyle(bgcolor="#25D366", color="#FFFFFF"),
                    on_click=abrir_whatsapp,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


def _linha_presidente_data_especial(
    page: ft.Page,
    ano: int,
    mes: int,
    rotulo_data: str,
    especial: dict,
    presidente_solto: dict | None,
    atualizar: Callable[[], None],
) -> ft.Control:
    """Semana tomada por um evento especial: não pede presidente.

    Assembleia, congresso e afins substituem a reunião normal, então cobrar um
    presidente aqui é falso alarme — a linha mostra o evento em vez do seletor.
    Se o evento tiver presidente (visita do superintendente, por exemplo), ele
    é definido no cadastro da própria data especial, e não em dois lugares.
    """
    nome_presidente = (especial.get("presidente_nome") or "").strip()
    chip = ft.Container(
        content=ft.Text(
            especial.get("tipo") or "Data especial",
            size=fonte(12),
            weight=ft.FontWeight.W_600,
            color=COR_AVISO,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        bgcolor=ft.Colors.with_opacity(0.13, COR_AVISO),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=9, vertical=3),
    )
    situacao = ft.Text(
        f"Presidente: {nome_presidente}" if nome_presidente else "Sem presidente",
        size=fonte(12),
        color=TEXTO_SECUNDARIO,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    def editar(_=None):
        abrir_dialog_data_especial(page, ano, mes, atualizar, especial)

    botao_editar = ft.IconButton(
        icon=ft.Icons.EDIT_OUTLINED,
        icon_size=fonte(18),
        icon_color=COR_DESTAQUE,
        tooltip="Editar a data especial",
        on_click=editar,
    )

    # Sobra de quando a data ainda não era especial: um presidente designado
    # aqui continuaria contando no rodízio. Oferece limpar.
    def limpar_sobra(_=None):
        excluir_presidente(especial["data"])
        atualizar()

    acoes = [botao_editar]
    if presidente_solto:
        situacao.value = (
            f"Presidente avulso: {presidente_solto['nome']} (a data virou especial)"
        )
        situacao.color = COR_AVISO
        acoes.insert(
            0,
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_size=fonte(18),
                icon_color=COR_ERRO,
                tooltip="Tirar o presidente desta data",
                on_click=limpar_sobra,
            ),
        )

    conteudo_texto = ft.Column(
        [ft.Text(rotulo_data, size=fonte(13), weight=ft.FontWeight.W_600), situacao],
        spacing=2,
        tight=True,
        expand=True,
    )
    if eh_mobile():
        corpo = ft.Column(
            [
                ft.Row([conteudo_texto], spacing=8),
                ft.Row(
                    [ft.Container(content=chip, expand=True,
                                  alignment=ft.Alignment.CENTER_LEFT), *acoes],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=4,
            tight=True,
        )
    else:
        corpo = ft.Row(
            [ft.Container(content=conteudo_texto, width=260), chip,
             ft.Container(expand=True), *acoes],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Container(
        content=corpo,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, COR_AVISO)),
        border_radius=8,
    )


def abrir_dialog_trocar_data(
    page: ft.Page,
    registro: dict,
    arranjo: dict,
    arranjo_id: int,
    atualizar_listas: Callable[[], None],
) -> None:
    """Troca ou move a data de uma designação sem abrir o editor completo.

    Escolher a data de outro orador TROCA as duas (swap); escolher uma data
    livre sugerida do mês apenas MOVE o registro.
    """
    tipo = registro["tipo"]
    registros = carregar_oradores_arranjo(arranjo_id)
    outros = [
        r
        for r in registros
        if r["tipo"] == tipo and int(r["id"]) != int(registro["id"]) and r.get("data")
    ]
    sugestoes = _sugerir_datas_arranjo(arranjo, tipo, registros, quantidade=8)

    def fechar(_=None):
        page.pop_dialog()

    def trocar(outro: dict):
        trocar_datas_designacoes(int(registro["id"]), int(outro["id"]))
        fechar()
        atualizar_listas()

    def mover(data_str: str):
        atualizar_data_designacao(int(registro["id"]), data_str)
        fechar()
        atualizar_listas()

    itens: list[ft.Control] = []
    if outros:
        itens.append(
            ft.Text("Trocar com…", size=fonte(12), weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO)
        )
        for outro in outros:
            itens.append(
                ft.ListTile(
                    dense=True,
                    leading=ft.Icon(ft.Icons.SWAP_HORIZ, size=fonte(18), color=COR_DESTAQUE),
                    title=ft.Text(nome_oradores(outro), size=fonte(13)),
                    subtitle=ft.Text(
                        _formatar_data_exibicao(outro.get("data")), size=fonte(12)
                    ),
                    on_click=lambda e, o=dict(outro): trocar(o),
                )
            )
    if sugestoes:
        itens.append(
            ft.Text("Mover para data livre…", size=fonte(12), weight=ft.FontWeight.W_700,
                    color=TEXTO_SECUNDARIO)
        )
        for item in sugestoes:
            itens.append(
                ft.ListTile(
                    dense=True,
                    leading=ft.Icon(
                        ft.Icons.EVENT_AVAILABLE, size=fonte(18), color=COR_SUCESSO
                    ),
                    title=ft.Text(item["rotulo"], size=fonte(13)),
                    on_click=lambda e, d=item["data"]: mover(d),
                )
            )
    if not itens:
        itens = [
            ft.Text(
                "Não há outras datas neste mês para trocar ou mover.",
                size=fonte(13),
                color=TEXTO_SECUNDARIO,
                italic=True,
            )
        ]

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(
                f"Data de {nome_oradores(registro)} — "
                f"{_formatar_data_exibicao(registro.get('data'))}",
                size=fonte(16),
                weight=ft.FontWeight.W_600,
            ),
            content=ft.Container(
                width=_largura_dialog(page, 420),
                content=ft.Column(
                    itens,
                    spacing=2,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                height=min(420, 64 + 52 * max(1, len(itens))),
            ),
            actions=[ft.TextButton("Cancelar", on_click=fechar)],
        )
    )


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
            logger.exception("Falha ao remover orador do arranjo")
            mostrar_aviso(page, "Erro", "Não foi possível remover o orador.")

    def editar_orador(item: dict):
        abrir_dialog_editar_orador_arranjo(page, item, atualizar_listas)

    def whatsapp_designacao(item: dict):
        def marcar_convite():
            """Mandou a mensagem: o app conta os dias a partir daqui."""
            registrar_convite_enviado(int(item["id"]))
            atualizar_listas()

        _abrir_whatsapp_designacao_envio(page, item, ao_enviar=marcar_convite)

    def whatsapp_recebido(item: dict):
        _abrir_whatsapp_designacao_recebida(page, item, arranjo)

    def alterar_status(registro_id: int, novo_status: str):
        atualizar_status_orador_arranjo(registro_id, novo_status)
        atualizar_listas()

    def mover_data(item: dict):
        abrir_dialog_trocar_data(page, item, arranjo, arranjo_id, atualizar_listas)

    def preencher_listas():
        registros = carregar_oradores_arranjo(arranjo_id)
        recebidos = [r for r in registros if r["tipo"] == "recebido"]
        enviados = [r for r in registros if r["tipo"] == "enviado"]

        lista_recebidos.controls = _montar_tabela_secao(
            recebidos,
            "Nenhum orador cadastrado.",
            editar_orador,
            remover_orador,
            on_whatsapp=whatsapp_recebido,
            on_status=alterar_status,
            on_mover=mover_data,
        )
        lista_enviados.controls = _montar_tabela_secao(
            enviados,
            "Nenhuma designação cadastrada.",
            editar_orador,
            remover_orador,
            on_whatsapp=whatsapp_designacao,
            on_status=alterar_status,
            on_mover=mover_data,
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
                    size=fonte(13),
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

            chip_tipo_especial = ft.Container(
                content=ft.Text(
                    registro["tipo"],
                    size=fonte(12),
                    weight=ft.FontWeight.W_600,
                    color=COR_AVISO,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                bgcolor=ft.Colors.with_opacity(0.13, COR_AVISO),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=9, vertical=3),
            )
            if eh_mobile():
                # Duas linhas no celular: data + tipo + ações, detalhes abaixo.
                return ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        registro["data"][:5],
                                        size=fonte(13),
                                        weight=ft.FontWeight.W_600,
                                        color=TEXTO_PRIMARIO,
                                    ),
                                    ft.Container(content=chip_tipo_especial, expand=True,
                                                 alignment=ft.Alignment.CENTER_LEFT),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_size=fonte(17),
                                        tooltip="Editar",
                                        icon_color=COR_DESTAQUE,
                                        on_click=editar,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_size=fonte(17),
                                        tooltip="Excluir",
                                        icon_color=COR_ERRO,
                                        on_click=excluir,
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                detalhes,
                                size=fonte(12),
                                color=TEXTO_SECUNDARIO,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border=ft.Border.all(1, BORDA_SUAVE),
                    border_radius=8,
                )

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Text(
                            registro["data"][:5],
                            size=fonte(13),
                            weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO,
                            width=52,
                        ),
                        chip_tipo_especial,
                        ft.Text(
                            detalhes,
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_size=fonte(17),
                            tooltip="Editar",
                            icon_color=COR_DESTAQUE,
                            on_click=editar,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=fonte(17),
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
        # Quem está no cadastro só para as datas especiais não é oferecido
        # aqui: é o ponto de ter duas escalas.
        cadastro = listar_presidentes_cadastro(escala="normais")
        # Assembleia, congresso, visita…: a semana existe, mas não é a reunião
        # normal, então não cobra presidente aqui (quem cuida é a aba Especiais).
        especiais_mes = listar_datas_especiais_por_ano(ano)

        if not cadastro:
            lista_presidentes.controls = [
                ft.Text(
                    "Nenhum presidente cadastrado ainda. "
                    "Cadastre-os em Minha congregação → Presidentes.",
                    size=fonte(13),
                    color=TEXTO_SECUNDARIO,
                    italic=True,
                )
            ]
            return

        opcoes = [
            ft.dropdown.Option(key=str(item["id"]), text=f"{item['nome']} ({item['categoria']})")
            for item in cadastro
        ]
        # Última opção: quem não está no cadastro (o irmão que saiu da
        # congregação, um visitante) entra pelo nome, sem virar cadastro nem
        # pesar no revezamento.
        opcoes.append(
            ft.dropdown.Option(key=CHAVE_PRESIDENTE_AVULSO, text="✏️  Digitar outro nome…")
        )
        linhas: list[ft.Control] = []
        for data_ref in datas:
            data_str = _formatar_data_arranjo(data_ref)
            atual = presidentes.get(data_str)
            rotulo_data_texto = (
                f"{_rotulo_weekday(data_ref.weekday())}, "
                f"{data_ref.day:02d}/{data_ref.month:02d}"
            )
            especial = especiais_mes.get(data_str)
            if especial:
                linhas.append(
                    _linha_presidente_data_especial(
                        page, ano, mes, rotulo_data_texto, especial,
                        atual, atualizar_listas,
                    )
                )
                continue
            eh_avulso = bool(atual and atual.get("avulso"))
            nome_avulso = atual["nome"] if eh_avulso else ""
            opcoes_data = opcoes
            if eh_avulso:
                # O nome digitado não existe entre as opções: entra como uma
                # opção própria para o campo não aparecer vazio.
                opcoes_data = [
                    ft.dropdown.Option(
                        key=CHAVE_PRESIDENTE_AVULSO_ATUAL,
                        text=f"{nome_avulso} (fora do rodízio)",
                    ),
                    *opcoes,
                ]
                valor_atual = CHAVE_PRESIDENTE_AVULSO_ATUAL
            elif atual:
                valor_atual = str(atual["presidente_id"])
            else:
                valor_atual = None
            campo = ft.Dropdown(
                label="Presidente",
                options=opcoes_data,
                value=valor_atual,
                expand=True,
            )

            # `nome` e `anterior` vêm como padrão porque o callback roda depois
            # do laço: sem isso, todas as datas leriam a última iteração.
            def ao_mudar(e, data_ref=data_str, campo=campo, anterior=valor_atual,
                         nome=nome_avulso):
                if campo.value == CHAVE_PRESIDENTE_AVULSO:
                    # Volta ao valor de antes: só o diálogo confirma a troca.
                    campo.value = anterior
                    abrir_dialog_presidente_avulso(
                        page, data_ref, atualizar_listas, nome_atual=nome,
                    )
                elif campo.value == CHAVE_PRESIDENTE_AVULSO_ATUAL:
                    pass  # continua o mesmo avulso: nada a gravar
                elif campo.value:
                    salvar_presidente(data_ref, int(campo.value))
                else:
                    excluir_presidente(data_ref)

            campo.on_select = ao_mudar

            def ao_remover(e, data_ref=data_str, campo=campo):
                excluir_presidente(data_ref)
                campo.value = None
                page.update()

            rotulo_data = ft.Text(
                rotulo_data_texto,
                size=fonte(13),
                weight=ft.FontWeight.W_600,
            )
            botao_remover = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_size=fonte(18),
                icon_color=COR_ERRO,
                tooltip="Remover presidente desta data",
                on_click=ao_remover,
            )
            if eh_mobile():
                # Data em cima, dropdown em largura total embaixo — com a
                # data ao lado o dropdown ficava estreito demais para o nome.
                linhas.append(
                    ft.Column(
                        [
                            rotulo_data,
                            ft.Row(
                                [campo, botao_remover],
                                spacing=4,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=4,
                        tight=True,
                    )
                )
            else:
                linhas.append(
                    ft.Row(
                        [
                            ft.Container(content=rotulo_data, width=170),
                            campo,
                            botao_remover,
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

    def exportar_agenda(_=None):
        """Escreve o mês num .ics para entrar na agenda do celular."""
        try:
            eventos = eventos_do_mes(
                ano,
                mes,
                carregar_recebidos_por_ano(ano),
                carregar_enviados_por_ano(ano),
                carregar_presidentes_por_ano(ano),
                listar_datas_especiais_por_ano(ano),
            )
            if not eventos:
                mostrar_aviso(
                    page,
                    "Nada para exportar",
                    "Este mês ainda não tem orador, designação ou data especial.",
                )
                return
            EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            caminho = EXPORTS_DIR / f"arranjo_{ano}_{mes:02d}.ics"
            caminho.write_text(gerar_ics(eventos), encoding="utf-8")
        except Exception as exc:
            logger.exception("Falha ao exportar o mês para a agenda")
            mostrar_aviso(page, "Erro", f"Não foi possível gerar o arquivo: {exc}")
            return
        entregar_arquivo(page, str(caminho), abrir_arquivo)

    def falar_com_responsavel(_=None):
        abrir_dialog_falar_responsavel(page, arranjo)

    def editar_arranjo(_=None):
        fechar()
        on_editar_arranjo(arranjo_id)

    def excluir_arranjo(_=None):
        fechar()
        on_excluir_arranjo(arranjo_id)

    def _cabecalho_secao(titulo: str, on_exportar, on_adicionar) -> ft.Control:
        texto = ft.Text(
            titulo, size=fonte(16), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO,
            expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
        )
        botao_exportar = ft.OutlinedButton(
            content="Exportar PNG", icon=ft.Icons.IMAGE_OUTLINED, on_click=on_exportar,
        )
        botao_adicionar = ft.FilledButton(
            content="Adicionar", icon=ft.Icons.ADD, on_click=on_adicionar,
        )
        if eh_mobile():
            # No celular título e botões não cabem lado a lado: empilha.
            return ft.Column(
                [
                    texto,
                    ft.Row([botao_exportar, botao_adicionar], spacing=8, wrap=True),
                ],
                spacing=8,
                tight=True,
            )
        return ft.Row(
            [texto, botao_exportar, botao_adicionar],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _cabecalho_secao_desc(descricao: str, *botoes: ft.Control) -> ft.Control:
        """Cabeçalho com descrição longa + botões. No celular empilha."""
        if eh_mobile():
            return ft.Column(
                [
                    ft.Text(descricao, size=fonte(13), color=TEXTO_SECUNDARIO),
                    ft.Row(list(botoes), spacing=8, wrap=True),
                ],
                spacing=8,
                tight=True,
            )
        return ft.Row(
            [
                ft.Text(descricao, size=fonte(13), color=TEXTO_SECUNDARIO, expand=True),
                *botoes,
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
                "A ordem do rodízio é definida em Minha congregação → Presidentes.",
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
                    size=fonte(13),
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
            _cabecalho_secao_desc(
                "Quem preside a reunião de fim de semana em cada data. "
                "Datas especiais não pedem presidente.",
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

    def preencher_rodizio_especiais(_=None):
        preenchidas = preencher_presidentes_especiais_rodizio(ano, mes)
        if preenchidas:
            mostrar_sucesso(
                page, f"{preenchidas} data(s) especial(is) preenchida(s) pelo rodízio."
            )
            atualizar_listas()
        else:
            mostrar_aviso(
                page,
                "Nada para preencher",
                "Nenhuma data especial deste mês está esperando presidente. "
                "Assembleia e congresso não pedem presidente. Isso é marcado "
                "por tipo de evento, na engrenagem ao lado do campo Tipo."
                "\n\n"
                "O rodízio das datas especiais usa apenas anciãos.",
            )

    secao_especiais = ft.Column(
        [
            _cabecalho_secao_desc(
                "Assembleias, congressos, visitas e outros eventos que "
                "substituem a reunião normal",
                ft.OutlinedButton(
                    content="Preencher em rodízio",
                    icon=ft.Icons.AUTORENEW,
                    tooltip="Sorteia entre os anciãos quem preside as datas "
                            "especiais deste mês que ainda estão sem presidente",
                    on_click=preencher_rodizio_especiais,
                ),
                ft.FilledButton(
                    content="Adicionar",
                    icon=ft.Icons.ADD,
                    on_click=abrir_adicionar_especial,
                ),
            ),
            ft.Container(height=12),
            lista_especiais,
        ],
        spacing=0,
        tight=True,
        visible=False,
    )

    def aplicar_aba(selecionada: str):
        secao_recebidos.visible = selecionada == "recebidos"
        secao_enviados.visible = selecionada == "enviados"
        secao_presidentes.visible = selecionada == "presidentes"
        secao_especiais.visible = selecionada == "especiais"

    ROTULOS_ABAS = [
        ("recebidos", "Oradores"),
        ("enviados", "Designações"),
        ("presidentes", "Presidentes"),
        ("especiais", "Especiais"),
    ]

    if eh_mobile():
        # As 4 abas não cabem lado a lado no celular (o SegmentedButton quebra
        # o texto letra a letra) — usa chips numa linha com rolagem horizontal.
        chips_abas: dict[str, tuple[ft.Container, ft.Text]] = {}

        def selecionar_aba(valor: str):
            aplicar_aba(valor)
            for v, (chip, texto) in chips_abas.items():
                ativo = v == valor
                chip.bgcolor = (
                    ft.Colors.with_opacity(0.18, COR_DESTAQUE_CLARA)
                    if ativo else ft.Colors.TRANSPARENT
                )
                chip.border = ft.Border.all(
                    1, COR_DESTAQUE if ativo else BORDA_SUAVE
                )
                texto.color = COR_DESTAQUE_SUAVE if ativo else TEXTO_SECUNDARIO
                texto.weight = ft.FontWeight.W_700 if ativo else ft.FontWeight.W_500
            page.update()

        def _chip_aba(valor: str, rotulo: str) -> ft.Container:
            ativo = valor == "recebidos"
            texto = ft.Text(
                rotulo,
                size=fonte(13),
                no_wrap=True,
                color=COR_DESTAQUE_SUAVE if ativo else TEXTO_SECUNDARIO,
                weight=ft.FontWeight.W_700 if ativo else ft.FontWeight.W_500,
            )
            chip = ft.Container(
                content=texto,
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                border_radius=18,
                bgcolor=(
                    ft.Colors.with_opacity(0.18, COR_DESTAQUE_CLARA)
                    if ativo else ft.Colors.TRANSPARENT
                ),
                border=ft.Border.all(1, COR_DESTAQUE if ativo else BORDA_SUAVE),
                on_click=lambda e, v=valor: selecionar_aba(v),
                ink=True,
            )
            chips_abas[valor] = (chip, texto)
            return chip

        alternador_abas = ft.Row(
            [_chip_aba(valor, rotulo) for valor, rotulo in ROTULOS_ABAS],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
        )
    else:
        def mudar_aba(e):
            selecionada = e.control.selected[0] if e.control.selected else "recebidos"
            aplicar_aba(selecionada)
            page.update()

        alternador_abas = ft.SegmentedButton(
            selected=["recebidos"],
            allow_empty_selection=False,
            on_change=mudar_aba,
            segments=[
                ft.Segment(value=valor, label=ft.Text(rotulo))
                for valor, rotulo in ROTULOS_ABAS
            ],
        )

    dialog_mes = ft.AlertDialog(
        modal=True,
        title=ft.Column(
            [
                ft.Text(
                    f"{titulo_mes} — {reunioes['host_nome']}",
                    size=fonte(20),
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(linha_reunioes, size=fonte(13), color=TEXTO_SECUNDARIO),
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
                width=_largura_dialog(page, LARGURA_DIALOG_MES),
                scroll=ft.ScrollMode.AUTO,
            ),
            height=altura_conteudo,
            padding=ft.Padding.symmetric(horizontal=4, vertical=8),
        ),
        content_padding=ft.Padding.symmetric(
            horizontal=12 if eh_mobile() else 32, vertical=16 if eh_mobile() else 24
        ),
        inset_padding=ft.Padding.all(12 if eh_mobile() else 40),
        actions=[
            _criar_rodape_dialog_mes(
                fechar,
                editar_arranjo,
                excluir_arranjo,
                falar_com_responsavel,
                on_agenda=exportar_agenda,
            ),
        ],
        actions_padding=ft.Padding.symmetric(
            horizontal=12 if eh_mobile() else 32, vertical=16
        ),
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
    campo_telefone = _campo_telefone(valor=dados["telefone"] if dados else "", expand=True)
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
    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)

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
            logger.exception("Falha ao salvar os dados da congregação")
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
                        linha_campos(campo_ano, campo_mes),
                        campo_congregacao,
                        linha_campos(campo_responsavel, campo_telefone),
                        linha_campos(campo_dia, campo_horario),
                        campo_endereco,
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                    width=_largura_dialog(page, 520),
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
            logger.exception("Falha ao excluir o arranjo do mês")
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
                    ft.Text(rotulo, size=fonte(15), weight=ft.FontWeight.W_700, color=TEXTO_SECUNDARIO),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=fonte(16), color=TEXTO_SECUNDARIO),
                            ft.Text("Cadastrar arranjo", size=fonte(13), color=TEXTO_SECUNDARIO),
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
            # No celular o card fica um por linha dentro de coluna rolável;
            # expand ali seria vertical (e inválido em scroll).
            expand=None if eh_mobile() else True,
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
        content=ft.Text(status, size=fonte(11), weight=ft.FontWeight.W_600, color=cor_status),
        bgcolor=ft.Colors.with_opacity(0.14, cor_status),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
    )

    # O selo diz o estado; esta linha diz o que fazer para fechar o mês.
    faltas: list[str] = []
    if semanas:
        if cobertas < semanas:
            faltam = semanas - cobertas
            faltas.append(f"{faltam} semana(s) sem orador")
        if presidentes < semanas:
            faltam = semanas - presidentes
            faltas.append(f"{faltam} sem presidente")
    linha_falta = (
        ft.Text(
            "Falta: " + " · ".join(faltas),
            size=fonte(11),
            color=COR_AVISO,
            max_lines=2,
        )
        if faltas
        else None
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
                        ft.Text(rotulo, size=fonte(15), weight=ft.FontWeight.W_700, color=TEXTO_PRIMARIO, expand=True),
                        badge,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=4),
                ft.Text(subtitulo, size=fonte(12), color=TEXTO_SECUNDARIO, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(height=10),
                segmentos,
                ft.Container(height=8),
                ft.Text(
                    f"{resumo['recebidos']} recebidos · {resumo['enviados']} enviados · "
                    f"{presidentes} de {semanas} pres.",
                    size=fonte(11),
                    color=TEXTO_SECUNDARIO,
                ),
                *([ft.Container(height=4), linha_falta] if linha_falta else []),
            ],
            spacing=0,
        ),
        padding=18,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(0.2),
        expand=None if eh_mobile() else True,
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
    texto_contagem = ft.Text(size=fonte(13), color=TEXTO_SECUNDARIO)

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

        def card_mes(numero_mes: int, rotulo: str) -> ft.Control:
            return _criar_card_mes_programacao(
                rotulo,
                numero_mes,
                mapa.get(numero_mes),
                _resumo_mes_programacao(
                    ano, numero_mes, recebidos, presidentes, contagens_ano, especiais
                ),
                on_abrir=abrir_oradores_mes,
                on_cadastrar=cadastrar_mes,
            )

        linhas: list[ft.Control] = []
        if eh_mobile():
            # Um card por linha: com dois lado a lado o nome do mês quebrava.
            for posicao, (numero_mes, rotulo) in enumerate(MESES_ANO):
                linhas.append(card_mes(numero_mes, rotulo))
                if posicao < len(MESES_ANO) - 1:
                    linhas.append(ft.Container(height=12))
        else:
            for indice in range(0, len(MESES_ANO), 2):
                par = MESES_ANO[indice : indice + 2]
                linhas.append(
                    ft.Row(
                        [card_mes(numero_mes, rotulo) for numero_mes, rotulo in par],
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

    def exportar_relatorio(_=None):
        from relatorios import secoes_programacao

        ano = estado["ano"]
        exportar_relatorio_pdf(
            page,
            lambda: secoes_programacao(ano),
            f"Programação de {ano}",
            "Programacao",
        )

    montar_blocos()

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Programação",
                "Oradores, designações e presidentes de cada mês",
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
                    ft.Container(expand=True),
                    botao_relatorio_tela(exportar_relatorio),
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


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

def _cartao_numero_relatorio(
    rotulo: str, valor: str, detalhe: str, cor: str, icone: str
) -> ft.Container:
    """Número grande do painel de relatórios, com rótulo e uma linha de apoio."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icone, size=fonte(16), color=cor),
                        ft.Text(
                            rotulo, size=fonte(11), color=TEXTO_SECUNDARIO,
                            weight=ft.FontWeight.W_600, expand=True,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Text(valor, size=fonte(26), weight=ft.FontWeight.W_700, color=cor),
                ft.Text(
                    detalhe, size=fonte(11), color=TEXTO_SECUNDARIO,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            spacing=2,
            tight=True,
        ),
        bgcolor=FUNDO_ELEVADO,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        expand=True,
    )


def _barra_proporcao(valor: int, total: int, cor: str, largura: int = 90) -> ft.Control:
    """Barrinha proporcional — dá a leitura do ranking sem ler os números."""
    fracao = (valor / total) if total else 0
    return ft.Container(
        content=ft.Container(
            bgcolor=cor,
            border_radius=4,
            height=6,
            width=max(3, round(largura * fracao)) if valor else 0,
        ),
        bgcolor=ft.Colors.with_opacity(0.10, cor),
        border_radius=4,
        height=6,
        width=largura,
        alignment=ft.Alignment.CENTER_LEFT,
    )


def _largura_conteudo_relatorio(page: ft.Page) -> int:
    """Largura útil de um quadro do relatório, já descontado o padding do card.

    As colunas do relatório recebem largura EXPLÍCITA a partir daqui. Usar
    ``expand`` fazia a coluna do nome nascer com zero de largura — dentro de
    uma coluna rolável a sobra é zero, então o nome simplesmente sumia da tela.
    """
    base = _largura_dialog(page, 720)
    return max(220, base - (32 if eh_mobile() else 40))


def _barra_proporcao(valor: int, total: int, cor: str, largura: int = 90) -> ft.Control:
    """Barrinha proporcional — dá a leitura do ranking sem ler os números."""
    fracao = (valor / total) if total else 0
    return ft.Container(
        content=ft.Container(
            bgcolor=cor,
            border_radius=4,
            height=6,
            width=max(3, round(largura * fracao)) if valor else 0,
        ),
        bgcolor=ft.Colors.with_opacity(0.10, cor),
        border_radius=4,
        height=6,
        width=largura,
        alignment=ft.Alignment.CENTER_LEFT,
    )


def _quadro_relatorio(titulo: str, descricao: str, corpo: list[ft.Control]) -> ft.Container:
    """Card padrão do relatório: título, uma linha de explicação e o conteúdo."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(titulo, size=fonte(15), weight=ft.FontWeight.W_600,
                        color=TEXTO_PRIMARIO),
                ft.Text(descricao, size=fonte(12), color=TEXTO_SECUNDARIO),
                ft.Container(height=10),
                *corpo,
            ],
            spacing=2,
            tight=True,
        ),
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        padding=16 if eh_mobile() else 20,
        shadow=_sombra_card(0.25),
    )


def _lista_ranking_relatorio(
    itens: list[dict],
    largura: int,
    cor: str,
    vazio: str,
) -> list[ft.Control]:
    """Ranking nome + número + barra + detalhe, em larguras fixas.

    ``itens``: ``[{nome, valor, detalhe}]``. No celular a linha é empilhada
    (nome e número em cima, barra e detalhe embaixo) porque lado a lado sobram
    poucos pixels para o nome.
    """
    if not itens:
        return [ft.Text(vazio, size=fonte(13), color=TEXTO_SECUNDARIO, italic=True)]

    maior = max((int(item["valor"]) for item in itens), default=0)
    mobile = eh_mobile()
    largura_valor = 44
    largura_detalhe = 96 if mobile else 104
    if mobile:
        largura_nome = max(80, largura - largura_valor - 10)
        largura_barra = max(40, largura - largura_detalhe - 10)
    else:
        largura_barra = 140
        largura_nome = max(
            120, largura - largura_valor - largura_barra - largura_detalhe - 36
        )

    def linha(item: dict, ultima: bool) -> ft.Control:
        nome = ft.Text(
            item["nome"], size=fonte(13), color=TEXTO_PRIMARIO,
            weight=ft.FontWeight.W_500, width=largura_nome,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        )
        valor = ft.Text(
            str(item["valor"]), size=fonte(14), weight=ft.FontWeight.W_700,
            color=cor, width=largura_valor, text_align=ft.TextAlign.RIGHT,
        )
        detalhe = ft.Text(
            item["detalhe"], size=fonte(11), color=TEXTO_SECUNDARIO,
            width=largura_detalhe, text_align=ft.TextAlign.RIGHT,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        )
        barra = _barra_proporcao(int(item["valor"]), maior, cor, largura_barra)

        if mobile:
            conteudo = ft.Column(
                [
                    ft.Row([nome, valor], spacing=10,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row([barra, detalhe], spacing=10,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ],
                spacing=5,
                tight=True,
            )
        else:
            conteudo = ft.Row(
                [nome, valor, barra, detalhe],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        return ft.Container(
            content=conteudo,
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            border=None if ultima else ft.Border(bottom=ft.BorderSide(1, BORDA_SUAVE)),
        )

    return [
        ft.Container(
            content=ft.Column(
                [linha(item, indice == len(itens) - 1) for indice, item in enumerate(itens)],
                spacing=0,
                tight=True,
            ),
            border=ft.Border.all(1, BORDA_SUAVE),
            border_radius=10,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
    ]


def _lista_meses_relatorio(meses: list[dict], largura: int) -> list[ft.Control]:
    """Mês a mês: onde estão os buracos de orador e de presidente.

    Cada mês vira uma faixa com dois selos (orador / presidente) que ficam
    verdes quando a cobertura está completa e âmbar quando falta alguém.
    """
    if not meses:
        return [
            ft.Text(
                "Nenhum arranjo cadastrado neste ano.",
                size=fonte(13), color=TEXTO_SECUNDARIO, italic=True,
            )
        ]

    def selo(rotulo: str, feito: int, total: int) -> ft.Control:
        completo = total and feito >= total
        cor = COR_SUCESSO if completo else COR_AVISO
        return ft.Container(
            content=ft.Text(
                f"{rotulo} {feito}/{total}",
                size=fonte(11), weight=ft.FontWeight.W_600, color=cor, no_wrap=True,
            ),
            bgcolor=ft.Colors.with_opacity(0.12, cor),
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        )

    largura_mes = 92 if eh_mobile() else 130

    def linha(mes: dict, ultima: bool) -> ft.Control:
        selos = ft.Row(
            [
                selo("Orador", mes["cobertas"], mes["semanas"]),
                selo("Pres.", mes["presidentes"], mes["semanas"]),
            ],
            spacing=6,
        )
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        mes["nome"], size=fonte(13), weight=ft.FontWeight.W_600,
                        color=TEXTO_PRIMARIO, width=largura_mes,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(content=selos, width=max(120, largura - largura_mes - 34)),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            border=None if ultima else ft.Border(bottom=ft.BorderSide(1, BORDA_SUAVE)),
        )

    return [
        ft.Container(
            content=ft.Column(
                [linha(mes, indice == len(meses) - 1) for indice, mes in enumerate(meses)],
                spacing=0,
                tight=True,
            ),
            border=ft.Border.all(1, BORDA_SUAVE),
            border_radius=10,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
    ]


def _lista_datas_especiais_relatorio(
    especiais: list[dict], largura: int
) -> list[ft.Control]:
    """Cada data especial do ano com o tipo e quem presidiu.

    O "—" tem dois significados diferentes, e por isso são dois textos: numa
    assembleia ninguém preside (a congregação está fora), enquanto um discurso
    especial sem nome é presidência ainda por decidir.
    """
    if not especiais:
        return [
            ft.Text(
                "Nenhuma data especial neste ano.",
                size=fonte(13), color=TEXTO_SECUNDARIO, italic=True,
            )
        ]

    mobile = eh_mobile()
    largura_data = 74 if mobile else 90

    def linha(item: dict, ultima: bool) -> ft.Control:
        presidente = item.get("presidente_nome") or ""
        pede_presidente = item.get("pede_presidente", True)
        if presidente:
            texto_pres, cor_pres, italico = presidente, TEXTO_PRIMARIO, False
        elif pede_presidente:
            texto_pres, cor_pres, italico = "a definir", COR_AVISO, True
        else:
            texto_pres, cor_pres, italico = "sem reunião local", TEXTO_SECUNDARIO, True

        tipo = ft.Text(
            item["tipo"], size=fonte(12), color=TEXTO_SECUNDARIO,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        )
        nome = ft.Text(
            texto_pres, size=fonte(13), weight=ft.FontWeight.W_600,
            color=cor_pres, italic=italico,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        )
        data = ft.Text(
            item["data"][:5] if mobile else item["data"],
            size=fonte(13), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO,
            width=largura_data, no_wrap=True,
        )
        # No celular tipo e presidente empilham: lado a lado, com a data na
        # frente, os dois ficavam cortados no meio.
        corpo = (
            ft.Column([nome, tipo], spacing=2, tight=True, expand=True)
            if mobile
            else ft.Row(
                [
                    ft.Container(content=tipo, width=max(120, largura - largura_data - 190)),
                    ft.Container(content=nome, expand=True),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return ft.Container(
            content=ft.Row(
                [data, corpo],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            border=None if ultima else ft.Border(bottom=ft.BorderSide(1, BORDA_SUAVE)),
        )

    return [
        ft.Container(
            content=ft.Column(
                [
                    linha(item, indice == len(especiais) - 1)
                    for indice, item in enumerate(especiais)
                ],
                spacing=0,
                tight=True,
            ),
            border=ft.Border.all(1, BORDA_SUAVE),
            border_radius=10,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
    ]


def datas_especiais_com_presidente(ano: int) -> list[dict]:
    """Datas especiais do ano em ordem, já sabendo quais pedem presidente."""
    sem_presidente = tipos_evento_sem_presidente()
    registros = sorted(
        listar_datas_especiais_por_ano(ano).values(),
        key=lambda r: (r["data"][6:10], r["data"][3:5], r["data"][0:2]),
    )
    for registro in registros:
        registro["pede_presidente"] = registro["tipo"] not in sem_presidente
    return registros


def tela_relatorios(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Painel com o retrato do arranjo: o que só aparece somando o ano inteiro.

    Fica dentro do app (o PDF virou só uma opção de exportação): números do
    ano, quem está discursando e presidindo de menos, e o mês a mês da
    cobertura.
    """
    _ = recarregar
    anos = listar_anos_arranjos() or [date.today().year]
    ano_atual = date.today().year
    estado_rel = {"ano": ano_atual if ano_atual in anos else anos[0]}

    def dados_do_ano(ano: int) -> dict:
        minha_cong = obter_id_minha_congregacao()
        recebidos = carregar_recebidos_por_ano(ano)
        presidentes = carregar_presidentes_por_ano(ano)
        especiais = listar_datas_especiais_por_ano(ano)
        contagens = contar_designacoes_por_mes(ano)
        arranjos = sorted({a["mes_inicio"] for a in carregar_arranjos_por_ano(ano)})

        resumo = {
            "semanas": 0, "cobertas": 0, "presidentes": 0,
            "recebidos": 0, "enviados": 0,
            "pendentes": contar_designacoes_por_status(ano).get("pendente", 0),
            "especiais": len(especiais),
            "meses": len(arranjos),
        }
        # Só os meses com arranjo cadastrado: mês sem arranjo é planejamento
        # futuro, não buraco na programação.
        por_mes = []
        for mes_ref in arranjos:
            parcial = _resumo_mes_programacao(
                ano, mes_ref, recebidos, presidentes, contagens, especiais
            )
            for chave in ("semanas", "cobertas", "presidentes", "recebidos", "enviados"):
                resumo[chave] += parcial[chave]
            por_mes.append({"nome": NOMES_MESES[mes_ref], **parcial})

        return {
            "resumo": resumo,
            "meses": por_mes,
            "frequencia": relatorio_frequencia_oradores(
                int(minha_cong) if minha_cong else None
            ),
            "presidencias": relatorio_presidencias(),
            "especiais_lista": datas_especiais_com_presidente(ano),
        }

    area = ft.Column(spacing=16, tight=True)

    def exportar_pdf(_=None):
        from relatorios import secoes_resumo_ano

        ano = estado_rel["ano"]

        def montar_secoes() -> list[dict]:
            dados = dados_do_ano(ano)
            return secoes_resumo_ano(
                dados["resumo"], dados["meses"],
                dados["frequencia"], dados["presidencias"],
                dados["especiais_lista"],
            )

        exportar_relatorio_pdf(
            page, montar_secoes, f"Resumo de {ano}", "Resumo"
        )

    def montar():
        ano = estado_rel["ano"]
        largura = _largura_conteudo_relatorio(page)
        dados = dados_do_ano(ano)
        resumo = dados["resumo"]
        semanas = resumo["semanas"]
        sem_orador = max(0, semanas - resumo["cobertas"])
        sem_presidente = max(0, semanas - resumo["presidentes"])

        cartoes = [
            _cartao_numero_relatorio(
                "Semanas com orador",
                f"{resumo['cobertas']}/{semanas}" if semanas else "—",
                f"{sem_orador} sem orador" if sem_orador else "nenhuma em aberto",
                COR_SUCESSO if not sem_orador else COR_AVISO,
                ft.Icons.RECORD_VOICE_OVER_OUTLINED,
            ),
            _cartao_numero_relatorio(
                "Semanas com presidente",
                f"{resumo['presidentes']}/{semanas}" if semanas else "—",
                f"{sem_presidente} sem presidente" if sem_presidente else "nenhuma em aberto",
                COR_SUCESSO if not sem_presidente else COR_AVISO,
                ft.Icons.PERSON_OUTLINE,
            ),
            _cartao_numero_relatorio(
                "Oradores recebidos",
                str(resumo["recebidos"]),
                f"em {resumo['meses']} mês(es) com arranjo",
                COR_DESTAQUE_CLARA,
                ft.Icons.CALL_RECEIVED,
            ),
            _cartao_numero_relatorio(
                "Designações enviadas",
                str(resumo["enviados"]),
                f"{resumo['pendentes']} aguardando confirmação",
                COR_DESTAQUE_CLARA if not resumo["pendentes"] else COR_AVISO,
                ft.Icons.CALL_MADE,
            ),
        ]
        if eh_mobile():
            grade = ft.Column(
                [ft.Row(cartoes[:2], spacing=10), ft.Row(cartoes[2:], spacing=10)],
                spacing=10,
                tight=True,
            )
        else:
            grade = ft.Row(cartoes, spacing=12)

        itens_freq = [
            {
                "nome": o["nome"],
                "valor": o["quantidade"],
                "detalhe": o["ultima_data"] or "nunca",
            }
            for o in dados["frequencia"]
        ]
        itens_pres = [
            {
                "nome": p["nome"],
                "valor": p["quantidade"],
                "detalhe": p["ultima_data"] or "nunca",
            }
            for p in dados["presidencias"]
        ]

        area.controls = [
            grade,
            _quadro_relatorio(
                f"Mês a mês em {ano}",
                "Onde estão os buracos: semanas com orador e com presidente em "
                "cada mês já montado.",
                _lista_meses_relatorio(dados["meses"], largura),
            ),
            _quadro_relatorio(
                "Oradores da minha congregação",
                "Discursos enviados. De quem discursou menos (e há mais tempo) "
                "para quem discursou mais.",
                _lista_ranking_relatorio(
                    itens_freq, largura, COR_DESTAQUE_CLARA,
                    "Nenhum orador cadastrado na sua congregação.",
                ),
            ),
            _quadro_relatorio(
                "Presidências da reunião",
                "Quantas vezes cada um presidiu, desde o começo. Quem presidiu "
                "menos vem primeiro.",
                _lista_ranking_relatorio(
                    itens_pres, largura, COR_SUCESSO,
                    "Nenhum presidente cadastrado.",
                ),
            ),
            _quadro_relatorio(
                f"Datas especiais em {ano}",
                "Assembleias, congressos, discursos especiais e visitas, com "
                "quem fez a presidência de cada um.",
                _lista_datas_especiais_relatorio(dados["especiais_lista"], largura),
            ),
        ]

    def mudar_ano(e=None):
        estado_rel["ano"] = int(seletor_ano.value)
        montar()
        page.update()

    seletor_ano = ft.Dropdown(
        label="Ano",
        value=str(estado_rel["ano"]),
        options=[ft.dropdown.Option(str(a)) for a in anos],
        width=140,
        border_color=BORDA_SUAVE,
        focused_border_color=COR_DESTAQUE,
    )
    # O Dropdown do Flet 0.86 avisa por on_select (não existe on_change aqui).
    seletor_ano.on_select = mudar_ano
    botao_pdf = ft.OutlinedButton(
        content="Exportar PDF",
        icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
        on_click=exportar_pdf,
    )

    def exportar_tudo(_=None):
        """Junta num PDF só o relatório de todas as telas.

        Um arquivo em vez de cinco: é o que se leva impresso ou se manda pelo
        WhatsApp de uma vez, e no celular não obriga a salvar cinco vezes.
        """
        from relatorios import (
            faixa,
            secoes_congregacoes,
            secoes_oradores,
            secoes_presidentes,
            secoes_programacao,
            secoes_resumo_ano,
            secoes_temas,
        )

        ano = estado_rel["ano"]

        def montar() -> list[dict]:
            dados = dados_do_ano(ano)
            # Cada parte entra atrás da sua tarja: num PDF de vinte páginas,
            # é o que deixa achar onde começa cada assunto.
            secoes: list[dict] = [faixa(f"Resumo de {ano}")]
            secoes += secoes_resumo_ano(
                dados["resumo"], dados["meses"],
                dados["frequencia"], dados["presidencias"],
                dados["especiais_lista"],
            )
            secoes += secoes_programacao(ano)
            secoes.append(faixa("Oradores"))
            secoes += secoes_oradores(carregar_dados(SQL_ORADORES).to_dict("records"))
            secoes.append(faixa("Congregações"))
            secoes += secoes_congregacoes(
                carregar_dados(SQL_CONGREGACOES).to_dict("records")
            )
            secoes.append(faixa("Presidentes da reunião"))
            secoes += secoes_presidentes()
            secoes.append(faixa("Temas"))
            secoes += secoes_temas()
            return secoes

        exportar_relatorio_pdf(
            page, montar, f"Relatório completo de {ano}", "Relatorio_Completo"
        )

    botao_tudo = ft.FilledButton(
        content="Gerar todos",
        icon=ft.Icons.LIBRARY_BOOKS_OUTLINED,
        tooltip="Um PDF com programação, oradores, congregações, presidentes e temas",
        on_click=exportar_tudo,
    )

    montar()
    controles_topo = (
        ft.Row([seletor_ano, botao_pdf, botao_tudo], spacing=10, wrap=True,
               vertical_alignment=ft.CrossAxisAlignment.CENTER)
        if eh_mobile()
        else ft.Row(
            [seletor_ano, ft.Container(expand=True), botao_pdf, botao_tudo],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Relatórios",
                "O retrato do arranjo: o que só aparece somando o ano inteiro.",
            ),
            ft.Container(height=12),
            controles_topo,
            ft.Container(height=16),
            ft.Column([area], expand=True, scroll=ft.ScrollMode.AUTO),
        ],
        spacing=0,
        expand=True,
    )


def _texto_de_confirmacao(base: str, aviso: str) -> ft.Control:
    """Corpo do diálogo de restauração, com o alerta em destaque quando existe."""
    linhas: list[ft.Control] = [ft.Text(base, size=fonte(13))]
    if aviso:
        linhas.append(ft.Container(height=10))
        linhas.append(
            ft.Text(aviso, size=fonte(13), color=COR_AVISO, weight=ft.FontWeight.W_600)
        )
    return ft.Column(linhas, tight=True, spacing=0)


def _linha_ultimo_envio(iso: str) -> ft.Control:
    """Quando o backup subiu pela última vez.

    Sem isso, um envio automático que parou de funcionar só aparece no dia em
    que o backup faz falta.
    """
    texto, nivel = descrever_ultimo_envio(iso)
    cor = COR_AVISO if nivel == "atencao" else TEXTO_SECUNDARIO
    return ft.Row(
        [
            ft.Icon(ft.Icons.SCHEDULE, size=fonte(14), color=cor),
            ft.Text(texto, size=fonte(12), color=cor, expand=True),
        ],
        spacing=6,
    )


def _cabecalho_card_ajustes(icone: str, titulo: str, descricao: str) -> ft.Control:
    """Título de um card de Ajustes: ícone, nome e uma linha do que ele faz.

    A tela é uma pilha de cards parecidos; o ícone é o que deixa achar o certo
    sem ler tudo.
    """
    return ft.Row(
        [
            ft.Container(
                content=ft.Icon(icone, size=fonte(18), color=COR_DESTAQUE),
                bgcolor=ft.Colors.with_opacity(0.12, COR_DESTAQUE),
                border_radius=10,
                padding=8,
            ),
            ft.Column(
                [
                    ft.Text(titulo, size=fonte(16), weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO),
                    ft.Text(descricao, size=fonte(12), color=TEXTO_SECUNDARIO),
                ],
                spacing=2,
                tight=True,
                expand=True,
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _secao_dados_congregacao(page: ft.Page) -> ft.Control:
    """Card com os dados da congregação (nome, endereço, reunião, coordenador).

    Vive na tela Minha congregação. Ficava em Ajustes, misturado com backup
    e preferências — coisas de manutenção, não o cadastro do dia a dia.
    """
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
    campo_telefone = _campo_telefone(
        "Telefone do coordenador", config["telefone_coordenador"], expand=True
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
        size=fonte(13),
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

    # Linha do tempo do dia de reunião: a congregação muda de dia de tempos em
    # tempos, e os meses antigos precisam ser montados no dia que valia neles.
    lista_periodos = ft.Column(spacing=0, tight=True)
    campo_inicio = ft.TextField(label="A partir de", hint_text="MM/AAAA", expand=True)
    campo_novo_dia = ft.TextField(label="Dia", hint_text="Ex: Domingo", expand=True)
    erro_periodo = ft.Text("", size=fonte(12), color=COR_ERRO, visible=False)

    def montar_periodos():
        periodos = listar_reuniao_historico()
        if not periodos:
            lista_periodos.controls = [
                ft.Text("Sem mudanças registradas: vale o dia acima em todos os meses.",
                        size=fonte(12), color=TEXTO_SECUNDARIO, italic=True)
            ]
            return

        def linha(item, ultima):
            def remover(_=None, inicio=item["inicio"]):
                excluir_reuniao_historico(inicio)
                montar_periodos()
                page.update()

            mes, ano = item["inicio"][5:7], item["inicio"][0:4]
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Text(f"{mes}/{ano}", size=fonte(13), width=76,
                                weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO),
                        ft.Text(item["dia_semana"], size=fonte(13),
                                color=TEXTO_SECUNDARIO, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE, icon_size=fonte(17),
                            icon_color=COR_ERRO, tooltip="Remover este período",
                            on_click=remover,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=2),
                border=None if ultima else ft.Border(bottom=ft.BorderSide(1, BORDA_SUAVE)),
            )

        lista_periodos.controls = [
            linha(item, i == len(periodos) - 1) for i, item in enumerate(periodos)
        ]

    def adicionar_periodo(_=None):
        texto = (campo_inicio.value or "").strip()
        dia = (campo_novo_dia.value or "").strip()
        casou = re.fullmatch(r"(\d{1,2})/(\d{4})", texto)
        if not casou or not 1 <= int(casou.group(1)) <= 12:
            erro_periodo.value = "Informe o mês no formato MM/AAAA."
            erro_periodo.visible = True
            page.update()
            return
        if _dia_semana_para_weekday(dia) is None:
            erro_periodo.value = "Informe um dia da semana (ex: Domingo)."
            erro_periodo.visible = True
            page.update()
            return
        salvar_reuniao_historico(f"{int(casou.group(2)):04d}-{int(casou.group(1)):02d}", dia)
        campo_inicio.value = ""
        campo_novo_dia.value = ""
        erro_periodo.visible = False
        montar_periodos()
        page.update()

    montar_periodos()

    formulario = ft.Container(
        content=ft.Column(
            [
                _cabecalho_card_ajustes(
                    ft.Icons.HOME_WORK_OUTLINED,
                    "Minha congregação",
                    "Dados usados nos cabeçalhos dos PDFs e nas exportações.",
                ),
                ft.Container(height=12),
                campo_nome,
                campo_endereco,
                linha_campos(campo_cidade, campo_cep),
                linha_campos(campo_coordenador, campo_telefone),
                linha_campos(campo_dia, campo_horario),
                campo_circuito,
                ft.Container(height=8),
                criar_secao_titulo("Quando o dia da reunião mudou"),
                ft.Text(
                    "A Programação monta cada mês no dia que valia nele. O dia "
                    "acima vale do último período em diante.",
                    size=fonte(12), color=TEXTO_SECUNDARIO,
                ),
                ft.Container(
                    content=lista_periodos,
                    border=ft.Border.all(1, BORDA_SUAVE),
                    border_radius=10,
                    padding=ft.Padding.symmetric(vertical=6),
                ),
                linha_campos(campo_inicio, campo_novo_dia),
                ft.Row(
                    [
                        ft.OutlinedButton("Adicionar período", icon=ft.Icons.ADD,
                                          on_click=adicionar_periodo),
                        erro_periodo,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
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
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=16,
            tight=True,
        ),
        padding=16 if eh_mobile() else 28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=_largura_dialog(page, 560),
    )

    return formulario


def tela_ajustes(
    page: ft.Page,
    recarregar: Callable[[], None],
    file_picker: ft.FilePicker,
) -> ft.Control:
    """Backup, nuvem, carga por planilha e preferências do aplicativo."""
    def exportar_backup_click(_=None):
        try:
            caminho, contagens = exportar_backup()
        except Exception as exc:
            logger.exception("Falha ao exportar backup")
            mostrar_aviso(page, "Erro ao exportar", f"Não foi possível gerar o backup: {exc}")
            return

        def fechar(_=None):
            page.pop_dialog()

        def abrir_pasta(_=None):
            entregar_arquivo(page, caminho, abrir_pasta_do_arquivo)
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
                    "Ele pode ser restaurado neste aplicativo, no computador "
                    "ou no celular.",
                    size=fonte(13),
                ),
                actions=[
                    ft.TextButton("Fechar", on_click=fechar),
                    ft.FilledButton(_rotulo_entrega(), icon=_icone_entrega(), on_click=abrir_pasta),
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

        resumo = resumo_backup(caminho)
        aviso = aviso_backup_antigo(
            resumo["gerado_em"], alterado_em_local(), resumo["aparelho"]
        )
        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Restaurar backup"),
                content=_texto_de_confirmacao(
                    "Os dados atuais serão substituídos pelos do arquivo selecionado.\n"
                    "Uma cópia de segurança do estado atual será salva antes.\n\n"
                    "Deseja continuar?",
                    aviso,
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
            caminho = executar_com_progresso(
                page, "Gerando planilha...", gerar_planilha_modelo
            )
        except Exception as exc:
            logger.exception("Falha ao gerar a planilha-modelo")
            mostrar_aviso(page, "Erro ao gerar", f"Não foi possível criar a planilha: {exc}")
            return

        def fechar(_=None):
            page.pop_dialog()

        def abrir_pasta(_=None):
            entregar_arquivo(page, caminho, abrir_pasta_do_arquivo)
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
                    size=fonte(13),
                ),
                actions=[
                    ft.TextButton("Fechar", on_click=fechar),
                    ft.FilledButton(_rotulo_entrega(), icon=_icone_entrega(), on_click=abrir_pasta),
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
            resumo = executar_com_progresso(
                page,
                "Importando planilha...",
                lambda: importar_planilha_dados(arquivos[0].path),
            )
        except Exception as exc:
            logger.exception("Falha ao importar a planilha")
            mostrar_aviso(page, "Não foi possível importar", str(exc))
            return
        recarregar()
        mostrar_aviso(page, "Planilha importada", _resumir_importacao_planilha(resumo))

    def abrir_importar_planilha(_=None):
        page.run_task(importar_planilha_click)

    secao_planilha = ft.Container(
        content=ft.Column(
            [
                _cabecalho_card_ajustes(
                    ft.Icons.TABLE_VIEW_OUTLINED,
                    "Carga inicial por planilha",
                    "Cadastrar muita gente de uma vez, por Excel.",
                ),
                ft.Container(height=4),
                ft.Text(
                    "Cadastre congregações, oradores e presidentes de uma vez por "
                    "planilha. A importação só adiciona; nada é apagado. Os temas "
                    "vêm dos formulários S-99/S-99a, na aba Temas.",
                    size=fonte(13),
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
                    wrap=True,
                ),
            ],
            spacing=0,
            tight=True,
        ),
        padding=16 if eh_mobile() else 28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=_largura_dialog(page, 560),
    )

    secao_backup = ft.Container(
        content=ft.Column(
            [
                _cabecalho_card_ajustes(
                    ft.Icons.SAVE_OUTLINED,
                    "Backup dos dados",
                    "Copiar tudo para um arquivo e restaurar quando precisar.",
                ),
                ft.Container(height=4),
                ft.Text(
                    "Salve todos os seus dados num arquivo, para guardar em outro "
                    "lugar ou levar para outro aparelho.",
                    size=fonte(13),
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
                    wrap=True,
                ),
            ],
            spacing=0,
            tight=True,
        ),
        padding=16 if eh_mobile() else 28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=_largura_dialog(page, 560),
    )

    # ---------------------------------------------------------------
    # Backup na nuvem (Google Drive)
    # ---------------------------------------------------------------
    cred_nuvem = nuvem_drive.carregar_credenciais()
    conectado_nuvem = nuvem_drive.esta_conectado(cred_nuvem)

    campo_client_id = ft.TextField(
        label="Client ID",
        value=cred_nuvem.get("client_id", ""),
        hint_text="123...apps.googleusercontent.com",
        expand=True,
    )
    campo_client_secret = ft.TextField(
        label="Client Secret",
        value=cred_nuvem.get("client_secret", ""),
        password=True,
        can_reveal_password=True,
        expand=True,
    )

    def salvar_credenciais_nuvem(_=None):
        dados = nuvem_drive.carregar_credenciais()
        dados["client_id"] = (campo_client_id.value or "").strip()
        dados["client_secret"] = (campo_client_secret.value or "").strip()
        nuvem_drive.salvar_credenciais(dados)
        mostrar_sucesso(page, "Credenciais salvas.")
        recarregar()

    def concluir_login_colado(texto: str, ao_terminar: Callable[[], None]) -> bool:
        """Troca por tokens o código que veio no endereço colado pelo usuário.

        Usa o PKCE salvo em ``login_pendente``, então funciona mesmo depois de
        o Android ter encerrado o aplicativo — é o resgate do login em que o
        navegador ficou em "não é possível acessar esse site" (o servidor local
        do app morreu, mas o código continua no endereço).
        """
        pendente = nuvem_drive.carregar_login_pendente()
        try:
            codigo = nuvem_drive.extrair_codigo(texto)
            obtidas = executar_com_progresso(
                page,
                "Concluindo o login...",
                lambda: nuvem_drive.trocar_codigo_com_retentativa(
                    pendente.get("client_id", ""),
                    pendente.get("client_secret", ""),
                    codigo,
                    pendente.get("redirect_uri", ""),
                    pendente.get("verificador", ""),
                    tentativas=3,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao concluir o login colado")
            mostrar_aviso(page, "Não foi possível concluir", str(exc))
            return False
        dados = nuvem_drive.carregar_credenciais()
        dados.update(obtidas)
        dados["client_id"] = pendente.get("client_id", "")
        dados["client_secret"] = pendente.get("client_secret", "")
        nuvem_drive.salvar_credenciais(dados)
        nuvem_drive.limpar_login_pendente()
        ao_terminar()
        mostrar_sucesso(page, "Conectado ao Google Drive.")
        recarregar()
        return True

    def _campo_colar_endereco() -> ft.TextField:
        return ft.TextField(
            label="Cole aqui o endereço do navegador",
            hint_text="http://127.0.0.1:.../?code=...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=3,
        )

    def abrir_dialog_login_pendente(_=None):
        """Retoma um login interrompido: o usuário cola o endereço de retorno."""
        campo = _campo_colar_endereco()

        def fechar(_=None):
            page.pop_dialog()

        def concluir(_=None):
            concluir_login_colado(campo.value or "", fechar)

        def descartar(_=None):
            nuvem_drive.limpar_login_pendente()
            fechar()
            recarregar()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Concluir o login do Google"),
                content=ft.Container(
                    width=_largura_dialog(page, 420),
                    content=ft.Column(
                        [
                            ft.Text(
                                "Se o navegador mostrou \"não é possível acessar "
                                "esse site\" (127.0.0.1), está tudo bem: o código "
                                "do login ficou no endereço.",
                                size=fonte(13),
                            ),
                            ft.Container(height=6),
                            ft.Text(
                                "Volte ao navegador, toque na barra de endereço, "
                                "copie o endereço inteiro e cole abaixo.",
                                size=fonte(13),
                                color=TEXTO_SECUNDARIO,
                            ),
                            ft.Container(height=10),
                            campo,
                        ],
                        spacing=0,
                        tight=True,
                    ),
                ),
                actions=[
                    ft.TextButton("Descartar", on_click=descartar),
                    ft.TextButton("Fechar", on_click=fechar),
                    ft.FilledButton(
                        "Concluir login", icon=ft.Icons.CHECK, on_click=concluir
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )
        page.update()

    def conectar_pelo_navegador(client_id: str, client_secret: str):
        """Abre o navegador e recebe o retorno automaticamente (loopback + PKCE).

        Vale para PC e celular: o app sobe um servidor em 127.0.0.1 e o
        navegador do próprio aparelho devolve o código para ele.
        """
        servidor = nuvem_drive.ServidorRetorno()
        servidor.__enter__()
        verificador, desafio = nuvem_drive._gerar_pkce()
        url = nuvem_drive.montar_url_autorizacao(
            client_id, servidor.url_redirecionamento, desafio
        )
        # O Android pode encerrar o app enquanto o navegador está aberto; com o
        # PKCE salvo, dá para concluir depois colando o endereço de retorno.
        nuvem_drive.salvar_login_pendente(
            {
                "verificador": verificador,
                "redirect_uri": servidor.url_redirecionamento,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        abrir_url(page, url)

        estado_login = {"cancelado": False}

        def cancelar(_=None):
            estado_login["cancelado"] = True
            servidor.encerrar()
            page.pop_dialog()

        # No celular, o app pode ser encerrado (ou congelado) enquanto o
        # navegador está aberto e o retorno automático se perde — o navegador
        # mostra "não é possível acessar esse site". Aí o usuário cola o
        # endereço que ficou na barra, que contém o código.
        campo_colar = _campo_colar_endereco()
        campo_colar.label = "Ou cole aqui o endereço do navegador"

        def encerrar_espera():
            estado_login["cancelado"] = True  # encerra a espera do servidor
            servidor.encerrar()
            page.pop_dialog()

        def concluir_colando(_=None):
            concluir_login_colado(campo_colar.value or "", encerrar_espera)

        campos_colar = (
            [
                ft.Container(height=4),
                ft.Text(
                    "Deu \"não é possível acessar esse site\"? É normal — copie "
                    "o endereço da barra do navegador e cole abaixo.",
                    size=fonte(12),
                    color=TEXTO_SECUNDARIO,
                ),
                campo_colar,
                ft.FilledButton(
                    "Concluir login", icon=ft.Icons.CHECK, on_click=concluir_colando
                ),
            ]
            if eh_mobile()
            else []
        )

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Entrar com o Google"),
                content=ft.Container(
                    width=_largura_dialog(page, 420),
                    content=ft.Column(
                        [
                            ft.Text(
                                "Abrimos o navegador para você entrar na sua conta "
                                "do Google e autorizar o aplicativo.",
                                size=fonte(13),
                            ),
                            ft.Container(height=8),
                            ft.Row(
                                [
                                    ft.ProgressRing(width=16, height=16, stroke_width=2),
                                    ft.Text("Aguardando…", size=fonte(12),
                                            color=TEXTO_SECUNDARIO),
                                ],
                                spacing=10,
                            ),
                            ft.Container(height=8),
                            ft.TextButton(
                                "Não abriu? Clique aqui",
                                icon=ft.Icons.OPEN_IN_NEW,
                                on_click=lambda _: abrir_url(page, url),
                            ),
                            *campos_colar,
                        ],
                        spacing=4,
                        tight=True,
                    ),
                ),
                actions=[ft.TextButton("Cancelar", on_click=cancelar)],
            )
        )
        page.update()

        async def aguardar_navegador():
            import asyncio

            try:
                codigo = await asyncio.to_thread(servidor.aguardar_codigo, 300)
                # No celular o código chega enquanto o app está em segundo
                # plano, sem DNS: a troca insiste até o usuário voltar ao app.
                obtidas = await asyncio.to_thread(
                    nuvem_drive.trocar_codigo_com_retentativa,
                    client_id, client_secret, codigo,
                    servidor.url_redirecionamento, verificador,
                )
            except Exception as exc:  # noqa: BLE001
                if estado_login["cancelado"]:
                    return
                logger.exception("Falha no login pelo navegador")
                page.pop_dialog()
                mostrar_aviso(page, "Não foi possível conectar", str(exc))
                return
            finally:
                servidor.encerrar()
            if estado_login["cancelado"]:
                return
            dados = nuvem_drive.carregar_credenciais()
            dados.update(obtidas)
            dados["client_id"], dados["client_secret"] = client_id, client_secret
            nuvem_drive.salvar_credenciais(dados)
            page.pop_dialog()
            mostrar_sucesso(page, "Conectado ao Google Drive.")
            recarregar()

        page.run_task(aguardar_navegador)

    def conectar_nuvem(_=None):
        """Conecta ao Drive pelo navegador (mesmo fluxo no PC e no celular)."""
        salvas = nuvem_drive.carregar_credenciais()
        client_id, client_secret = nuvem_drive.credenciais_efetivas(eh_mobile(), salvas)
        if not client_id or not client_secret:
            mostrar_aviso(
                page,
                "Faltam as credenciais",
                "Esta versão foi compilada sem as credenciais do Google. "
                "Informe as suas em \"Usar minhas credenciais\" — o passo a "
                "passo está no README do projeto.",
            )
            return

        conectar_pelo_navegador(client_id, client_secret)

    def enviar_para_nuvem(_=None):
        try:
            def tarefa():
                caminho, _ = exportar_backup()
                dados = nuvem_drive.carregar_credenciais()
                token = nuvem_drive.obter_access_token(dados)
                return nuvem_drive.enviar_backup(token, caminho)

            executar_com_progresso(page, "Enviando para o Google Drive...", tarefa)
            nuvem_drive.registrar_envio()
            mostrar_sucesso(page, "Backup enviado para o Google Drive.")
            recarregar()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao enviar backup para o Drive")
            mostrar_aviso(page, "Não foi possível enviar", str(exc))

    def restaurar_da_nuvem(_=None):
        """Baixa o backup mais recente da nuvem e restaura (com confirmação)."""
        try:
            def buscar():
                dados = nuvem_drive.carregar_credenciais()
                token = nuvem_drive.obter_access_token(dados)
                return token, nuvem_drive.listar_backups(token)

            token, arquivos = executar_com_progresso(
                page, "Consultando o Google Drive...", buscar
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao listar backups do Drive")
            mostrar_aviso(page, "Não foi possível consultar", str(exc))
            return

        mais_novo = nuvem_drive.escolher_mais_novo(arquivos)
        if not mais_novo:
            mostrar_aviso(page, "Nenhum backup na nuvem",
                          "Envie um backup a partir de outro aparelho primeiro.")
            return

        quando = formatar_data_hora_sao_paulo(mais_novo.get("modifiedTime"))

        def confirmar(_=None):
            page.pop_dialog()
            try:
                def tarefa():
                    conteudo = nuvem_drive.baixar_backup(token, mais_novo["id"])
                    from armazenamento import BACKUPS_DIR

                    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
                    destino = BACKUPS_DIR / f"nuvem_{mais_novo.get('name', 'backup.json')}"
                    destino.write_bytes(conteudo)
                    return restaurar_backup(destino)

                ok, mensagem = executar_com_progresso(
                    page, "Restaurando da nuvem...", tarefa
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Falha ao restaurar backup da nuvem")
                mostrar_aviso(page, "Não foi possível restaurar", str(exc))
                return
            if not ok:
                mostrar_aviso(page, "Não foi possível restaurar", mensagem)
                return
            mostrar_sucesso(page, "Dados restaurados da nuvem.")
            recarregar()

        aviso = aviso_backup_antigo(mais_novo.get("modifiedTime"), alterado_em_local())
        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Restaurar da nuvem?"),
                content=_texto_de_confirmacao(
                    f"O backup mais recente da nuvem é de {quando} (horário de Brasília).\n\n"
                    "Os dados atuais deste aparelho serão SUBSTITUÍDOS. Uma cópia "
                    "de segurança do estado atual é salva antes, na pasta de backups.",
                    aviso,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: page.pop_dialog()),
                    ft.FilledButton("Restaurar", icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
                                    on_click=confirmar),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def desconectar_nuvem(_=None):
        nuvem_drive.esquecer_credenciais()
        mostrar_sucesso(page, "Desconectado. Os backups na nuvem continuam lá.")
        recarregar()

    if conectado_nuvem:
        controles_nuvem = [
            ft.Row(
                [
                    ft.Icon(ft.Icons.CLOUD_DONE, color=COR_SUCESSO, size=fonte(18)),
                    ft.Text("Conectado ao Google Drive", size=fonte(13),
                            color=COR_SUCESSO, weight=ft.FontWeight.W_600),
                ],
                spacing=8,
            ),
            ft.Container(height=6),
            _linha_ultimo_envio(nuvem_drive.ultimo_envio(cred_nuvem)),
            ft.Container(height=10),
            ft.Row(
                [
                    ft.FilledButton("Enviar backup agora",
                                    icon=ft.Icons.CLOUD_UPLOAD_OUTLINED,
                                    on_click=enviar_para_nuvem),
                    ft.OutlinedButton("Restaurar da nuvem",
                                      icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
                                      on_click=restaurar_da_nuvem),
                    ft.TextButton("Desconectar", on_click=desconectar_nuvem),
                ],
                spacing=12,
                wrap=True,
            ),
        ]
    else:
        tem_credenciais = nuvem_drive.ha_credenciais(eh_mobile(), cred_nuvem)
        area_avancado = ft.Column(
            [
                ft.Container(height=10),
                campo_client_id,
                ft.Container(height=8),
                campo_client_secret,
                ft.Container(height=10),
                ft.OutlinedButton("Salvar credenciais", icon=ft.Icons.SAVE,
                                  on_click=salvar_credenciais_nuvem),
            ],
            spacing=0,
            tight=True,
            visible=not tem_credenciais,
        )

        def alternar_avancado(_=None):
            area_avancado.visible = not area_avancado.visible
            page.update()

        # Login interrompido (o Android congelou o app e o navegador não
        # conseguiu devolver o código): oferece concluir colando o endereço.
        aviso_pendente = (
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.INFO_OUTLINE, color=COR_AVISO,
                                            size=fonte(18)),
                                    ft.Text(
                                        "Login começado e não concluído",
                                        size=fonte(13),
                                        color=COR_AVISO,
                                        weight=ft.FontWeight.W_600,
                                        expand=True,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Container(height=6),
                            ft.Text(
                                "O navegador mostrou \"não é possível acessar esse "
                                "site\"? O código do login ficou no endereço — dá "
                                "para terminar sem começar de novo.",
                                size=fonte(12),
                                color=TEXTO_SECUNDARIO,
                            ),
                            ft.Container(height=8),
                            ft.FilledButton(
                                "Concluir colando o endereço",
                                icon=ft.Icons.CONTENT_PASTE_GO,
                                on_click=abrir_dialog_login_pendente,
                            ),
                        ],
                        spacing=0,
                        tight=True,
                    ),
                    padding=12,
                    bgcolor=ft.Colors.with_opacity(0.10, COR_AVISO),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, COR_AVISO)),
                    border_radius=10,
                ),
                ft.Container(height=12),
            ]
            if nuvem_drive.login_pendente_valido()
            else []
        )

        controles_nuvem = [
            ft.Text(
                "Guarde o backup na sua conta do Google e restaure em outro "
                "aparelho. O aplicativo só enxerga a pasta dele mesmo no Drive, "
                "nunca o restante dos seus arquivos.",
                size=fonte(13),
                color=TEXTO_SECUNDARIO,
            ),
            ft.Container(height=12),
            *aviso_pendente,
            ft.FilledButton(
                "Entrar com o Google",
                icon=ft.Icons.CLOUD_SYNC_OUTLINED,
                on_click=conectar_nuvem,
            ),
            ft.Container(height=4),
            ft.TextButton(
                "Usar minhas credenciais (avançado)",
                icon=ft.Icons.KEY_OUTLINED,
                on_click=alternar_avancado,
            ),
            area_avancado,
        ]

    secao_nuvem = ft.Container(
        content=ft.Column(
            [
                _cabecalho_card_ajustes(
                    ft.Icons.CLOUD_OUTLINED,
                    "Backup na nuvem",
                    "Guardar o backup na sua conta do Google e restaurar em outro aparelho.",
                ),
                ft.Container(height=8),
                *controles_nuvem,
            ],
            spacing=0,
            tight=True,
        ),
        padding=16 if eh_mobile() else 28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=_largura_dialog(page, 560),
    )

    def mudar_escala(e=None):
        """Aplica e salva a escala de fonte, remontando a tela."""
        try:
            nova = float(seletor_escala.value)
        except (TypeError, ValueError):
            nova = 1.0
        _tema.definir_escala(nova)
        salvar_escala_fonte(_tema.escala_atual())
        recarregar()

    seletor_escala = ft.Dropdown(
        label="Tamanho do texto",
        width=None if eh_mobile() else 220,
        value=f"{_tema.escala_atual():.2f}",
        options=[
            ft.dropdown.Option(key="0.90", text="Pequeno (90%)"),
            ft.dropdown.Option(key="1.00", text="Padrão (100%)"),
            ft.dropdown.Option(key="1.15", text="Grande (115%)"),
            ft.dropdown.Option(key="1.30", text="Maior (130%)"),
            ft.dropdown.Option(key="1.45", text="Muito grande (145%)"),
        ],
        border_color=BORDA_SUAVE,
        focused_border_color=COR_DESTAQUE,
    )
    seletor_escala.on_select = mudar_escala

    secao_acessibilidade = ft.Container(
        content=ft.Column(
            [
                _cabecalho_card_ajustes(
                    ft.Icons.TEXT_FIELDS,
                    "Acessibilidade",
                    "Tamanho do texto em todo o aplicativo.",
                ),
                ft.Container(height=4),
                ft.Text(
                    "Aumente o texto do aplicativo inteiro. As colunas das tabelas "
                    "acompanham o tamanho escolhido.",
                    size=fonte(13),
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Container(height=12),
                seletor_escala,
            ],
            spacing=0,
            tight=True,
        ),
        padding=16 if eh_mobile() else 28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=_largura_dialog(page, 560),
    )

    secao_atualizacao = ft.Container(
        content=ft.Column(
            [
                _cabecalho_card_ajustes(
                    ft.Icons.SYSTEM_UPDATE,
                    "Atualizações",
                    f"Versão instalada: {VERSAO_APP}.",
                ),
                ft.Container(height=4),
                ft.Text(
                    "Procura a última versão publicada e baixa o arquivo certo "
                    "para este aparelho. A atualização instala por cima: os "
                    "dados, os backups e as preferências continuam onde estão."
                    if eh_mobile()
                    else "Procura a última versão publicada, baixa o instalador "
                    "e o abre. Os dados, os backups e as preferências "
                    "continuam onde estão.",
                    size=fonte(13),
                    color=TEXTO_SECUNDARIO,
                ),
                ft.Container(height=12),
                ft.FilledButton(
                    "Buscar atualizações",
                    icon=ft.Icons.SYSTEM_UPDATE,
                    on_click=lambda _: verificar_agora(page),
                ),
            ],
            spacing=0,
            tight=True,
        ),
        padding=16 if eh_mobile() else 28,
        bgcolor=FUNDO_CARD,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(),
        width=_largura_dialog(page, 560),
    )

    return ft.Column(
        [
            criar_cabecalho_tela(
                "Ajustes",
                "Dados da congregação, backup e preferências",
            ),
            ft.Container(height=12 if eh_mobile() else 24),
            # Ordem: proteger os dados → começar do zero → preferências
            # (mexidas uma vez só, ficam por último). Os dados da
            # congregação saíram daqui para a tela Minha congregação.
            secao_backup,
            ft.Container(height=24),
            secao_nuvem,
            ft.Container(height=24),
            secao_planilha,
            ft.Container(height=24),
            secao_acessibilidade,
            ft.Container(height=24),
            secao_atualizacao,
        ],
        spacing=0,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        # No celular os cards têm largura fixa; centralizar deixa as margens
        # iguais dos dois lados.
        horizontal_alignment=ft.CrossAxisAlignment.CENTER if eh_mobile() else ft.CrossAxisAlignment.START,
    )


def _preview_quadro_mobile(
    ano: int, mes: int, dados: list[dict], nome_congregacao: str
) -> ft.Control:
    """Prévia do quadro em componentes nativos do Flet (texto grande e legível
    no celular). A imagem/PDF fiéis continuam disponíveis em "Exportar PDF" —
    aqui o objetivo é só conseguir LER quem está designado em cada semana, algo
    impossível encaixando a tabela larga do PDF na largura de um celular.
    """
    # Mesmas cores e estrutura do PDF/imagem (gerar_preview_quadro_mes): faixas
    # vermelha/cinza com texto PRETO, Data e Presidente lado a lado, e a grade
    # preta aparecendo nos vãos de 1px entre as células.
    COR_RED = "#C84040"
    COR_GRAY = "#757070"
    BRANCO = "#FFFFFF"
    PRETO = "#000000"
    GRADE = "#000000"

    def faixa(texto: str, cor: str, tamanho: int = 13):
        return ft.Container(
            content=ft.Text(
                texto, size=tamanho, weight=ft.FontWeight.W_700,
                color=PRETO, text_align=ft.TextAlign.CENTER,
            ),
            bgcolor=cor,
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
            alignment=ft.Alignment.CENTER,
        )

    def linha_data_presidente(rotulo_data: str, presidente: str):
        # Data (vermelho) à esquerda e Presidente (cinza) à direita, ~50/50,
        # exatamente como a primeira linha de cada semana no PDF.
        texto_pres = f"PRESIDENTE:  {presidente}" if presidente else "PRESIDENTE:"
        # Altura fixa nas duas células para elas ficarem do mesmo tamanho SEM
        # usar CrossAxisAlignment.STRETCH (que, num Row dentro de coluna
        # rolável, gera erro de layout e deixa a prévia em branco). Presidente
        # em até 2 linhas para o nome não ser cortado na metade da largura.
        return ft.Row(
            [
                ft.Container(
                    content=ft.Text(
                        rotulo_data, size=fonte(12), weight=ft.FontWeight.W_700,
                        color=PRETO, text_align=ft.TextAlign.CENTER,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    bgcolor=COR_RED, alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(horizontal=6),
                    height=54, expand=True,
                ),
                ft.Container(
                    content=ft.Text(
                        texto_pres, size=fonte(12), weight=ft.FontWeight.W_600, color=PRETO,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    bgcolor=COR_GRAY, alignment=ft.Alignment.CENTER_LEFT,
                    padding=ft.Padding.symmetric(horizontal=8),
                    height=54, expand=True,
                ),
            ],
            spacing=1,
            tight=True,
        )

    def linha_campo(rotulo: str, valor: str):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(rotulo, size=fonte(13), weight=ft.FontWeight.W_700, color=PRETO,
                            width=110),
                    ft.Text(valor or "", size=fonte(14), color=PRETO, expand=True),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=BRANCO,
            padding=ft.Padding.symmetric(horizontal=10, vertical=9),
        )

    itens: list[ft.Control] = [
        faixa(f"Conferência Pública - {nome_congregacao}", COR_RED, tamanho=14),
        faixa(f"{NOMES_MESES[mes]}/{ano}", COR_GRAY, tamanho=13),
    ]
    for indice, item in enumerate(dados):
        data = item.get("data")
        dia = data.day if hasattr(data, "day") else ""
        presidente = item.get("presidente") or ""
        itens.append(
            linha_data_presidente(f"SÁBADO, {dia} DE {NOMES_MESES[mes].upper()}", presidente)
        )
        itens.append(linha_campo("Orador:", item.get("orador")))
        itens.append(linha_campo("Tema:", item.get("tema")))
        itens.append(linha_campo("Congregação:", item.get("congregacao")))
        if indice < len(dados) - 1:
            # Faixa cinza separando as semanas, como no PDF.
            itens.append(ft.Container(bgcolor=COR_GRAY, height=10))

    return ft.Container(
        content=ft.Column(itens, spacing=1, tight=True),
        bgcolor=GRADE,
        border=ft.Border.all(1, GRADE),
        border_radius=6,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        margin=ft.Margin.only(bottom=16),
    )


def tela_quadro_anuncios(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Prévia e exportação do quadro de anúncios (publicado de 2 em 2 meses)."""
    hoje = date.today()
    anos_disponiveis = {opcao.key for opcao in _opcoes_anos_arranjos()}
    estado = {
        "ano": hoje.year if str(hoje.year) in anos_disponiveis else ANO_PADRAO_ARRANJOS,
        "mes_inicial": par_meses_do_mes_quadro(hoje.month)[0],
        # Prévia do PC: qual dos dois meses está na tela e o zoom aplicado.
        "mes_preview": par_meses_do_mes_quadro(hoje.month)[0],
        "zoom": 1.0,
    }
    area_preview = ft.Container(expand=True)
    rotulo_zoom = ft.Text("100%", size=fonte(12), color=TEXTO_SECUNDARIO, width=46,
                          text_align=ft.TextAlign.CENTER)
    rotulo_mes_preview = ft.Text("", size=fonte(13), weight=ft.FontWeight.W_600,
                                 color=TEXTO_PRIMARIO)

    opcoes_pares = [
        ft.dropdown.Option(
            key=str(inicio),
            text=f"{NOMES_MESES[inicio]}-{NOMES_MESES[fim]}",
        )
        for inicio, fim in PARES_MESES_QUADRO
    ]

    def aplicar_zoom(novo: float, atualizar_tela: bool = True):
        estado["zoom"] = max(ZOOM_PREVIEW_MIN, min(ZOOM_PREVIEW_MAX, round(novo, 2)))
        if atualizar_tela:
            montar_preview()
            page.update()

    def ao_rolar_preview(e):
        """Ctrl + roda do mouse sobre a prévia: para cima amplia, para baixo reduz.

        Sem Ctrl, ignora — deixando a rolagem normal da página. O Ctrl é
        consultado no sistema (ver _ctrl_pressionado), pois o ScrollEvent não
        traz modificadores.
        """
        if not _ctrl_pressionado():
            return
        delta = getattr(getattr(e, "scroll_delta", None), "y", 0) or 0
        if not delta:
            return
        aplicar_zoom(estado["zoom"] * (0.9 if delta > 0 else 1.1))

    def mudar_mes_preview(delta: int):
        inicio = estado["mes_inicial"]
        estado["mes_preview"] = inicio if estado["mes_preview"] != inicio else inicio + 1
        _ = delta
        montar_preview()
        page.update()

    def montar_preview():
        config = carregar_configuracao()
        nome_congregacao = config.get("nome_congregacao") or "Minha congregação"
        inicio = estado["mes_inicial"]
        blocos = []
        mobile = eh_mobile()
        if mobile:
            blocos.append(
                ft.Text(
                    "Prévia dos dois meses. O PDF exportado tem o layout de impressão.",
                    size=fonte(12), color=TEXTO_SECUNDARIO, italic=True,
                )
            )
        if mobile:
            for mes in (inicio, inicio + 1):
                dados = carregar_dados_mes_quadro(estado["ano"], mes)
                # No celular a tabela larga do PDF fica ilegível ao encaixar na
                # largura da tela. Mostramos a prévia com componentes nativos
                # (texto grande de verdade). O PDF exportado é o layout fiel.
                blocos.append(
                    _preview_quadro_mobile(estado["ano"], mes, dados, nome_congregacao)
                )
            area_preview.content = ft.Column(
                blocos,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )
            return

        # PC: um mês por vez, com zoom (roda do mouse ou botões). A imagem é
        # gerada a LARGURA_PREVIEW_BASE * ESCALA px, então ampliar até ~300%
        # continua nítido sem precisar regerar o PNG.
        mes = estado["mes_preview"]
        if mes not in (inicio, inicio + 1):
            mes = inicio
            estado["mes_preview"] = mes
        rotulo_mes_preview.value = f"{NOMES_MESES[mes]} de {estado['ano']}"
        rotulo_zoom.value = f"{int(round(estado['zoom'] * 100))}%"

        dados = carregar_dados_mes_quadro(estado["ano"], mes)
        png_bytes = gerar_preview_quadro_mes(
            estado["ano"], mes, dados, nome_congregacao, largura_base=LARGURA_PREVIEW_BASE
        )
        imagem = ft.Image(
            src=png_bytes,
            width=LARGURA_PREVIEW_BASE * estado["zoom"],
            fit=ft.BoxFit.FILL,
        )
        area_preview.content = ft.GestureDetector(
            on_scroll=ao_rolar_preview,
            content=ft.Column(
                [ft.Row([imagem], scroll=ft.ScrollMode.AUTO, tight=True)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )

    def exportar(_=None):
        try:
            caminho, erro = executar_com_progresso(
                page,
                "Gerando PDF...",
                lambda: gerar_quadro_anuncios(estado["ano"], estado["mes_inicial"]),
            )
            if erro:
                mostrar_aviso(page, "Erro ao gerar PDF", erro)
                return
            entregar_arquivo(page, caminho, abrir_arquivo)
            if not eh_mobile():
                mostrar_aviso(
                    page,
                    "PDF gerado com sucesso",
                    f"O quadro de anúncios foi salvo em:\n{caminho}",
                )
        except Exception as exc:
            logger.exception("Falha ao gerar o PDF do quadro")
            mostrar_aviso(page, "Erro", f"Não foi possível gerar o PDF: {exc}")

    def abrir_pdf(_=None):
        # Gera o PDF REAL do quadro e abre a folha do Android para visualizá-lo
        # num leitor de PDF (zoom/arraste perfeitos, layout exato) — melhor do
        # que qualquer visualizador que a gente faça dentro do app.
        try:
            caminho, erro = executar_com_progresso(
                page,
                "Gerando PDF...",
                lambda: gerar_quadro_anuncios(estado["ano"], estado["mes_inicial"]),
            )
            if erro:
                mostrar_aviso(page, "Erro ao gerar PDF", erro)
                return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao gerar o PDF do quadro")
            mostrar_aviso(page, "Erro", f"Não foi possível gerar o PDF: {exc}")
            return

        if _share_global is not None:
            async def _abrir():
                try:
                    await _share_global.share_files([ft.ShareFile.from_path(caminho)])
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Falha ao abrir o PDF do quadro")
                    mostrar_aviso(page, "Não foi possível abrir o PDF", f"Detalhes: {exc}")

            page.run_task(_abrir)
        else:
            # Desktop: abre o arquivo direto.
            entregar_arquivo(page, caminho, abrir_arquivo)

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

    botao_adicionar_ano = ft.IconButton(
        icon=ft.Icons.ADD,
        tooltip="Adicionar ano",
        on_click=abrir_adicionar_ano,
    )
    botao_exportar = ft.FilledButton(
        "Exportar PDF",
        icon=ft.Icons.PICTURE_AS_PDF_OUTLINED,
        on_click=exportar,
    )
    botao_ver_imagem = ft.OutlinedButton(
        "Abrir PDF",
        icon=ft.Icons.OPEN_IN_NEW,
        on_click=abrir_pdf,
    )

    if eh_mobile():
        # Cada seletor em sua própria linha, em largura total: assim "Meses"
        # mostra "Julho-Agosto" inteiro (antes era cortado por dividir a linha
        # com o seletor de Ano). Botão de exportar em linha própria.
        seletor_ano.width = None
        seletor_ano.expand = True
        seletor_par.width = None
        controles = ft.Column(
            [
                ft.Row(
                    [seletor_ano, botao_adicionar_ano],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                seletor_par,
                ft.Row([botao_exportar, botao_ver_imagem], spacing=8, wrap=True),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return ft.Column(
            [
                criar_cabecalho_tela("Quadro de Anúncios"),
                ft.Container(height=8),
                controles,
                ft.Container(height=8),
                area_preview,
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    barra_preview = ft.Row(
        [
            ft.IconButton(
                ft.Icons.CHEVRON_LEFT,
                tooltip="Outro mês do par",
                on_click=lambda _: mudar_mes_preview(-1),
            ),
            rotulo_mes_preview,
            ft.IconButton(
                ft.Icons.CHEVRON_RIGHT,
                tooltip="Outro mês do par",
                on_click=lambda _: mudar_mes_preview(1),
            ),
            ft.Container(expand=True),
            ft.Text("Zoom (Ctrl + roda)", size=fonte(12), color=TEXTO_SECUNDARIO),
            ft.IconButton(
                ft.Icons.ZOOM_OUT,
                tooltip="Reduzir",
                on_click=lambda _: aplicar_zoom(estado["zoom"] - 0.1),
            ),
            rotulo_zoom,
            ft.IconButton(
                ft.Icons.ZOOM_IN,
                tooltip="Ampliar",
                on_click=lambda _: aplicar_zoom(estado["zoom"] + 0.1),
            ),
            ft.TextButton("100%", on_click=lambda _: aplicar_zoom(1.0)),
        ],
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

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
                    botao_adicionar_ano,
                    seletor_par,
                    ft.Container(expand=True),
                    botao_exportar,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            ft.Container(height=8),
            barra_preview,
            ft.Container(height=8),
            area_preview,
        ],
        spacing=0,
        expand=True,
    )


def abrir_dialog_presidente(
    page: ft.Page,
    item: dict | None,
    ao_salvar: Callable[[], None],
) -> None:
    """Adiciona ou edita um presidente num diálogo focado.

    O formulário ficava fixo no topo da lista e mudava de dono quando se
    tocava no lápis — com a lista rolada, a edição acontecia fora da vista.
    Num diálogo fica claro quem está sendo editado.
    """
    editando = item is not None
    item = item or {}
    vinculo = {"contato_id": item.get("contato_id", "")}

    campo_nome = ft.TextField(
        label="Nome", value=item.get("nome", ""), autofocus=not editando
    )
    campo_telefone = _campo_telefone(
        valor=item.get("telefone", ""), hint_text="(11) 90000-0000", expand=True
    )
    campo_categoria = ft.Dropdown(
        label="Privilégio",
        value=item.get("categoria") or "Ancião",
        options=[
            ft.dropdown.Option("Ancião"),
            ft.dropdown.Option("Servo Ministerial"),
        ],
    )
    # Duas escalas independentes: há quem entre no cadastro só para presidir a
    # Celebração e a visita do superintendente, sem pegar fim de semana comum.
    # Novo presidente nasce na escala semanal, que é o caso comum.
    campo_normais = ft.Checkbox(
        label="Preside a reunião de fim de semana",
        value=item.get("preside_normais", True) if editando else True,
        tooltip="Entra no rodízio semanal da Programação.",
    )
    campo_especiais = ft.Checkbox(
        label="Preside datas especiais",
        # Cadastro novo segue o privilégio, que é a prática da congregação e o
        # mesmo critério da migração: ancião entra, servo não. Marcar ou
        # desmarcar continua sendo do usuário.
        value=(item.get("preside_especiais", False) if editando
               else (item.get("categoria") or "Ancião") == "Ancião"),
        tooltip="Entra no rodízio da Celebração, da visita do superintendente "
                "e dos outros eventos, numa fila por tipo, à parte da semanal.",
    )

    def acompanhar_privilegio(e=None):
        # Só enquanto cadastra: em edição, a escolha já feita manda.
        if not editando:
            campo_especiais.value = campo_categoria.value == "Ancião"
        conferir_escalas()

    campo_categoria.on_select = acompanhar_privilegio
    aviso_escala = ft.Text(
        "", size=fonte(12), color=COR_AVISO, visible=False,
    )

    def conferir_escalas(_=None):
        # Nenhuma das duas é permitido (fica no cadastro para o histórico),
        # mas é o tipo de coisa que se faz sem querer ao desmarcar.
        nenhuma = not campo_normais.value and not campo_especiais.value
        aviso_escala.value = (
            "Sem nenhuma das duas ele fica no cadastro, mas fora dos rodízios."
            if nenhuma else ""
        )
        aviso_escala.visible = nenhuma
        page.update()

    campo_normais.on_change = conferir_escalas
    campo_especiais.on_change = conferir_escalas

    texto_erro = ft.Text("", color=ft.Colors.ERROR, size=fonte(13), visible=False)
    botao_contato = _botao_buscar_contato(page, campo_telefone, campo_nome, vinculo)
    icone_contato = ft.IconButton(
        icon=ft.Icons.CONTACT_PHONE_OUTLINED,
        icon_size=fonte(22),
        icon_color=COR_DESTAQUE,
        tooltip="Buscar nos contatos do celular",
        on_click=botao_contato.on_click,
    )

    def fechar(_=None):
        page.pop_dialog()

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
                cadastro_id=item.get("id"),
                telefone=(campo_telefone.value or "").strip(),
                contato_id=vinculo["contato_id"],
                preside_normais=bool(campo_normais.value),
                preside_especiais=bool(campo_especiais.value),
            )
        except sqlite3.IntegrityError:
            texto_erro.value = "Já existe um presidente com esse nome."
            texto_erro.visible = True
            page.update()
            return
        except Exception:
            logger.exception("Falha ao salvar presidente")
            texto_erro.value = "Não foi possível salvar o presidente."
            texto_erro.visible = True
            page.update()
            return
        fechar()
        ao_salvar()

    campo_nome.on_submit = salvar

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Editar presidente" if editando else "Novo presidente",
                size=fonte(18),
                weight=ft.FontWeight.W_600,
            ),
            content=ft.Container(
                width=_largura_dialog(page, 420),
                content=ft.Column(
                    [
                        campo_nome,
                        ft.Row(
                            [campo_telefone, icone_contato],
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        campo_categoria,
                        ft.Container(height=2),
                        ft.Text("Escalas", size=fonte(12), weight=ft.FontWeight.W_600,
                                color=TEXTO_SECUNDARIO),
                        campo_normais,
                        campo_especiais,
                        aviso_escala,
                        texto_erro,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.FilledButton("Salvar", icon=ft.Icons.SAVE, on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
    page.update()


def _linha_presidente(
    indice: int,
    item: dict,
    total: int,
    on_mover: Callable[[int, int], None],
    on_editar: Callable[[dict], None],
    on_excluir: Callable[[dict], None],
    on_conversar: Callable[[dict], None] | None = None,
) -> ft.Control:
    """Um presidente na lista, no mesmo formato da tela de Oradores.

    Antes cada um era um cartão grande e solto; cabiam sete numa tela e
    reordenar o rodízio virava um rolar sem fim. Aqui é uma linha só —
    posição, avatar, nome, contato e ações — dentro de um quadro único.
    """
    telefone = mascara_telefone(item.get("telefone", ""))
    eh_anciao = item["categoria"] == "Ancião"
    cor_privilegio = COR_DESTAQUE_SUAVE if eh_anciao else COR_AVISO

    posicao = ft.Container(
        content=ft.Text(
            f"{indice + 1}",
            size=fonte(12),
            weight=ft.FontWeight.W_700,
            color=TEXTO_SECUNDARIO,
        ),
        width=20,
        alignment=ft.Alignment.CENTER,
    )
    def _selo(texto: str, cor: str, dica: str = "") -> ft.Control:
        return ft.Container(
            content=ft.Text(texto, size=fonte(11), weight=ft.FontWeight.W_600,
                            color=cor, no_wrap=True),
            bgcolor=ft.Colors.with_opacity(0.13, cor),
            border_radius=9,
            padding=ft.Padding.symmetric(horizontal=9, vertical=3),
            tooltip=dica or None,
        )

    chip = _selo("Ancião" if eh_anciao else "Servo", cor_privilegio)
    # De relance: quem é só das datas especiais e quem ficou fora dos dois
    # rodízios (dá para acontecer sem querer ao desmarcar as duas).
    normais = item.get("preside_normais", True)
    especiais = item.get("preside_especiais", False)
    if especiais and not normais:
        selo_escala = _selo("só especiais", COR_DESTAQUE_SUAVE,
                            "Preside apenas Celebração, visita do superintendente e afins")
    elif especiais:
        selo_escala = _selo("+ especiais", COR_SUCESSO,
                            "Preside o fim de semana e também as datas especiais")
    elif not normais:
        selo_escala = _selo("fora do rodízio", COR_AVISO,
                            "Não entra em nenhum dos dois rodízios")
    else:
        selo_escala = None

    def _seta(icone: str, dica: str, delta: int, desabilitada: bool) -> ft.Control:
        return ft.IconButton(
            icon=icone,
            icon_size=fonte(17),
            tooltip=dica,
            icon_color=TEXTO_SECUNDARIO,
            disabled=desabilitada,
            style=ft.ButtonStyle(padding=2),
            on_click=lambda e, i=indice: on_mover(i, delta),
        )

    subir = _seta(ft.Icons.KEYBOARD_ARROW_UP, "Subir no rodízio", -1, indice == 0)
    descer = _seta(
        ft.Icons.KEYBOARD_ARROW_DOWN, "Descer no rodízio", 1, indice == total - 1
    )
    botao_conversar = (
        ft.IconButton(
            icon=ft.Icons.CHAT_OUTLINED,
            icon_size=fonte(17),
            tooltip="Conversar no WhatsApp",
            icon_color="#34D399",
            on_click=lambda e, i=dict(item): on_conversar(i),
        )
        if on_conversar and telefone
        else None
    )
    botao_editar = ft.IconButton(
        icon=ft.Icons.EDIT_OUTLINED,
        icon_size=fonte(17),
        tooltip="Editar",
        icon_color=TEXTO_SECUNDARIO,
        on_click=lambda e, i=dict(item): on_editar(i),
    )
    botao_excluir = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        icon_size=fonte(17),
        icon_color=COR_ERRO,
        tooltip="Excluir (remove também as semanas atribuídas)",
        on_click=lambda e, i=dict(item): on_excluir(i),
    )
    borda_linha = ft.Border(
        ft.BorderSide(0, BORDA_SUAVE),
        ft.BorderSide(0, BORDA_SUAVE),
        ft.BorderSide(1 if indice < total - 1 else 0, BORDA_SUAVE),
        ft.BorderSide(0, BORDA_SUAVE),
    )

    if eh_mobile():
        # Nome na linha inteira: lado a lado com avatar, setas e lixeira
        # sobravam ~90px e ele saía cortado ("Fábio Morei…").
        conteudo = ft.Column(
            [
                ft.Row(
                    [
                        posicao,
                        _avatar_contato(item["nome"], item.get("contato_id", "")),
                        ft.Text(
                            item["nome"],
                            size=fonte(14),
                            weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        _menu_acoes_mobile(
                            [
                                (
                                    "Editar",
                                    ft.Icons.EDIT_OUTLINED,
                                    lambda e, i=dict(item): on_editar(i),
                                ),
                                (
                                    "Excluir",
                                    ft.Icons.DELETE_OUTLINE,
                                    lambda e, i=dict(item): on_excluir(i),
                                ),
                            ]
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text(
                            telefone or "sem telefone",
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                            italic=not telefone,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        chip,
                        *([selo_escala] if selo_escala else []),
                        *([botao_conversar] if botao_conversar else []),
                        subir,
                        descer,
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=6,
            tight=True,
        )
    else:
        conteudo = ft.Row(
            [
                posicao,
                _avatar_contato(item["nome"], item.get("contato_id", "")),
                ft.Column(
                    [
                        ft.Text(
                            item["nome"],
                            size=fonte(14),
                            weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            telefone or "sem telefone",
                            size=fonte(12),
                            color=TEXTO_SECUNDARIO,
                            italic=not telefone,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                chip,
                *([selo_escala] if selo_escala else []),
                *([botao_conversar] if botao_conversar else []),
                botao_editar,
                botao_excluir,
                subir,
                descer,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Container(
        content=conteudo,
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        border=borda_linha,
    )


def _lista_presidentes(
    cadastro: list[dict],
    on_mover: Callable[[int, int], None],
    on_editar: Callable[[dict], None],
    on_excluir: Callable[[dict], None],
    on_conversar: Callable[[dict], None] | None = None,
) -> ft.Control:
    """Todos os presidentes num quadro só, como a lista de Oradores."""
    linhas = [
        _linha_presidente(
            indice, item, len(cadastro), on_mover, on_editar, on_excluir, on_conversar
        )
        for indice, item in enumerate(cadastro)
    ]
    return ft.Container(
        content=ft.Column(linhas, spacing=0, tight=True, scroll=ft.ScrollMode.AUTO),
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        bgcolor=FUNDO_CARD,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def _secao_presidentes(page: ft.Page, ao_mudar: Callable[[], None]) -> ft.Control:
    """Lista dos presidentes com a ordem do rodízio; edição em diálogo."""
    cadastro = listar_presidentes_cadastro()

    def mover(indice: int, delta: int):
        ids = [item["id"] for item in cadastro]
        destino = indice + delta
        if 0 <= destino < len(ids):
            ids[indice], ids[destino] = ids[destino], ids[indice]
            salvar_ordem_presidentes(ids)
            ao_mudar()

    def editar(item: dict):
        abrir_dialog_presidente(page, item, ao_mudar)

    def adicionar(_=None):
        abrir_dialog_presidente(page, None, ao_mudar)

    def excluir(item: dict):
        def fechar(_=None):
            page.pop_dialog()

        def confirmar(_=None):
            fechar()
            try:
                excluir_presidente_cadastro(item["id"])
            except Exception:  # noqa: BLE001
                logger.exception("Falha ao excluir presidente")
                mostrar_aviso(page, "Erro", "Não foi possível excluir este presidente.")
                return
            ao_mudar()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Excluir presidente"),
                content=ft.Text(
                    f"Remover {item['nome']} do cadastro? As semanas já "
                    "atribuídas a ele também são apagadas.",
                    size=fonte(13),
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=fechar),
                    ft.FilledButton(
                        "Excluir",
                        icon=ft.Icons.DELETE_OUTLINE,
                        style=ft.ButtonStyle(bgcolor=COR_ERRO, color="#FFFFFF"),
                        on_click=confirmar,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )
        page.update()

    def conversar(item: dict):
        """WhatsApp do presidente direto da lista, como na tela de Oradores."""
        telefone = (item.get("telefone") or "").strip()
        if not telefone:
            mostrar_aviso(
                page,
                "Sem telefone",
                f"{item.get('nome') or 'Este presidente'} não tem telefone cadastrado.",
            )
            return
        abrir_url(page, gerar_link_whatsapp(telefone, ""))

    anciaos = sum(1 for item in cadastro if item["categoria"] == "Ancião")
    de_especiais = sum(1 for item in cadastro if item.get("preside_especiais"))
    resumo = (
        f"{len(cadastro)} cadastrados · {anciaos} anciãos e "
        f"{len(cadastro) - anciaos} servos · {de_especiais} em datas especiais"
        if cadastro
        else "Ninguém cadastrado ainda"
    )
    botao_adicionar = ft.FilledButton(
        "Adicionar", icon=ft.Icons.PERSON_ADD_ALT, on_click=adicionar
    )

    def exportar_relatorio(_=None):
        from relatorios import secoes_presidentes

        exportar_relatorio_pdf(
            page, secoes_presidentes, "Presidentes e rodízio", "Presidentes"
        )

    texto_resumo = ft.Column(
        [
            ft.Text(resumo, size=fonte(13), weight=ft.FontWeight.W_600,
                    color=TEXTO_PRIMARIO),
            ft.Text(
                "A ordem desta lista define os rodízios. Cada um pode presidir "
                "o fim de semana, as datas especiais, ou as duas coisas.",
                size=fonte(11),
                color=TEXTO_SECUNDARIO,
            ),
        ],
        spacing=2,
        tight=True,
        expand=True,
    )
    botoes = [botao_relatorio_tela(exportar_relatorio), botao_adicionar]
    if eh_mobile():
        # `wrap=True` numa Row com filho `expand=True` não resolve a largura no
        # Flet e a seção inteira vira um retângulo vazio: no celular, empilha.
        cabecalho = ft.Column(
            [texto_resumo, ft.Row(botoes, spacing=8)],
            spacing=8,
            tight=True,
        )
    else:
        cabecalho = ft.Row(
            [texto_resumo, *botoes],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    if not cadastro:
        corpo: list[ft.Control] = [
            criar_painel_informativo(
                "Nenhum presidente cadastrado",
                "Cadastre quem pode presidir a reunião de fim de semana. A "
                "ordem que você definir aqui é a do rodízio automático da "
                "Programação.",
                ft.Icons.MANAGE_ACCOUNTS,
            )
        ]
    else:
        corpo = [_lista_presidentes(cadastro, mover, editar, excluir, conversar)]

    return ft.Column(
        [cabecalho, ft.Container(height=12), *corpo],
        spacing=8,
        tight=True,
    )


def tela_minha_congregacao(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Tudo que é da própria congregação: os dados dela e quem preside.

    Antes os dados moravam em Ajustes (junto de backup e preferências) e os
    presidentes numa aba separada. São a mesma coisa do ponto de vista de quem
    usa: o cadastro da minha congregação.
    """
    estado_aba = {"atual": "dados"}
    area = ft.Column(spacing=0, tight=True)

    def montar():
        if estado_aba["atual"] == "dados":
            area.controls = [_secao_dados_congregacao(page)]
        elif estado_aba["atual"] == "oradores":
            area.controls = [_secao_oradores(page, recarregar)]
        else:
            area.controls = [_secao_presidentes(page, atualizar)]

    def atualizar():
        montar()
        page.update()

    def trocar_aba(valor: str):
        estado_aba["atual"] = valor
        for nome, (chip, texto) in chips.items():
            ativo = nome == valor
            chip.bgcolor = (
                ft.Colors.with_opacity(0.18, COR_DESTAQUE_CLARA)
                if ativo else ft.Colors.TRANSPARENT
            )
            chip.border = ft.Border.all(1, COR_DESTAQUE if ativo else BORDA_SUAVE)
            texto.color = COR_DESTAQUE_SUAVE if ativo else TEXTO_SECUNDARIO
            texto.weight = ft.FontWeight.W_700 if ativo else ft.FontWeight.W_500
        atualizar()

    chips: dict[str, tuple[ft.Container, ft.Text]] = {}

    def _chip(valor: str, rotulo: str, icone: str) -> ft.Container:
        ativo = valor == estado_aba["atual"]
        texto = ft.Text(
            rotulo,
            size=fonte(13),
            no_wrap=True,
            color=COR_DESTAQUE_SUAVE if ativo else TEXTO_SECUNDARIO,
            weight=ft.FontWeight.W_700 if ativo else ft.FontWeight.W_500,
        )
        chip = ft.Container(
            content=ft.Row(
                [ft.Icon(icone, size=fonte(15), color=texto.color), texto],
                spacing=6,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=18,
            bgcolor=(
                ft.Colors.with_opacity(0.18, COR_DESTAQUE_CLARA)
                if ativo else ft.Colors.TRANSPARENT
            ),
            border=ft.Border.all(1, COR_DESTAQUE if ativo else BORDA_SUAVE),
            on_click=lambda e, v=valor: trocar_aba(v),
            ink=True,
        )
        chips[valor] = (chip, texto)
        return chip

    alternador = ft.Row(
        [
            _chip("dados", "Dados", ft.Icons.HOME_WORK_OUTLINED),
            _chip("oradores", "Oradores", ft.Icons.PEOPLE_OUTLINE),
            _chip("presidentes", "Presidentes", ft.Icons.MANAGE_ACCOUNTS),
        ],
        spacing=8,
        tight=True,
    )

    montar()
    return ft.Column(
        [
            criar_cabecalho_tela(
                "Minha congregação",
                "Os dados da congregação, os oradores e quem preside a reunião.",
            ),
            ft.Container(height=12),
            alternador,
            ft.Container(height=16),
            ft.Container(
                content=area,
                # A lista de oradores precisa da largura toda (checkbox, selos
                # e ações); Dados e Presidentes ficam melhor numa coluna.
                width=None if estado_aba["atual"] == "oradores"
                else _largura_dialog(page, 640),
                expand=estado_aba["atual"] == "oradores",
            ),
            ft.Container(height=16),
        ],
        spacing=0,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=(
            ft.CrossAxisAlignment.CENTER if eh_mobile() else ft.CrossAxisAlignment.START
        ),
    )


# ---------------------------------------------------------------------------
# Layout principal
# ---------------------------------------------------------------------------

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
                        size=fonte(11),
                        weight=ft.FontWeight.W_600,
                        color=TEXTO_SECUNDARIO,
                    ),
                    ft.Text(f"v{VERSAO_APP}", size=fonte(10), color=TEXTO_SECUNDARIO),
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
        icone = ft.Icon(secao["icone"], size=_tema.ICON_SIZE_MENU, color=cor)
        rotulo = ft.Text(
            secao["nome"],
            size=fonte(13),
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
        width=_tema.LARGURA_BARRA_LATERAL,
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


def _auto_backup_diario() -> None:
    """Faz, no máximo, uma cópia de segurança automática por dia.

    Silenciosa e defensiva: nunca interrompe a abertura do app. Não faz backup
    de banco vazio (instalação nova) e nunca apaga backups existentes — só cria
    o do dia se ainda não houver. Reaproveita ``exportar_backup`` do database.
    """
    try:
        from armazenamento import BACKUPS_DIR

        hoje = date.today().strftime("%Y-%m-%d")
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        ja_tem_hoje = any(
            arquivo.name.startswith(f"backup_gestao_arranjo_{hoje}")
            for arquivo in BACKUPS_DIR.glob("*.json")
        )
        if ja_tem_hoje:
            return
        total = int(carregar_dados("SELECT COUNT(*) AS n FROM oradores")["n"].iloc[0])
        if total == 0:
            return
        caminho, _ = exportar_backup()
        return caminho
    except Exception:  # noqa: BLE001 — backup automático nunca deve quebrar o app
        logger.exception("Falha no backup automático diário")
        return None


def _enviar_backup_nuvem_em_segundo_plano(page: ft.Page, caminho: str) -> None:
    """Sobe o backup do dia para o Drive, se o aparelho estiver conectado.

    Silencioso e fora da thread da interface: é uma conveniência, não pode
    atrasar nem quebrar a abertura do app. Falhas ficam no log.
    """
    if not nuvem_drive.esta_conectado():
        return

    async def _subir():
        import asyncio

        def tarefa():
            credenciais = nuvem_drive.carregar_credenciais()
            token = nuvem_drive.obter_access_token(credenciais)
            nuvem_drive.enviar_backup(token, caminho)

        try:
            await asyncio.to_thread(tarefa)
            nuvem_drive.registrar_envio()
            logger.info("Backup do dia enviado ao Google Drive")
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao enviar o backup automático para a nuvem")

    page.run_task(_subir)




def _mostrar_onboarding(page: ft.Page, navegar: Callable[[int], None]) -> None:
    """Boas-vindas no primeiro uso: orienta o preenchimento inicial."""

    def ir_ajustes(_=None):
        page.pop_dialog()
        navegar(INDICE_MINHA_CONGREGACAO)

    passos = [
        ("1. Sua congregação", "Preencha os dados na tela Minha congregação."),
        ("2. Congregações", "Cadastre as congregações com que você faz arranjos."),
        ("3. Oradores e temas", "Adicione oradores e importe os temas (S-99/S-99a)."),
        ("4. Programação", "Monte os arranjos do mês, ou importe tudo de uma planilha."),
    ]
    linhas = [
        ft.Column(
            [
                ft.Text(titulo, weight=ft.FontWeight.W_600, size=fonte(13), color=TEXTO_PRIMARIO),
                ft.Text(desc, size=fonte(12), color=TEXTO_SECUNDARIO),
            ],
            spacing=1,
            tight=True,
        )
        for titulo, desc in passos
    ]
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Bem-vindo ao Gestão de Arranjo"),
            content=ft.Container(
                width=_largura_dialog(page, 420),
                content=ft.Column(
                    [
                        ft.Text(
                            "Estes são os primeiros passos:",
                            size=fonte(13),
                            color=TEXTO_PRIMARIO,
                        ),
                        ft.Container(height=6),
                        *linhas,
                    ],
                    spacing=10,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Depois", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton(
                    "Preencher Minha Congregação",
                    icon=ft.Icons.APARTMENT,
                    on_click=ir_ajustes,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )




def main(page: ft.Page):
    """Configura a janela e monta o layout principal."""
    # Layout pela plataforma REAL: só Android/iOS usam a interface de celular.
    # (O desktop empacotado também define FLET_APP_STORAGE_DATA, por isso não
    # dá para deduzir o layout a partir da área de armazenamento.)
    definir_layout_mobile(
        page.platform
        in (
            ft.PagePlatform.ANDROID,
            ft.PagePlatform.ANDROID_TV,
            ft.PagePlatform.IOS,
        )
    )
    configurar_log()
    logger.info(
        "Aplicativo iniciado (v%s) — plataforma=%s, layout_celular=%s",
        VERSAO_APP,
        page.platform,
        eh_mobile(),
    )
    garantir_tabelas()
    # Escala de fonte escolhida pelo usuário (acessibilidade), antes de montar a UI.
    _tema.definir_escala(carregar_escala_fonte())
    backup_do_dia = _auto_backup_diario()

    page.title = "Gestão de Arranjo"
    page.on_keyboard_event = _registrar_teclado  # rastreia Ctrl p/ o zoom do quadro
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

    def mostrar_congregacoes():
        area_conteudo.content = tela_congregacoes(page, recarregar)

    def mostrar_temas():
        area_conteudo.content = tela_temas(page, file_picker)

    def mostrar_quadro_anuncios():
        area_conteudo.content = tela_quadro_anuncios(page, recarregar)

    def mostrar_ajustes():
        area_conteudo.content = tela_ajustes(page, recarregar, file_picker)

    def mostrar_calendario():
        area_conteudo.content = tela_calendario(page, recarregar)

    def mostrar_relatorios():
        area_conteudo.content = tela_relatorios(page, recarregar)

    def mostrar_minha_congregacao():
        area_conteudo.content = tela_minha_congregacao(page, recarregar)

    telas = [
        mostrar_inicio,
        mostrar_programacao,
        mostrar_congregacoes,
        mostrar_minha_congregacao,
        mostrar_temas,
        mostrar_quadro_anuncios,
        mostrar_calendario,
        mostrar_relatorios,
        mostrar_ajustes,
    ]

    def navegar(indice: int):
        estado["indice"] = indice
        atualizar_menu_lateral(itens_menu, indice)
        titulo_topo = estado.get("titulo_topo")
        if titulo_topo is not None:
            titulo_topo.value = SECOES[indice]["nome"]
        telas[indice]()
        page.update()

    def recarregar():
        navegar(estado["indice"])

    file_picker = ft.FilePicker()
    servico_share = ft.Share()
    servico_clipboard = ft.Clipboard()
    global _file_picker_global, _share_global, _clipboard_global
    global _contatos_nativo_global
    _file_picker_global = file_picker
    _share_global = servico_share
    _clipboard_global = servico_clipboard
    # Só existe no build do Android; no PC continua None e o app usa o .vcf.
    _contatos_nativo_global = (
        _ServicoContatosNativo() if _ServicoContatosNativo is not None else None
    )

    if eh_mobile():
        # Layout de celular: barra superior com menu que abre a lista de seções;
        # conteúdo em largura total (sem barra lateral fixa).
        area_conteudo.padding = ft.Padding.symmetric(horizontal=16, vertical=16)
        titulo_topo = ft.Text(
            SECOES[0]["nome"], size=fonte(18), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO,
        )
        estado["titulo_topo"] = titulo_topo

        def abrir_menu(_=None):
            def escolher(indice):
                page.pop_dialog()
                navegar(indice)

            itens = [
                ft.ListTile(
                    leading=ft.Icon(secao["icone"], color=TEXTO_SECUNDARIO),
                    title=ft.Text(secao["nome"]),
                    on_click=lambda e, i=indice: escolher(i),
                )
                for indice, secao in enumerate(SECOES)
            ]
            rodape_versao = ft.Container(
                content=ft.Text(
                    f"Gestão de Arranjo · v{VERSAO_APP}",
                    size=fonte(12), color=TEXTO_SECUNDARIO,
                ),
                padding=ft.Padding.only(left=16, top=12, bottom=4),
            )
            page.show_dialog(
                ft.AlertDialog(
                    content=ft.Column([*itens, rodape_versao], tight=True, spacing=0,
                                      width=300, scroll=ft.ScrollMode.AUTO),
                    content_padding=ft.Padding.symmetric(horizontal=0, vertical=8),
                )
            )

        barra_superior = ft.Container(
            content=ft.Row(
                [
                    ft.IconButton(ft.Icons.MENU, on_click=abrir_menu, icon_color=TEXTO_PRIMARIO),
                    titulo_topo,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=FUNDO_SIDEBAR,
            padding=ft.Padding.only(left=6, right=12, top=4, bottom=4),
        )
        page.add(
            ft.SafeArea(
                content=ft.Column(
                    [barra_superior, area_conteudo],
                    spacing=0,
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                expand=True,
            )
        )
    else:
        barra_lateral = criar_barra_lateral(navegar, itens_menu)
        page.add(
            ft.Container(
                content=ft.Row(
                    [barra_lateral, area_conteudo],
                    expand=True,
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                expand=True,
                bgcolor=FUNDO_APP,
            )
        )

    page.update()
    navegar(0)
    verificar_na_abertura(page)
    # Quem trocou de número na agenda do celular chega aqui já atualizado.
    sincronizar_contatos_vinculados(page, ao_terminar=recarregar)
    if backup_do_dia:
        _enviar_backup_nuvem_em_segundo_plano(page, backup_do_dia)

    # Primeiro uso: se a congregação ainda não foi preenchida, orienta o usuário.
    if not carregar_configuracao().get("nome_congregacao", "").strip():
        _mostrar_onboarding(page, navegar)


# Ponto de entrada do flet build (mobile) e do `flet run` (desktop): o Flet
# escolhe a janela/tela conforme a plataforma.
ft.run(main)
