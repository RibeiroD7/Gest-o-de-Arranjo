import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from armazenamento import (
    BACKUPS_DIR,
    DATA_DIR,
    caminho_temas_embutido,
    caminho_temas_seed_json,
)

DB_PATH = str(DATA_DIR / "gestao_arranjo.db")

def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _migrar_presidentes_para_cadastro(conn) -> None:
    """Migra a tabela `presidentes` do esquema antigo (orador_id) para o novo.

    No esquema novo, as atribuições semanais apontam para `presidentes_cadastro`
    (registro próprio com nome e privilégio), não mais para `oradores`.
    """
    cursor = conn.cursor()
    colunas = [linha[1] for linha in cursor.execute("PRAGMA table_info(presidentes)")]
    if "orador_id" not in colunas:
        return

    atribuicoes = cursor.execute(
        """
        SELECT p.data, o.nome, COALESCE(o.categoria, 'Ancião')
        FROM presidentes p
        JOIN oradores o ON p.orador_id = o.id
        """
    ).fetchall()

    cursor.execute("""
        CREATE TABLE presidentes_nova (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            presidente_id INTEGER NOT NULL,
            FOREIGN KEY (presidente_id) REFERENCES presidentes_cadastro(id)
        )
    """)
    for data, nome, categoria in atribuicoes:
        cursor.execute(
            "INSERT OR IGNORE INTO presidentes_cadastro (nome, categoria) VALUES (?, ?)",
            (nome, categoria),
        )
        cadastro_id = cursor.execute(
            "SELECT id FROM presidentes_cadastro WHERE nome = ?", (nome,)
        ).fetchone()[0]
        cursor.execute(
            "INSERT OR REPLACE INTO presidentes_nova (data, presidente_id) VALUES (?, ?)",
            (data, cadastro_id),
        )
    cursor.execute("DROP TABLE presidentes")
    cursor.execute("ALTER TABLE presidentes_nova RENAME TO presidentes")
    conn.commit()


TIPOS_EVENTO_PADRAO = [
    "Assembleia de Circuito",
    "Congresso Regional",
    "Visita do Superintendente",
    "Celebração",
    "Reunião Especial",
    "Arranjo Local",
]


def _semear_tipos_evento(conn) -> None:
    """Garante os tipos padrão e os já usados em datas especiais."""
    cursor = conn.cursor()
    usados = [linha[0] for linha in cursor.execute("SELECT DISTINCT tipo FROM datas_especiais")]
    for nome in [*TIPOS_EVENTO_PADRAO, *usados]:
        if nome:
            cursor.execute(
                "INSERT OR IGNORE INTO tipos_evento_especial (nome) VALUES (?)", (nome,)
            )
    conn.commit()


# Sequência opcional para ordenar o rodízio na migração; vazio ordena por nome.
ROTACAO_PRESIDENTES_2026: list[str] = []


def _semear_ordem_presidentes(conn) -> None:
    """Ordena o cadastro pela sequência de rotação usada em 2026; o resto vai depois."""
    import unicodedata

    def norm(nome: str) -> str:
        texto = unicodedata.normalize("NFKD", (nome or "").casefold().strip())
        return " ".join("".join(c for c in texto if not unicodedata.combining(c)).split())

    cursor = conn.cursor()
    cadastro = {norm(nome): pid for pid, nome in cursor.execute("SELECT id, nome FROM presidentes_cadastro")}
    posicao = 0
    usados = set()
    for nome in ROTACAO_PRESIDENTES_2026:
        pid = cadastro.get(norm(nome))
        if pid is not None:
            posicao += 1
            usados.add(pid)
            cursor.execute("UPDATE presidentes_cadastro SET ordem = ? WHERE id = ?", (posicao, pid))
    restantes = cursor.execute(
        "SELECT id FROM presidentes_cadastro WHERE ordem IS NULL ORDER BY nome"
    ).fetchall()
    for (pid,) in restantes:
        posicao += 1
        cursor.execute("UPDATE presidentes_cadastro SET ordem = ? WHERE id = ?", (posicao, pid))
    conn.commit()


