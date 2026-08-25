"""Importação da planilha: cria o que falta e completa o que já existe.

O caminho que motivou isto: exportar a lista de congregações incompletas,
preencher os contatos no Excel e trazer de volta. Antes, quem já estava
cadastrado era pulado, e a planilha corrigida não servia para nada.
"""

import sqlite3

import pytest
from openpyxl import Workbook

import database
from planilha_dados import (
    ABA_CONGREGACOES,
    ABA_ORADORES,
    ABA_PRESIDENTES,
    COLUNAS_CONGREGACOES,
    COLUNAS_ORADORES,
    COLUNAS_PRESIDENTES,
    importar_planilha_dados,
)


def _planilha(tmp_path, congregacoes=(), oradores=(), presidentes=()):
    """Monta um .xlsx no formato que o app espera."""
    wb = Workbook()
    wb.remove(wb.active)
    for aba, colunas, linhas in (
        (ABA_CONGREGACOES, COLUNAS_CONGREGACOES, congregacoes),
        (ABA_ORADORES, COLUNAS_ORADORES, oradores),
        (ABA_PRESIDENTES, COLUNAS_PRESIDENTES, presidentes),
    ):
        ws = wb.create_sheet(aba)
        ws.append(colunas)
        for linha in linhas:
            ws.append(list(linha))
    caminho = tmp_path / "planilha.xlsx"
    wb.save(caminho)
    return str(caminho)


@pytest.fixture(autouse=True)
def _banco_limpo():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        for tabela in ("arranjo_oradores", "arranjos", "orador_temas", "oradores",
                       "congregacoes", "presidentes", "presidentes_cadastro"):
            conn.execute(f"DELETE FROM {tabela}")
        conn.commit()
    finally:
        conn.close()


def _congregacao(nome):
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row
    try:
        linha = conn.execute("SELECT * FROM congregacoes WHERE nome = ?", (nome,)).fetchone()
        return dict(linha) if linha else None
    finally:
        conn.close()


class TestCongregacoes:
    def test_cria_quem_nao_existe(self, tmp_path):
        caminho = _planilha(tmp_path, congregacoes=[
            ["Jardim Primavera", "João", "(11) 91234-5678", "Rua A, 100", "Sábado", "19:30", ""],
        ])
        resumo = importar_planilha_dados(caminho)
        assert resumo["congregacoes"]["novas"] == 1
        cong = _congregacao("Jardim Primavera")
        assert cong["responsavel"] == "João"
        assert cong["horario"] == "19:30"

    def test_completa_quem_ja_existe(self, tmp_path):
        """O caso real: a congregação existe só com o nome, vinda de outro ano."""
        importar_planilha_dados(_planilha(tmp_path, congregacoes=[
            ["Jardim Primavera", "", "", "", "", "", ""],
        ]))
        caminho = _planilha(tmp_path, congregacoes=[
            ["Jardim Primavera", "Maria", "(11) 95555-0000", "Rua B, 20", "Domingo", "09:00", ""],
        ])
        resumo = importar_planilha_dados(caminho)

        assert resumo["congregacoes"]["atualizadas"] == 1
        assert resumo["congregacoes"]["novas"] == 0
        cong = _congregacao("Jardim Primavera")
        assert cong["responsavel"] == "Maria"
        assert cong["dia_semana"] == "Domingo"
        assert cong["horario"] == "09:00"

    def test_coluna_em_branco_nao_apaga(self, tmp_path):
        importar_planilha_dados(_planilha(tmp_path, congregacoes=[
            ["Jardim Primavera", "Maria", "(11) 95555-0000", "Rua B, 20", "Domingo", "09:00", ""],
        ]))
        importar_planilha_dados(_planilha(tmp_path, congregacoes=[
            ["Jardim Primavera", "", "", "Rua C, 30", "", "", ""],
        ]))
        cong = _congregacao("Jardim Primavera")
        assert cong["endereco"] == "Rua C, 30", "a coluna preenchida entra"
        assert cong["responsavel"] == "Maria", "a coluna vazia não apaga"
        assert cong["horario"] == "09:00"

    def test_reimportar_a_mesma_planilha_nao_conta_mudanca(self, tmp_path):
        caminho = _planilha(tmp_path, congregacoes=[
            ["Jardim Primavera", "Maria", "(11) 95555-0000", "Rua B, 20", "Domingo", "09:00", ""],
        ])
        importar_planilha_dados(caminho)
        resumo = importar_planilha_dados(caminho)
        assert resumo["congregacoes"] == {"novas": 0, "atualizadas": 0, "sem_mudanca": 1}


class TestOradores:
    def test_completa_telefone_e_categoria_de_quem_existe(self, tmp_path):
        importar_planilha_dados(_planilha(tmp_path, oradores=[
            ["Fulano de Tal", "", "", "Jardim Primavera", "", ""],
        ]))
        resumo = importar_planilha_dados(_planilha(tmp_path, oradores=[
            ["Fulano de Tal", "(11) 90000-0000", "Ancião", "Jardim Primavera", "", ""],
        ]))
        assert resumo["oradores"]["atualizados"] == 1

        conn = database.get_connection()
        try:
            telefone, categoria = conn.execute(
                "SELECT telefone, categoria FROM oradores WHERE nome = ?", ("Fulano de Tal",)
            ).fetchone()
        finally:
            conn.close()
        assert telefone == "(11) 90000-0000"
        assert categoria == "Ancião"

    def test_temas_novos_entram_sem_desligar_os_antigos(self, tmp_path):
        importar_planilha_dados(_planilha(tmp_path, oradores=[
            ["Fulano de Tal", "", "Ancião", "Jardim Primavera", "1, 2", ""],
        ]))
        importar_planilha_dados(_planilha(tmp_path, oradores=[
            ["Fulano de Tal", "", "Ancião", "Jardim Primavera", "3", ""],
        ]))
        conn = database.get_connection()
        try:
            temas = [n for (n,) in conn.execute(
                "SELECT tema_nr FROM orador_temas ot JOIN oradores o ON o.id = ot.orador_id "
                "WHERE o.nome = ? ORDER BY tema_nr", ("Fulano de Tal",))]
        finally:
            conn.close()
        assert temas == [1, 2, 3]

    def test_orador_de_outra_congregacao_e_outra_pessoa(self, tmp_path):
        importar_planilha_dados(_planilha(tmp_path, oradores=[
            ["Fulano de Tal", "", "Ancião", "Jardim Primavera", "", ""],
            ["Fulano de Tal", "", "Ancião", "Jardim Segundo", "", ""],
        ]))
        conn = database.get_connection()
        try:
            quantos = conn.execute(
                "SELECT COUNT(*) FROM oradores WHERE nome = ?", ("Fulano de Tal",)
            ).fetchone()[0]
        finally:
            conn.close()
        assert quantos == 2


class TestPresidentes:
    def test_corrige_a_categoria_de_quem_existe(self, tmp_path):
        importar_planilha_dados(_planilha(tmp_path, presidentes=[["Beltrano", "Ancião"]]))
        resumo = importar_planilha_dados(
            _planilha(tmp_path, presidentes=[["Beltrano", "Servo Ministerial"]])
        )
        assert resumo["presidentes"]["atualizados"] == 1

        conn = database.get_connection()
        try:
            categoria = conn.execute(
                "SELECT categoria FROM presidentes_cadastro WHERE nome = ?", ("Beltrano",)
            ).fetchone()[0]
        finally:
            conn.close()
        assert categoria == "Servo Ministerial"
