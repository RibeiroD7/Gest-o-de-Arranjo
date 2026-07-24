"""Teste de ida-e-volta do backup (src/database.py).

Garante que exportar → apagar → restaurar recupera os dados idênticos. O banco
fica numa pasta temporária (ver conftest.py).
"""

import database
from database import (
    create_tables,
    exportar_backup,
    get_connection,
    restaurar_backup,
)


def _resetar_banco():
    conn = get_connection()
    try:
        create_tables(conn)
        conn.execute("DELETE FROM oradores")
        conn.execute("DELETE FROM congregacoes")
        conn.commit()
    finally:
        conn.close()


def test_backup_roundtrip():
    _resetar_banco()

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO congregacoes (nome, telefone, dia_semana, horario) "
            "VALUES (?, ?, ?, ?)",
            ("Central", "1199999", "domingo", "09:00"),
        )
        cong_id = conn.execute(
            "SELECT id FROM congregacoes WHERE nome = 'Central'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) VALUES (?, ?, ?)",
            ("Fulano", "Ancião", cong_id),
        )
        conn.commit()
    finally:
        conn.close()

    caminho, contagens = exportar_backup()
    assert contagens["congregacoes"] == 1
    assert contagens["oradores"] == 1

    # Apaga tudo e confirma que sumiu.
    conn = get_connection()
    try:
        conn.execute("DELETE FROM oradores")
        conn.execute("DELETE FROM congregacoes")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM congregacoes").fetchone()[0] == 0
    finally:
        conn.close()

    ok, _mensagem = restaurar_backup(caminho)
    assert ok is True

    # Dados voltaram idênticos.
    conn = get_connection()
    try:
        cong = conn.execute(
            "SELECT nome, telefone, dia_semana, horario FROM congregacoes"
        ).fetchall()
        oradores = conn.execute("SELECT nome, categoria FROM oradores").fetchall()
    finally:
        conn.close()

    assert cong == [("Central", "1199999", "domingo", "09:00")]
    assert oradores == [("Fulano", "Ancião")]


def test_backup_usa_pasta_temporaria():
    # Sanidade: o teste não deve tocar o banco real do projeto.
    assert "ga-testes-" in database.DB_PATH


def test_trocar_datas_designacoes():
    """O swap respeita a UNIQUE(arranjo_id, tipo, orador_id, data)."""
    _resetar_banco()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM arranjo_oradores")
        conn.execute("DELETE FROM arranjos")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('X')")
        cong = conn.execute("SELECT id FROM congregacoes").fetchone()[0]
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) "
            "VALUES ('A', 'Ancião', ?), ('B', 'Ancião', ?)",
            (cong, cong),
        )
        ids = [r[0] for r in conn.execute("SELECT id FROM oradores ORDER BY nome")]
        conn.execute(
            "INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 1, 1)"
        )
        arranjo = conn.execute("SELECT id FROM arranjos").fetchone()[0]
        conn.execute(
            "INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, data) "
            "VALUES (?, 'enviado', ?, '04/01/2026'), (?, 'enviado', ?, '11/01/2026')",
            (arranjo, ids[0], arranjo, ids[1]),
        )
        conn.commit()
        regs = {
            r[1]: r[0]
            for r in conn.execute("SELECT id, orador_id FROM arranjo_oradores")
        }
    finally:
        conn.close()

    database.trocar_datas_designacoes(regs[ids[0]], regs[ids[1]])

    conn = get_connection()
    try:
        datas = dict(
            conn.execute("SELECT orador_id, data FROM arranjo_oradores").fetchall()
        )
    finally:
        conn.close()
    assert datas[ids[0]] == "11/01/2026"
    assert datas[ids[1]] == "04/01/2026"