def _migrar_oradores_fantasma(conn) -> None:
    """Converte oradores que não são pessoas em datas especiais e divide simpósios.

    - "Arranjo Local", "Congresso" etc. viram registros em `datas_especiais`
      (com o tema, quando houver) e saem do cadastro de oradores.
    - Nomes compostos "A/B" (simpósio) viram dois registros de designação na
      mesma data, um por orador real.
    """
    cursor = conn.cursor()
    mapa_fantasmas = {
        "Arranjo Local": "Arranjo Local",
        "Congresso": "Congresso Regional",
        "Assembleia": "Assembleia de Circuito",
        "Reunião Especial": "Reunião Especial",
        "Visita do Superintendente": "Visita do Superintendente",
        "Celebração": "Celebração",
        "Sem designação": None,
    }

    for nome, tipo in mapa_fantasmas.items():
        linha = cursor.execute(
            "SELECT id FROM oradores WHERE TRIM(nome) = ?", (nome,)
        ).fetchone()
        if not linha:
            continue
        orador_id = linha[0]
        if tipo:
            registros = cursor.execute(
                """
                SELECT ao.data, t.titulo
                FROM arranjo_oradores ao
                LEFT JOIN temas t ON ao.tema_nr = t.nr
                WHERE ao.orador_id = ? AND ao.data IS NOT NULL
                """,
                (orador_id,),
            ).fetchall()
            for data, titulo in registros:
                cursor.execute(
                    """
                    INSERT INTO datas_especiais (data, tipo, tema)
                    VALUES (?, ?, ?)
                    ON CONFLICT(data) DO NOTHING
                    """,
                    (data, tipo, titulo or None),
                )
        cursor.execute("DELETE FROM arranjo_oradores WHERE orador_id = ?", (orador_id,))
        cursor.execute("DELETE FROM orador_temas WHERE orador_id = ?", (orador_id,))
        cursor.execute("DELETE FROM presidentes WHERE presidente_id IN (SELECT id FROM presidentes_cadastro WHERE 0)")
        cursor.execute("DELETE FROM oradores WHERE id = ?", (orador_id,))

    compostos = cursor.execute(
        "SELECT id, nome, congregacao_id FROM oradores WHERE nome LIKE '%/%'"
    ).fetchall()
    for composto_id, nome, congregacao_id in compostos:
        partes = [parte.strip() for parte in nome.split("/") if parte.strip()]
        if len(partes) < 2:
            continue
        ids_partes = []
        for parte in partes:
            existente = cursor.execute(
                "SELECT id FROM oradores WHERE TRIM(nome) = ? COLLATE NOCASE", (parte,)
            ).fetchone()
            if existente:
                ids_partes.append(existente[0])
            else:
                cursor.execute(
                    """INSERT INTO oradores (nome, telefone, categoria, congregacao_id, observacoes)
                       VALUES (?, '', 'Ancião', ?, '')""",
                    (parte, congregacao_id),
                )
                ids_partes.append(cursor.lastrowid)
        registros = cursor.execute(
            """SELECT id, arranjo_id, tipo, tema_nr, congregacao_id, data
               FROM arranjo_oradores WHERE orador_id = ?""",
            (composto_id,),
        ).fetchall()
        for registro_id, arranjo_id, tipo, tema_nr, cong_id, data in registros:
            for parte_id in ids_partes:
                cursor.execute(
                    """INSERT INTO arranjo_oradores (arranjo_id, tipo, orador_id, tema_nr, congregacao_id, data)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (arranjo_id, tipo, parte_id, tema_nr, cong_id, data),
                )
            cursor.execute("DELETE FROM arranjo_oradores WHERE id = ?", (registro_id,))
        cursor.execute("DELETE FROM orador_temas WHERE orador_id = ?", (composto_id,))
        cursor.execute("DELETE FROM oradores WHERE id = ?", (composto_id,))

    conn.commit()


def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS congregacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            responsavel TEXT,
            telefone TEXT,
            endereco TEXT,
            dia_semana TEXT,
            horario TEXT,
            observacoes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            categoria TEXT CHECK(categoria IN ('Ancião', 'Servo Ministerial')),
            congregacao_id INTEGER,
            observacoes TEXT,
            FOREIGN KEY (congregacao_id) REFERENCES congregacoes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS temas (
            nr INTEGER PRIMARY KEY,
            titulo TEXT NOT NULL,
            anos_uso TEXT,
            data_limite_uso TEXT,
            notas TEXT
        )
    """)

    migrar_temas(conn)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS temas_anos_colunas (
            ano INTEGER PRIMARY KEY,
            visivel INTEGER NOT NULL DEFAULT 1,
            ordem INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tema_uso_por_ano (
            tema_nr INTEGER NOT NULL,
            ano_coluna INTEGER NOT NULL,
            data_uso TEXT,
            PRIMARY KEY (tema_nr, ano_coluna),
            FOREIGN KEY (tema_nr) REFERENCES temas(nr) ON DELETE CASCADE,
            FOREIGN KEY (ano_coluna) REFERENCES temas_anos_colunas(ano) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orador_temas (
            orador_id INTEGER,
            tema_nr INTEGER,
            PRIMARY KEY (orador_id, tema_nr),
            FOREIGN KEY (orador_id) REFERENCES oradores(id),
            FOREIGN KEY (tema_nr) REFERENCES temas(nr)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arranjos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano INTEGER,
            mes_inicio INTEGER,
            mes_fim INTEGER,
            congregacao_host_id INTEGER,
            responsavel TEXT,
            telefone TEXT,
            endereco TEXT,
            dia_semana TEXT,
            horario TEXT,
            FOREIGN KEY (congregacao_host_id) REFERENCES congregacoes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS designacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT,
            orador_id INTEGER,
            tema_nr INTEGER,
            presidente_id INTEGER,
            congregacao_host_id INTEGER,
            local_reuniao TEXT,
            observacoes TEXT,
            FOREIGN KEY (orador_id) REFERENCES oradores(id),
            FOREIGN KEY (presidente_id) REFERENCES oradores(id),
            FOREIGN KEY (congregacao_host_id) REFERENCES congregacoes(id),
            FOREIGN KEY (tema_nr) REFERENCES temas(nr)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presidentes_cadastro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            categoria TEXT NOT NULL DEFAULT 'Ancião'
                CHECK(categoria IN ('Ancião', 'Servo Ministerial'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presidentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            presidente_id INTEGER NOT NULL,
            FOREIGN KEY (presidente_id) REFERENCES presidentes_cadastro(id)
        )
    """)

    _migrar_presidentes_para_cadastro(conn)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anos_planejamento (
            ano INTEGER PRIMARY KEY
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS datas_especiais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            tipo TEXT NOT NULL,
            orador TEXT,
            tema TEXT,
            presidente_id INTEGER,
            FOREIGN KEY (presidente_id) REFERENCES presidentes_cadastro(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tipos_evento_especial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    """)
    _semear_tipos_evento(conn)
    _migrar_oradores_fantasma(conn)

    colunas_oradores = [linha[1] for linha in cursor.execute("PRAGMA table_info(oradores)")]
    if "ativo" not in colunas_oradores:
        cursor.execute("ALTER TABLE oradores ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")

    colunas_especiais = [linha[1] for linha in cursor.execute("PRAGMA table_info(datas_especiais)")]
    if "congregacao_id" not in colunas_especiais:
        cursor.execute("ALTER TABLE datas_especiais ADD COLUMN congregacao_id INTEGER")

    colunas_cadastro = [linha[1] for linha in cursor.execute("PRAGMA table_info(presidentes_cadastro)")]
    if "ordem" not in colunas_cadastro:
        cursor.execute("ALTER TABLE presidentes_cadastro ADD COLUMN ordem INTEGER")
        _semear_ordem_presidentes(conn)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome_congregacao TEXT NOT NULL DEFAULT '',
            endereco TEXT,
            cidade TEXT DEFAULT '',
            cep TEXT DEFAULT '',
            coordenador_discursos TEXT,
            telefone_coordenador TEXT,
            dia_reuniao TEXT,
            horario_reuniao TEXT,
            circuito TEXT DEFAULT ''
        )
    """)

    migrar_configuracoes(conn)
    migrar_oradores(conn)
    migrar_arranjos(conn)
    migrar_arranjo_oradores(conn)

    # Status de confirmação das designações (pendente/confirmado/recusado).
    # Registros já existentes são históricos: marcados como confirmados; novos
    # nascem como "pendente" (o coordenador confirma quando o orador responde).
    colunas_ao = [linha[1] for linha in cursor.execute("PRAGMA table_info(arranjo_oradores)")]
    if "status" not in colunas_ao:
        cursor.execute(
            "ALTER TABLE arranjo_oradores ADD COLUMN status TEXT NOT NULL DEFAULT 'pendente'"
        )
        cursor.execute("UPDATE arranjo_oradores SET status = 'confirmado'")

    conn.commit()
    print("Tabelas criadas com sucesso!")


def migrar_oradores(conn) -> None:
    """Remove oradores duplicados e impede novas duplicatas por nome/congregação."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT o2.id, o1.id
        FROM oradores o1
        JOIN oradores o2
          ON o1.nome = o2.nome
         AND COALESCE(o1.congregacao_id, -1) = COALESCE(o2.congregacao_id, -1)
         AND o1.id < o2.id
        """
    )
    for dup_id, keep_id in cursor.fetchall():
        cursor.execute(
            """
            INSERT OR IGNORE INTO orador_temas (orador_id, tema_nr)
            SELECT ?, tema_nr FROM orador_temas WHERE orador_id = ?
            """,
            (keep_id, dup_id),
        )
        cursor.execute("DELETE FROM orador_temas WHERE orador_id = ?", (dup_id,))
        cursor.execute(
            "UPDATE designacoes SET orador_id = ? WHERE orador_id = ?",
            (keep_id, dup_id),
        )
        cursor.execute(
            "UPDATE designacoes SET presidente_id = ? WHERE presidente_id = ?",
            (keep_id, dup_id),
        )
        cursor.execute("DELETE FROM oradores WHERE id = ?", (dup_id,))

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_oradores_nome_congregacao
        ON oradores(nome, congregacao_id)
        """
    )
    conn.commit()


def migrar_arranjos(conn) -> None:
    """Remove arranjos duplicados e impede novas duplicatas por ano/período."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a2.id, a1.id
        FROM arranjos a1
        JOIN arranjos a2
          ON a1.ano = a2.ano
         AND a1.mes_inicio = a2.mes_inicio
         AND a1.mes_fim = a2.mes_fim
         AND a1.id < a2.id
        """
    )
    for dup_id, _keep_id in cursor.fetchall():
        cursor.execute("DELETE FROM arranjos WHERE id = ?", (dup_id,))

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_arranjos_periodo
        ON arranjos(ano, mes_inicio, mes_fim)
        """
    )
    conn.commit()


def migrar_arranjo_oradores(conn) -> None:
    """Cria/atualiza tabela de oradores recebidos/enviados por arranjo mensal."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='arranjo_oradores'"
    )
    if not cursor.fetchone():
        cursor.execute(
            """
            CREATE TABLE arranjo_oradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                arranjo_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('recebido', 'enviado')),
                orador_id INTEGER NOT NULL,
                tema_nr INTEGER,
                congregacao_id INTEGER,
                data TEXT,
                FOREIGN KEY (arranjo_id) REFERENCES arranjos(id) ON DELETE CASCADE,
                FOREIGN KEY (orador_id) REFERENCES oradores(id),
                FOREIGN KEY (tema_nr) REFERENCES temas(nr),
                FOREIGN KEY (congregacao_id) REFERENCES congregacoes(id),
                UNIQUE(arranjo_id, tipo, orador_id, data)
            )
            """
        )
        conn.commit()
        return

    cursor.execute("PRAGMA table_info(arranjo_oradores)")
    colunas = {linha[1] for linha in cursor.fetchall()}
    if "data" in colunas:
        return

    cursor.execute(
        """
        CREATE TABLE arranjo_oradores_nova (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arranjo_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('recebido', 'enviado')),
            orador_id INTEGER NOT NULL,
            tema_nr INTEGER,
            congregacao_id INTEGER,
            data TEXT,
            FOREIGN KEY (arranjo_id) REFERENCES arranjos(id) ON DELETE CASCADE,
            FOREIGN KEY (orador_id) REFERENCES oradores(id),
            FOREIGN KEY (tema_nr) REFERENCES temas(nr),
            FOREIGN KEY (congregacao_id) REFERENCES congregacoes(id),
            UNIQUE(arranjo_id, tipo, orador_id, data)
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO arranjo_oradores_nova (
            id, arranjo_id, tipo, orador_id, tema_nr, congregacao_id, data
        )
        SELECT id, arranjo_id, tipo, orador_id, tema_nr, congregacao_id, NULL
        FROM arranjo_oradores
        """
    )
    cursor.execute("DROP TABLE arranjo_oradores")
    cursor.execute("ALTER TABLE arranjo_oradores_nova RENAME TO arranjo_oradores")
    conn.commit()


def carregar_oradores_arranjo(arranjo_id: int) -> list[dict]:
    """Lista oradores vinculados a um arranjo (recebidos ou enviados)."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT ao.id,
                   ao.tipo,
                   ao.orador_id,
                   ao.tema_nr,
                   ao.congregacao_id,
                   ao.data,
                   COALESCE(o.nome, '') AS orador_nome,
                   COALESCE(t.titulo, '') AS tema_titulo,
                   COALESCE(c.nome, '') AS congregacao_nome
            FROM arranjo_oradores ao
            JOIN oradores o ON ao.orador_id = o.id
            LEFT JOIN temas t ON ao.tema_nr = t.nr
            LEFT JOIN congregacoes c ON ao.congregacao_id = c.id
            WHERE ao.arranjo_id = ?
            ORDER BY ao.tipo,
                     substr(ao.data, 7, 4),
                     substr(ao.data, 4, 2),
                     substr(ao.data, 1, 2),
                     o.nome
            """,
            (arranjo_id,),
        )
        colunas = [desc[0] for desc in cursor.description]
        return [dict(zip(colunas, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def adicionar_orador_arranjo(
    arranjo_id: int,
    tipo: str,
    orador_id: int,
    tema_nr: int | None,
    congregacao_id: int | None = None,
    data: str | None = None,
) -> None:
    """Adiciona orador recebido ou enviado em um arranjo mensal."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if congregacao_id is None:
            if tipo == "recebido":
                cursor.execute(
                    "SELECT congregacao_id FROM oradores WHERE id = ?",
                    (orador_id,),
                )
                row = cursor.fetchone()
                congregacao_id = row[0] if row else None
            else:
                cursor.execute(
                    "SELECT congregacao_host_id FROM arranjos WHERE id = ?",
                    (arranjo_id,),
                )
                row = cursor.fetchone()
                congregacao_id = row[0] if row else None

        cursor.execute(
            """
            INSERT INTO arranjo_oradores (
                arranjo_id, tipo, orador_id, tema_nr, congregacao_id, data
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (arranjo_id, tipo, orador_id, tema_nr, congregacao_id, data),
        )
        conn.commit()
    finally:
        conn.close()


def remover_orador_arranjo(registro_id: int) -> None:
    """Remove um orador da lista de recebidos/enviados do arranjo."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM arranjo_oradores WHERE id = ?", (registro_id,))
        conn.commit()
    finally:
        conn.close()


def atualizar_orador_arranjo(
    registro_id: int,
    tema_nr: int | None,
    congregacao_id: int | None = None,
    data: str | None = None,
) -> None:
    """Atualiza data, tema e congregação de um orador/designação do arranjo."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE arranjo_oradores
            SET tema_nr = ?, congregacao_id = ?, data = ?
            WHERE id = ?
            """,
            (tema_nr, congregacao_id, data, registro_id),
        )
        conn.commit()
    finally:
        conn.close()


def listar_anos_arranjos() -> list[int]:
    """Lista anos com arranjos cadastrados."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT DISTINCT ano FROM arranjos WHERE ano IS NOT NULL ORDER BY ano DESC"
        )
        return [int(row[0]) for row in cursor.fetchall()]
    finally:
        conn.close()


def carregar_arranjos_por_ano(ano: int) -> list[dict]:
    """Carrega arranjos de um ano com dados da congregação anfitriã."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT a.id,
                   a.ano,
                   a.mes_inicio,
                   a.mes_fim,
                   a.congregacao_host_id,
                   COALESCE(c.nome, '') AS congregacao,
                   COALESCE(a.responsavel, '') AS responsavel,
                   COALESCE(a.telefone, '') AS telefone,
                   COALESCE(a.endereco, '') AS endereco,
                   COALESCE(a.dia_semana, '') AS dia_semana,
                   COALESCE(a.horario, '') AS horario
            FROM arranjos a
            LEFT JOIN congregacoes c ON a.congregacao_host_id = c.id
            WHERE a.ano = ?
            ORDER BY a.mes_inicio
            """,
            (ano,),
        )
        colunas = [desc[0] for desc in cursor.description]
        return [dict(zip(colunas, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def carregar_recebidos_por_ano(ano: int) -> dict[str, dict]:
    """Oradores recebidos no ano, indexados por data (DD/MM/AAAA)."""
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT ao.data,
                   COALESCE(o.nome, '') AS orador,
                   ao.tema_nr,
                   COALESCE(t.titulo, '') AS tema
            FROM arranjo_oradores ao
            JOIN oradores o ON ao.orador_id = o.id
            LEFT JOIN temas t ON ao.tema_nr = t.nr
            WHERE ao.tipo = 'recebido' AND substr(ao.data, 7, 4) = ?
            """,
            (str(ano),),
        ).fetchall()
        return {
            linha[0]: {"orador": linha[1], "tema_nr": linha[2], "tema": linha[3]}
            for linha in linhas
        }
    finally:
        conn.close()


def contar_designacoes_por_mes(ano: int) -> dict[int, dict[str, int]]:
    """Contagem de recebidos/enviados por mês do ano: {mes: {"recebidos", "enviados"}}."""
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT CAST(substr(ao.data, 4, 2) AS INTEGER) AS mes,
                   ao.tipo,
                   COUNT(*)
            FROM arranjo_oradores ao
            WHERE substr(ao.data, 7, 4) = ?
            GROUP BY mes, ao.tipo
            """,
            (str(ano),),
        ).fetchall()
        resultado: dict[int, dict[str, int]] = {}
        for mes, tipo, quantidade in linhas:
            chave = "recebidos" if tipo == "recebido" else "enviados"
            resultado.setdefault(int(mes), {"recebidos": 0, "enviados": 0})[chave] = quantidade
        return resultado
    finally:
        conn.close()


def carregar_arranjo(arranjo_id: int) -> dict | None:
    """Carrega um arranjo pelo ID para edição."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT id, ano, mes_inicio, mes_fim, congregacao_host_id,
                   responsavel, telefone, endereco, dia_semana, horario
            FROM arranjos
            WHERE id = ?
            """,
            (arranjo_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "ano": int(row[1]) if row[1] is not None else 2026,
            "mes_inicio": int(row[2]) if row[2] is not None else 1,
            "mes_fim": int(row[3]) if row[3] is not None else 2,
            "congregacao_host_id": (
                str(int(row[4])) if row[4] is not None else None
            ),
            "responsavel": row[5] or "",
            "telefone": row[6] or "",
            "endereco": row[7] or "",
            "dia_semana": row[8] or "",
            "horario": row[9] or "",
        }
    finally:
        conn.close()


def salvar_arranjo(
    arranjo_id: int | None,
    ano: int,
    mes_inicio: int,
    mes_fim: int,
    congregacao_host_id: int | None,
    responsavel: str,
    telefone: str,
    endereco: str,
    dia_semana: str,
    horario: str,
) -> None:
    """Insere ou atualiza um arranjo mensal."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        params = (
            ano,
            mes_inicio,
            mes_fim,
            congregacao_host_id,
            responsavel or None,
            telefone or None,
            endereco or None,
            dia_semana or None,
            horario or None,
        )
        if arranjo_id:
            cursor.execute(
                """
                UPDATE arranjos
                SET ano = ?, mes_inicio = ?, mes_fim = ?, congregacao_host_id = ?,
                    responsavel = ?, telefone = ?, endereco = ?,
                    dia_semana = ?, horario = ?
                WHERE id = ?
                """,
                params + (arranjo_id,),
            )
        else:
            cursor.execute(
                """
                INSERT INTO arranjos (
                    ano, mes_inicio, mes_fim, congregacao_host_id,
                    responsavel, telefone, endereco, dia_semana, horario
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        conn.commit()
    finally:
        conn.close()


def excluir_arranjo(arranjo_id: int) -> None:
    """Exclui um arranjo mensal."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM arranjos WHERE id = ?", (arranjo_id,))
        conn.commit()
    finally:
        conn.close()


def carregar_temas_de_orador(orador_id: int) -> set[int]:
    """Retorna os números dos temas que um orador pode apresentar."""
    conn = get_connection()
    try:
        linhas = conn.execute(
            "SELECT tema_nr FROM orador_temas WHERE orador_id = ?", (orador_id,)
        ).fetchall()
        return {int(linha[0]) for linha in linhas}
    finally:
        conn.close()


def salvar_orador(
    nome: str,
    telefone: str,
    categoria: str,
    congregacao_id: int | None,
    observacoes: str,
    temas_nr: set[int],
    orador_id: int | None = None,
) -> int:
    """Cria ou atualiza um orador e os temas que ele pode apresentar."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if orador_id:
            cursor.execute(
                """
                UPDATE oradores
                SET nome = ?, telefone = ?, categoria = ?, congregacao_id = ?, observacoes = ?
                WHERE id = ?
                """,
                (nome, telefone, categoria, congregacao_id, observacoes, orador_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO oradores (nome, telefone, categoria, congregacao_id, observacoes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (nome, telefone, categoria, congregacao_id, observacoes),
            )
            orador_id = int(cursor.lastrowid)

        cursor.execute("DELETE FROM orador_temas WHERE orador_id = ?", (orador_id,))
        for nr in sorted(temas_nr):
            cursor.execute(
                "INSERT OR IGNORE INTO orador_temas (orador_id, tema_nr) VALUES (?, ?)",
                (orador_id, nr),
            )

        conn.commit()
        return orador_id
    finally:
        conn.close()


def excluir_orador(orador_id: int) -> None:
    """Remove um orador do cadastro.

    Se ele tiver designações no histórico, é arquivado (some das listas e
    seletores, mas as designações antigas continuam íntegras no quadro).
    Sem histórico, o registro é apagado de vez.
    """
    conn = get_connection()
    try:
        tem_historico = conn.execute(
            """
            SELECT EXISTS(SELECT 1 FROM arranjo_oradores WHERE orador_id = ?)
                OR EXISTS(SELECT 1 FROM designacoes WHERE orador_id = ? OR presidente_id = ?)
            """,
            (orador_id, orador_id, orador_id),
        ).fetchone()[0]
        conn.execute("DELETE FROM orador_temas WHERE orador_id = ?", (orador_id,))
        if tem_historico:
            conn.execute("UPDATE oradores SET ativo = 0 WHERE id = ?", (orador_id,))
        else:
            conn.execute("DELETE FROM oradores WHERE id = ?", (orador_id,))
        conn.commit()
    finally:
        conn.close()


def carregar_presidentes_por_ano(ano: int) -> dict[str, dict]:
    """Retorna os presidentes designados no ano, indexados por data (DD/MM/AAAA)."""
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT p.id, p.data, p.presidente_id, COALESCE(c.nome, '') AS nome
            FROM presidentes p
            JOIN presidentes_cadastro c ON p.presidente_id = c.id
            WHERE substr(p.data, 7, 4) = ?
            """,
            (str(ano),),
        ).fetchall()
        return {
            linha[1]: {"id": linha[0], "data": linha[1], "presidente_id": linha[2], "nome": linha[3]}
            for linha in linhas
        }
    finally:
        conn.close()


def salvar_presidente(data: str, presidente_id: int) -> None:
    """Define (ou substitui) o presidente designado para uma data."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO presidentes (data, presidente_id) VALUES (?, ?)
            ON CONFLICT(data) DO UPDATE SET presidente_id = excluded.presidente_id
            """,
            (data, presidente_id),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_presidente(data: str) -> None:
    """Remove a designação de presidente de uma data."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM presidentes WHERE data = ?", (data,))
        conn.commit()
    finally:
        conn.close()


def listar_presidentes_cadastro() -> list[dict]:
    """Lista o cadastro de presidentes na ordem da rotação."""
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT id, nome, categoria, ordem FROM presidentes_cadastro
            ORDER BY COALESCE(ordem, 999999), nome
            """
        ).fetchall()
        return [
            {"id": linha[0], "nome": linha[1], "categoria": linha[2], "ordem": linha[3]}
            for linha in linhas
        ]
    finally:
        conn.close()


def trocar_ordem_presidentes(id_a: int, id_b: int) -> None:
    """Troca a posição de dois presidentes na rotação."""
    conn = get_connection()
    try:
        ordem_a = conn.execute(
            "SELECT ordem FROM presidentes_cadastro WHERE id = ?", (id_a,)
        ).fetchone()
        ordem_b = conn.execute(
            "SELECT ordem FROM presidentes_cadastro WHERE id = ?", (id_b,)
        ).fetchone()
        if not ordem_a or not ordem_b:
            return
        conn.execute("UPDATE presidentes_cadastro SET ordem = ? WHERE id = ?", (ordem_b[0], id_a))
        conn.execute("UPDATE presidentes_cadastro SET ordem = ? WHERE id = ?", (ordem_a[0], id_b))
        conn.commit()
    finally:
        conn.close()


def carregar_todas_designacoes_presidente() -> dict[str, int]:
    """Todas as designações de presidente já feitas: {data (DD/MM/AAAA): presidente_id}."""
    conn = get_connection()
    try:
        return {
            linha[0]: linha[1]
            for linha in conn.execute("SELECT data, presidente_id FROM presidentes")
        }
    finally:
        conn.close()


def ultimo_presidente_antes(data_br: str) -> int | None:
    """ID do presidente da última data atribuída antes de `data_br` (DD/MM/AAAA)."""
    chave = data_br[6:10] + data_br[3:5] + data_br[0:2]
    conn = get_connection()
    try:
        linha = conn.execute(
            """
            SELECT presidente_id FROM presidentes
            WHERE substr(data, 7, 4) || substr(data, 4, 2) || substr(data, 1, 2) < ?
            ORDER BY substr(data, 7, 4) || substr(data, 4, 2) || substr(data, 1, 2) DESC
            LIMIT 1
            """,
            (chave,),
        ).fetchone()
        return linha[0] if linha else None
    finally:
        conn.close()


def salvar_ordem_presidentes(ids_em_ordem: list[int]) -> None:
    """Regrava a sequência do rodízio conforme a lista de IDs."""
    conn = get_connection()
    try:
        for posicao, presidente_id in enumerate(ids_em_ordem, start=1):
            conn.execute(
                "UPDATE presidentes_cadastro SET ordem = ? WHERE id = ?",
                (posicao, presidente_id),
            )
        conn.commit()
    finally:
        conn.close()


def salvar_presidente_cadastro(nome: str, categoria: str, cadastro_id: int | None = None) -> int:
    """Cria ou atualiza um presidente no cadastro; retorna o ID."""
    conn = get_connection()
    try:
        if cadastro_id:
            conn.execute(
                "UPDATE presidentes_cadastro SET nome = ?, categoria = ? WHERE id = ?",
                (nome, categoria, cadastro_id),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO presidentes_cadastro (nome, categoria, ordem)
                VALUES (?, ?, (SELECT COALESCE(MAX(ordem), 0) + 1 FROM presidentes_cadastro))
                """,
                (nome, categoria),
            )
            cadastro_id = int(cursor.lastrowid)
        conn.commit()
        return cadastro_id
    finally:
        conn.close()


def excluir_presidente_cadastro(cadastro_id: int) -> None:
    """Remove um presidente do cadastro e as semanas atribuídas a ele."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM presidentes WHERE presidente_id = ?", (cadastro_id,))
        conn.execute("DELETE FROM presidentes_cadastro WHERE id = ?", (cadastro_id,))
        conn.commit()
    finally:
        conn.close()


def listar_anos_planejamento() -> list[int]:
    """Lista anos adicionados manualmente para planejamento."""
    conn = get_connection()
    try:
        linhas = conn.execute("SELECT ano FROM anos_planejamento ORDER BY ano").fetchall()
        return [int(linha[0]) for linha in linhas]
    finally:
        conn.close()


def listar_datas_especiais_por_ano(ano: int) -> dict[str, dict]:
    """Datas especiais do ano (Assembleia, Congresso…), indexadas por data."""
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT e.id, e.data, e.tipo,
                   COALESCE(e.orador, '') AS orador,
                   COALESCE(e.tema, '') AS tema,
                   e.presidente_id,
                   COALESCE(c.nome, '') AS presidente_nome,
                   e.congregacao_id,
                   COALESCE(cong.nome, '') AS congregacao_nome
            FROM datas_especiais e
            LEFT JOIN presidentes_cadastro c ON e.presidente_id = c.id
            LEFT JOIN congregacoes cong ON e.congregacao_id = cong.id
            WHERE substr(e.data, 7, 4) = ?
            """,
            (str(ano),),
        ).fetchall()
        return {
            linha[1]: {
                "id": linha[0],
                "data": linha[1],
                "tipo": linha[2],
                "orador": linha[3],
                "tema": linha[4],
                "presidente_id": linha[5],
                "presidente_nome": linha[6],
                "congregacao_id": linha[7],
                "congregacao_nome": linha[8],
            }
            for linha in linhas
        }
    finally:
        conn.close()


def salvar_data_especial(
    data: str,
    tipo: str,
    orador: str,
    tema: str,
    presidente_id: int | None,
    registro_id: int | None = None,
    congregacao_id: int | None = None,
) -> None:
    """Cria ou atualiza uma data especial (substitui se a data já existir)."""
    conn = get_connection()
    try:
        if registro_id:
            conn.execute(
                """
                UPDATE datas_especiais
                SET data = ?, tipo = ?, orador = ?, tema = ?,
                    presidente_id = ?, congregacao_id = ?
                WHERE id = ?
                """,
                (data, tipo, orador or None, tema or None, presidente_id,
                 congregacao_id, registro_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO datas_especiais
                    (data, tipo, orador, tema, presidente_id, congregacao_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(data) DO UPDATE SET
                    tipo = excluded.tipo,
                    orador = excluded.orador,
                    tema = excluded.tema,
                    presidente_id = excluded.presidente_id,
                    congregacao_id = excluded.congregacao_id
                """,
                (data, tipo, orador or None, tema or None, presidente_id, congregacao_id),
            )
        conn.commit()
    finally:
        conn.close()


def excluir_data_especial(registro_id: int) -> None:
    """Remove uma data especial."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM datas_especiais WHERE id = ?", (registro_id,))
        conn.commit()
    finally:
        conn.close()


def listar_tipos_evento() -> list[dict]:
    """Tipos de evento especial disponíveis (ordenados por nome)."""
    conn = get_connection()
    try:
        return [
            {"id": linha[0], "nome": linha[1]}
            for linha in conn.execute(
                "SELECT id, nome FROM tipos_evento_especial ORDER BY nome"
            )
        ]
    finally:
        conn.close()


def adicionar_tipo_evento(nome: str) -> None:
    """Adiciona um tipo de evento especial (idempotente)."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO tipos_evento_especial (nome) VALUES (?)",
            (nome.strip(),),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_tipo_evento(tipo_id: int) -> None:
    """Remove um tipo de evento (datas já cadastradas mantêm o texto)."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM tipos_evento_especial WHERE id = ?", (tipo_id,))
        conn.commit()
    finally:
        conn.close()


def adicionar_ano_planejamento(ano: int) -> None:
    """Adiciona um ano à lista de planejamento (idempotente)."""
    conn = get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO anos_planejamento (ano) VALUES (?)", (ano,))
        conn.commit()
    finally:
        conn.close()


def migrar_temas(conn):
    """Adiciona colunas novas na tabela temas em bancos já existentes."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(temas)")
    colunas = {linha[1] for linha in cursor.fetchall()}
    if "anos_uso" not in colunas:
        cursor.execute("ALTER TABLE temas ADD COLUMN anos_uso TEXT")
    if "categoria" not in colunas:
        cursor.execute("ALTER TABLE temas ADD COLUMN categoria TEXT")
    conn.commit()


def _valor_celula_preenchida(valor) -> bool:
    if valor is None:
        return False
    if isinstance(valor, float) and valor != valor:
        return False
    texto = str(valor).strip().replace("\xa0", "")
    return texto != ""


def _formatar_mes_ano(valor) -> str | None:
    """Converte a data da célula para formato MM/AAAA."""
    if isinstance(valor, datetime):
        return valor.strftime("%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%m/%Y")

    texto = str(valor).strip().replace("\xa0", "")
    if not texto:
        return None

    for parte in (texto.split()[0], texto):
        for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(parte, formato).strftime("%m/%Y")
            except ValueError:
                continue
    return None


def _extrair_limite_uso(titulo: str) -> tuple[str | None, str]:
    """Extrai data limite e nota de restrição a partir do título."""
    if "não use a partir" not in titulo.lower():
        return None, ""

    match = re.search(r"setembro de (\d{4})", titulo, flags=re.IGNORECASE)
    if match:
        ano = match.group(1)
        return f"{ano}-09-01", f"Não usar a partir de setembro/{ano}"

    return "2026-09-01", "Uso restrito"


def _extrair_colunas_ano_planilha(raw) -> list[tuple[int, int]]:
    """Retorna lista (índice_coluna, ano) a partir da linha ANO: da planilha."""
    colunas: list[tuple[int, int]] = []
    for coluna in range(3, raw.shape[1]):
        valor = raw.iloc[2, coluna]
        if not _valor_celula_preenchida(valor):
            continue
        try:
            ano = int(str(valor).strip().replace("\xa0", ""))
            colunas.append((coluna, ano))
        except (TypeError, ValueError):
            continue
    return colunas


def _registrar_anos_colunas(cursor, colunas_ano: list[tuple[int, int]]) -> None:
    for ordem, (_, ano) in enumerate(colunas_ano):
        cursor.execute(
            """
            INSERT INTO temas_anos_colunas (ano, visivel, ordem)
            VALUES (?, 1, ?)
            ON CONFLICT(ano) DO UPDATE SET ordem = excluded.ordem
            """,
            (ano, ordem),
        )


def listar_anos_colunas(apenas_visiveis: bool = False) -> list[dict]:
    """Lista anos configurados como colunas da tabela de temas."""
    filtro = "WHERE visivel = 1" if apenas_visiveis else ""
    conn = get_connection()
    try:
        cursor = conn.execute(
            f"SELECT ano, visivel, ordem FROM temas_anos_colunas {filtro} ORDER BY ordem, ano"
        )
        return [
            {"ano": row[0], "visivel": bool(row[1]), "ordem": row[2]}
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def adicionar_ano_coluna(ano: int) -> None:
    """Adiciona um novo ano como coluna na tabela de temas."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(ordem), -1) + 1 FROM temas_anos_colunas")
        ordem = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO temas_anos_colunas (ano, visivel, ordem)
            VALUES (?, 1, ?)
            ON CONFLICT(ano) DO UPDATE SET visivel = 1
            """,
            (ano, ordem),
        )
        conn.commit()
    finally:
        conn.close()


def definir_visibilidade_ano_coluna(ano: int, visivel: bool) -> None:
    """Oculta ou exibe um ano na tabela de temas."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE temas_anos_colunas SET visivel = ? WHERE ano = ?",
            (1 if visivel else 0, ano),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_ano_coluna(ano: int) -> None:
    """Remove um ano e todos os registros de uso associados."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tema_uso_por_ano WHERE ano_coluna = ?", (ano,))
        cursor.execute("DELETE FROM temas_anos_colunas WHERE ano = ?", (ano,))
        conn.commit()
    finally:
        conn.close()


def carregar_tema(nr: int) -> dict | None:
    """Carrega um tema pelo número, incluindo datas de uso por ano."""
    conn = get_connection()
    try:
        migrar_temas(conn)
        cursor = conn.execute(
            "SELECT nr, titulo, notas, data_limite_uso, categoria FROM temas WHERE nr = ?",
            (nr,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        uso_rows = conn.execute(
            "SELECT ano_coluna, data_uso FROM tema_uso_por_ano WHERE tema_nr = ?",
            (nr,),
        ).fetchall()

        return {
            "nr": int(row[0]),
            "titulo": row[1] or "",
            "notas": row[2] or "",
            "data_limite_uso": row[3] or "",
            "categoria": row[4] or "",
            "uso_por_ano": {int(ano): (data or "") for ano, data in uso_rows},
        }
    finally:
        conn.close()


def salvar_tema(
    nr: int,
    titulo: str,
    notas: str,
    data_limite_uso: str | None,
    uso_por_ano: dict[int, str] | None = None,
    categoria: str | None = None,
) -> None:
    """Atualiza título, assunto, observações e datas de uso por ano."""
    conn = get_connection()
    try:
        migrar_temas(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE temas
            SET titulo = ?, notas = ?, data_limite_uso = ?, categoria = ?
            WHERE nr = ?
            """,
            (titulo, notas or None, data_limite_uso or None, (categoria or "").strip() or None, nr),
        )

        if uso_por_ano is not None:
            for ano_coluna, data_uso in uso_por_ano.items():
                data_limpa = (data_uso or "").strip()
                if data_limpa and data_limpa != "—":
                    cursor.execute(
                        """
                        INSERT INTO tema_uso_por_ano (tema_nr, ano_coluna, data_uso)
                        VALUES (?, ?, ?)
                        ON CONFLICT(tema_nr, ano_coluna) DO UPDATE SET
                            data_uso = excluded.data_uso
                        """,
                        (nr, int(ano_coluna), data_limpa),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM tema_uso_por_ano WHERE tema_nr = ? AND ano_coluna = ?",
                        (nr, int(ano_coluna)),
                    )

        conn.commit()
    finally:
        conn.close()


def excluir_tema(nr: int) -> None:
    """Exclui um tema e seus registros de uso por ano."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tema_uso_por_ano WHERE tema_nr = ?", (nr,))
        cursor.execute("DELETE FROM temas WHERE nr = ?", (nr,))
        conn.commit()
    finally:
        conn.close()


def _chave_mes_ano(data_uso) -> str:
    """Converte "MM/AAAA" em chave ordenável "AAAA-MM"; vazio se não reconhecer."""
    match = re.match(r"^\s*(\d{1,2})\s*/\s*(\d{4})\s*$", str(data_uso or ""))
    if not match:
        return ""
    return f"{match.group(2)}-{int(match.group(1)):02d}"


def carregar_dataframe_temas(apenas_anos_visiveis: bool = True):
    """Monta DataFrame de temas com uma coluna por ano (como na planilha)."""
    import pandas as pd

    conn = get_connection()
    try:
        anos = listar_anos_colunas(apenas_visiveis=apenas_anos_visiveis)
        temas_df = pd.read_sql_query(
            """
            SELECT nr,
                   titulo,
                   COALESCE(NULLIF(categoria, ''), '—') AS assunto,
                   CASE
                       WHEN COALESCE(notas, '') != '' THEN notas
                       WHEN data_limite_uso IS NOT NULL
                           THEN 'Uso restrito — limite: ' || data_limite_uso
                       ELSE '—'
                   END AS restricoes,
                   data_limite_uso,
                   CASE WHEN data_limite_uso IS NOT NULL THEN 1 ELSE 0 END AS restrito,
                   CASE
                       WHEN COALESCE(notas, '') != '' THEN 1
                       ELSE 0
                   END AS tem_observacao
            FROM temas
            ORDER BY nr
            """,
            conn,
        )

        uso_df = pd.read_sql_query(
            "SELECT tema_nr, ano_coluna, data_uso FROM tema_uso_por_ano",
            conn,
        )
    finally:
        conn.close()

    # Último uso considera todos os anos registrados, mesmo colunas ocultas
    ultimo_uso: dict[int, str] = {}
    if not uso_df.empty:
        chaves = uso_df.assign(chave=uso_df["data_uso"].map(_chave_mes_ano))
        chaves = chaves[chaves["chave"] != ""]
        if not chaves.empty:
            ultimo_uso = chaves.groupby("tema_nr")["chave"].max().to_dict()

    temas_df["ultimo_uso_chave"] = temas_df["nr"].map(lambda nr: ultimo_uso.get(nr, ""))
    temas_df["ultimo_uso"] = temas_df["ultimo_uso_chave"].map(
        lambda chave: f"{chave[5:7]}/{chave[0:4]}" if chave else "Nunca"
    )

    if not uso_df.empty and anos:
        anos_visiveis = {item["ano"] for item in anos}
        uso_visivel = uso_df[uso_df["ano_coluna"].isin(anos_visiveis)]
        if not uso_visivel.empty:
            pivot = uso_visivel.pivot(index="tema_nr", columns="ano_coluna", values="data_uso")
            pivot.columns = [str(int(c)) for c in pivot.columns]
            temas_df = temas_df.merge(pivot, left_on="nr", right_index=True, how="left")

    for item in anos:
        coluna = str(item["ano"])
        if coluna not in temas_df.columns:
            temas_df[coluna] = "—"
        else:
            temas_df[coluna] = temas_df[coluna].fillna("—").replace("", "—")

    colunas_ano = [str(item["ano"]) for item in anos]
    return temas_df[
        [
            "nr", "titulo", "assunto", *colunas_ano, "ultimo_uso",
            "restricoes", "data_limite_uso", "restrito", "tem_observacao", "ultimo_uso_chave",
        ]
    ]


def _importar_temas_seed_json(conn, caminho) -> int:
    """Importa os temas do temas_seed.json embutido (sem depender de Excel).

    No celular não há python-calamine e o openpyxl não lê o Temas.xlsx de
    forma confiável, então a carga inicial usa este JSON, gerado a partir da
    própria planilha na versão de computador.
    """
    import json

    with open(caminho, "r", encoding="utf-8") as arquivo:
        seed = json.load(arquivo)

    cursor = conn.cursor()
    for item in seed.get("anos_colunas", []):
        cursor.execute(
            """
            INSERT INTO temas_anos_colunas (ano, visivel, ordem)
            VALUES (?, 1, ?)
            ON CONFLICT(ano) DO UPDATE SET ordem = excluded.ordem
            """,
            (item["ano"], item["ordem"]),
        )
    for tema in seed.get("temas", []):
        cursor.execute(
            """
            INSERT INTO temas (nr, titulo, anos_uso, data_limite_uso, notas)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(nr) DO UPDATE SET
                titulo = excluded.titulo,
                anos_uso = excluded.anos_uso,
                data_limite_uso = excluded.data_limite_uso,
                notas = excluded.notas
            """,
            (tema["nr"], tema["titulo"], tema["anos_uso"],
             tema["data_limite_uso"], tema["notas"]),
        )
    for uso in seed.get("usos", []):
        cursor.execute(
            """
            INSERT INTO tema_uso_por_ano (tema_nr, ano_coluna, data_uso)
            VALUES (?, ?, ?)
            ON CONFLICT(tema_nr, ano_coluna) DO UPDATE SET
                data_uso = excluded.data_uso
            """,
            (uso["tema_nr"], uso["ano_coluna"], uso["data_uso"]),
        )
    conn.commit()
    total = len(seed.get("temas", []))
    print(f"Temas importados do seed JSON: {total} ({caminho})")
    return total


def importar_temas_planilha(conn, caminho: str | None = None) -> int:
    """Importa temas: usa o seed JSON embutido quando disponível (mobile),
    senão lê a planilha Temas.xlsx (desktop)."""
    if caminho is None:
        seed_json = caminho_temas_seed_json()
        if seed_json is not None:
            return _importar_temas_seed_json(conn, seed_json)

    import pandas as pd

    arquivo = Path(caminho) if caminho and Path(caminho).exists() else caminho_temas_embutido()
    if arquivo is None:
        print("Aviso: arquivo Temas.xlsx não encontrado — temas não importados.")
        return 0

    try:
        raw = pd.read_excel(arquivo, engine="calamine", header=None)
    except ImportError:
        # python-calamine indisponível (ex.: Android) — usa o engine padrão
        raw = pd.read_excel(arquivo, header=None)
    colunas_ano = _extrair_colunas_ano_planilha(raw)

    cursor = conn.cursor()
    _registrar_anos_colunas(cursor, colunas_ano)
    inseridos = 0

    for indice in range(4, len(raw)):
        nr_valor = raw.iloc[indice, 0]
        if not _valor_celula_preenchida(nr_valor):
            continue
        try:
            nr = int(nr_valor)
        except (TypeError, ValueError):
            continue

        titulo = str(raw.iloc[indice, 1] or "").replace("\n", " ").strip()
        if not titulo:
            continue

        datas_uso: list[tuple[str, str]] = []
        for coluna, ano_coluna in colunas_ano:
            valor = raw.iloc[indice, coluna]
            if not _valor_celula_preenchida(valor):
                continue
            data_formatada = _formatar_mes_ano(valor)
            if not data_formatada:
                continue
            datas_uso.append((ano_coluna, data_formatada))

        anos_uso = ", ".join(data for _, data in datas_uso)
        data_limite, nota_restricao = _extrair_limite_uso(titulo)

        # O tema precisa existir antes das datas de uso (FK em tema_uso_por_ano)
        cursor.execute(
            """
            INSERT INTO temas (nr, titulo, anos_uso, data_limite_uso, notas)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(nr) DO UPDATE SET
                titulo = excluded.titulo,
                anos_uso = excluded.anos_uso,
                data_limite_uso = excluded.data_limite_uso,
                notas = excluded.notas
            """,
            (nr, titulo, anos_uso or None, data_limite, nota_restricao or None),
        )
        for ano_coluna, data_formatada in datas_uso:
            cursor.execute(
                """
                INSERT INTO tema_uso_por_ano (tema_nr, ano_coluna, data_uso)
                VALUES (?, ?, ?)
                ON CONFLICT(tema_nr, ano_coluna) DO UPDATE SET
                    data_uso = excluded.data_uso
                """,
                (nr, ano_coluna, data_formatada),
            )
        inseridos += 1

    conn.commit()
    print(f"Temas importados da planilha: {inseridos} ({arquivo})")
    return inseridos


def importar_temas_pdf(caminho: str) -> dict:
    """Importa temas de um formulário oficial em PDF (S-99 ou S-99a).

    O S-99 preenche números e títulos; o S-99a preenche o assunto (categoria)
    de cada tema. Datas de uso, observações e limites já cadastrados são
    preservados. Retorna um resumo:
    {"formulario", "total", "novos", "atualizados", "sem_alteracao"}.
    """
    from pdf_temas import ler_formulario_temas

    formulario, temas = ler_formulario_temas(caminho)

    conn = get_connection()
    try:
        migrar_temas(conn)  # bancos antigos podem não ter a coluna categoria
        cursor = conn.cursor()
        novos = atualizados = 0
        for tema in temas:
            row = cursor.execute(
                "SELECT titulo, categoria FROM temas WHERE nr = ?",
                (tema["nr"],),
            ).fetchone()

            if row is None:
                cursor.execute(
                    "INSERT INTO temas (nr, titulo, categoria) VALUES (?, ?, ?)",
                    (tema["nr"], tema["titulo"], tema["categoria"]),
                )
                novos += 1
                continue

            # Título provisório (criado pela carga por planilha) conta como vazio
            titulo_atual = (row[0] or "").strip()
            if titulo_atual.startswith("(título pendente"):
                titulo_atual = ""

            alterou = False
            if (formulario == "S-99" or not titulo_atual) and titulo_atual != tema["titulo"]:
                # O S-99 é a fonte oficial dos títulos; o S-99a só preenche lacunas
                cursor.execute(
                    "UPDATE temas SET titulo = ? WHERE nr = ?",
                    (tema["titulo"], tema["nr"]),
                )
                alterou = True
            if tema["categoria"] and (row[1] or "") != tema["categoria"]:
                cursor.execute(
                    "UPDATE temas SET categoria = ? WHERE nr = ?",
                    (tema["categoria"], tema["nr"]),
                )
                alterou = True
            if alterou:
                atualizados += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "formulario": formulario,
        "total": len(temas),
        "novos": novos,
        "atualizados": atualizados,
        "sem_alteracao": len(temas) - novos - atualizados,
    }


def migrar_configuracoes(conn):
    """Adiciona colunas novas em bancos já existentes."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(configuracoes)")
    colunas = {linha[1] for linha in cursor.fetchall()}
    if "cidade" not in colunas:
        cursor.execute(
            "ALTER TABLE configuracoes ADD COLUMN cidade TEXT DEFAULT ''"
        )
    if "cep" not in colunas:
        cursor.execute(
            "ALTER TABLE configuracoes ADD COLUMN cep TEXT DEFAULT ''"
        )
    conn.commit()


def garantir_configuracao_inicial(conn):
    """Garante uma linha de configuração da congregação principal."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM configuracoes")
    if cursor.fetchone()[0] > 0:
        return

    cursor.execute(
        """
        INSERT INTO configuracoes (
            id, nome_congregacao, endereco, coordenador_discursos,
            telefone_coordenador, dia_reuniao, horario_reuniao, circuito
        ) VALUES (1, '', '', '', '', '', '', '')
        """
    )
    conn.commit()

# ---------------------------------------------------------------------------
# Backup e restauração
# ---------------------------------------------------------------------------
#
# O backup é um JSON versionado e autodescritivo, para que o futuro aplicativo
# de smartphone (ou qualquer outra plataforma) consiga importar os dados sem
# depender do arquivo SQLite: {"app", "versao_backup", "gerado_em", "tabelas"}.

# BACKUPS_DIR vem de armazenamento (área gravável no mobile).
VERSAO_BACKUP = 1

# Ordem respeita as chaves estrangeiras (pais antes dos filhos) — a restauração
# insere nesta ordem e apaga na ordem inversa.
TABELAS_BACKUP = [
    "congregacoes",
    "oradores",
    "temas",
    "temas_anos_colunas",
    "tema_uso_por_ano",
    "orador_temas",
    "arranjos",
    "arranjo_oradores",
    "designacoes",
    "presidentes_cadastro",
    "presidentes",
    "configuracoes",
    "anos_planejamento",
    "datas_especiais",
    "tipos_evento_especial",
]


def exportar_backup() -> tuple[str, dict[str, int]]:
    """Exporta todos os dados para um JSON versionado em `backups/`.

    Retorna (caminho, contagens por tabela).
    """
    import json

    conn = get_connection()
    try:
        tabelas: dict[str, list[dict]] = {}
        for tabela in TABELAS_BACKUP:
            cursor = conn.execute(f"SELECT * FROM {tabela}")  # noqa: S608 — nomes fixos
            colunas = [descricao[0] for descricao in cursor.description]
            tabelas[tabela] = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    finally:
        conn.close()

    payload = {
        "app": "gestao-arranjo",
        "versao_backup": VERSAO_BACKUP,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "tabelas": tabelas,
    }

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"backup_gestao_arranjo_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    caminho = BACKUPS_DIR / nome
    caminho.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    contagens = {tabela: len(linhas) for tabela, linhas in tabelas.items()}
    return str(caminho.resolve()), contagens


def restaurar_backup(caminho: str | Path) -> tuple[bool, str]:
    """Restaura os dados a partir de um JSON de backup.

    Antes de substituir qualquer coisa, salva uma cópia de segurança do banco
    atual em `backups/`. Retorna (sucesso, mensagem).
    """
    import json
    import shutil

    try:
        payload = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "Não foi possível ler o arquivo de backup."

    if payload.get("app") != "gestao-arranjo" or "tabelas" not in payload:
        return False, "O arquivo selecionado não é um backup válido do Gestão de Arranjo."
    if int(payload.get("versao_backup", 0)) > VERSAO_BACKUP:
        return False, (
            "Este backup foi gerado por uma versão mais nova do aplicativo. "
            "Atualize o aplicativo para restaurá-lo."
        )

    tabelas = payload["tabelas"]

    # Cópia de segurança do estado atual antes de qualquer alteração
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    seguranca = BACKUPS_DIR / f"antes_restauracao_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, seguranca)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF")
        for tabela in reversed(TABELAS_BACKUP):
            cursor.execute(f"DELETE FROM {tabela}")  # noqa: S608 — nomes fixos
        for tabela in TABELAS_BACKUP:
            linhas = tabelas.get(tabela) or []
            if not linhas:
                continue
            colunas_existentes = {
                info[1] for info in cursor.execute(f"PRAGMA table_info({tabela})")
            }
            for linha in linhas:
                dados = {c: v for c, v in linha.items() if c in colunas_existentes}
                if not dados:
                    continue
                nomes = ", ".join(dados.keys())
                marcadores = ", ".join("?" * len(dados))
                cursor.execute(
                    f"INSERT INTO {tabela} ({nomes}) VALUES ({marcadores})",  # noqa: S608
                    tuple(dados.values()),
                )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return False, f"Erro ao restaurar: {exc}. O banco original não foi alterado."
    finally:
        conn.close()

    return True, f"Backup restaurado com sucesso. Cópia de segurança salva em:\n{seguranca}"


if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    garantir_configuracao_inicial(conn)
    conn.close()
    print(f"\nBanco de dados criado com sucesso em: {DB_PATH}")
