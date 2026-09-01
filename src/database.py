import os
import re
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from armazenamento import (
    BACKUPS_DIR,
    DATA_DIR,
)
from util import SEPARADOR_SIMPOSIO

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


def _migrar_presidentes_avulsos(conn) -> None:
    """Permite gravar um presidente pelo NOME, sem estar no cadastro.

    Acontece de um ancião ou servo ministerial sair da congregação: a semana
    que era dele fica vazia, mas quem presidiu (ou vai presidir) precisa
    aparecer na programação mesmo assim. Esse nome avulso não entra no
    revezamento — por isso ``presidente_id`` passa a aceitar NULL e a linha
    guarda ``nome_avulso``.

    SQLite não afrouxa um NOT NULL com ALTER, então a tabela é reconstruída.
    """
    cursor = conn.cursor()
    colunas = [linha[1] for linha in cursor.execute("PRAGMA table_info(presidentes)")]
    if not colunas or "nome_avulso" in colunas:
        return

    cursor.execute("""
        CREATE TABLE presidentes_avulso_nova (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            presidente_id INTEGER,
            nome_avulso TEXT,
            FOREIGN KEY (presidente_id) REFERENCES presidentes_cadastro(id)
        )
    """)
    cursor.execute(
        """
        INSERT INTO presidentes_avulso_nova (id, data, presidente_id, nome_avulso)
        SELECT id, data, presidente_id, NULL FROM presidentes
        """
    )
    cursor.execute("DROP TABLE presidentes")
    cursor.execute("ALTER TABLE presidentes_avulso_nova RENAME TO presidentes")
    conn.commit()


TIPOS_EVENTO_PADRAO = [
    "Assembleia de Circuito",
    "Congresso Regional",
    "Visita do Superintendente",
    "Celebração",
    "Reunião Especial",
]

# Nesses eventos a congregação não se reúne no salão: ninguém preside, e o
# rodízio de datas especiais não deve gastar a vez de um ancião com eles.
# É só o palpite inicial — o usuário liga e desliga por tipo na tela.
TIPOS_SEM_PRESIDENTE_LOCAL = {
    "Assembleia de Circuito",
    "Congresso Regional",
    "Reunião Especial",
}

# Estes têm reunião normal no salão, com o presidente da semana: são datas
# marcadas para lembrar o que acontece ali, não eventos com fila própria. O
# "Arranjo Local" é o caso: o discurso é de um orador daqui, e quem preside é
# quem já estava escalado para aquele fim de semana.
TIPOS_FORA_DO_RODIZIO_ESPECIAIS = {
    "Arranjo Local",
}


def _recuperar_presidente_avulso_especiais(cursor) -> None:
    """Traz para a data especial o nome que já estava na semana comum.

    A data especial só aceitava presidente do cadastro, então quem presidiu a
    Celebração ou o discurso especial ficava sem registro ali — mas o nome
    costuma estar gravado na semana comum da mesma data. Traz de lá os dois
    casos: quem está no cadastro (pelo id) e quem foi digitado à mão (pelo
    nome). Só preenche o que está vazio, então rodar de novo não desfaz nada.
    """
    cursor.execute(
        """
        UPDATE datas_especiais SET presidente_id = (
            SELECT p.presidente_id FROM presidentes p
            WHERE p.data = datas_especiais.data AND p.presidente_id IS NOT NULL
        )
        WHERE presidente_id IS NULL
          AND COALESCE(presidente_avulso, '') = ''
        """
    )
    cursor.execute(
        """
        UPDATE datas_especiais SET presidente_avulso = (
            SELECT p.nome_avulso FROM presidentes p
            WHERE p.data = datas_especiais.data
              AND COALESCE(p.nome_avulso, '') <> ''
        )
        WHERE presidente_id IS NULL
          AND COALESCE(presidente_avulso, '') = ''
        """
    )


def _aplicar_padrao_escala_especiais(cursor) -> None:
    """Marca os anciãos do cadastro como presidentes de datas especiais.

    É o critério que valia antes de a escala existir. Serve à migração e à
    restauração de um backup anterior a ela.
    """
    cursor.execute(
        "UPDATE presidentes_cadastro SET preside_especiais = 1 "
        "WHERE categoria = 'Ancião'"
    )


def _migracao_3_rodizio_por_tipo(conn) -> None:
    """Separa "tem presidente local" de "entra no rodízio das datas especiais".

    Eram a mesma coisa, e não são: o Arranjo Local tem reunião normal, com o
    presidente da semana, mas não é um evento com fila própria de anciãos.
    Aparecia como uma fila na aba de datas especiais e podia gastar a vez de
    alguém.
    """
    colunas = [
        linha[1] for linha in conn.execute("PRAGMA table_info(tipos_evento_especial)")
    ]
    if "entra_rodizio" not in colunas:
        conn.execute(
            "ALTER TABLE tipos_evento_especial "
            "ADD COLUMN entra_rodizio INTEGER NOT NULL DEFAULT 1"
        )
    marcadores = ",".join("?" * len(TIPOS_FORA_DO_RODIZIO_ESPECIAIS))
    conn.execute(
        f"UPDATE tipos_evento_especial SET entra_rodizio = 0 WHERE nome IN ({marcadores})",  # noqa: S608
        sorted(TIPOS_FORA_DO_RODIZIO_ESPECIAIS),
    )
    conn.commit()


def _migracao_4_presidente_arquivado(conn) -> None:
    """Presidente sai da escala sem apagar o que ele presidiu.

    Quem se muda de congregação precisa sumir do rodízio e das listas, mas o
    nome dele fica no histórico das semanas e das datas especiais — que é a
    memória de onde o próprio rodízio tira a vez de cada um. Excluir apagava
    as semanas atribuídas e batia em erro quando havia data especial.
    """
    colunas = [
        linha[1] for linha in conn.execute("PRAGMA table_info(presidentes_cadastro)")
    ]
    if "ativo" not in colunas:
        conn.execute(
            "ALTER TABLE presidentes_cadastro "
            "ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1"
        )
    conn.commit()


def _aplicar_padrao_presidente_por_tipo(cursor) -> None:
    """Desliga o presidente local nos tipos em que não há reunião no salão."""
    marcadores = ",".join("?" * len(TIPOS_SEM_PRESIDENTE_LOCAL))
    cursor.execute(
        f"UPDATE tipos_evento_especial SET tem_presidente = 0 WHERE nome IN ({marcadores})",  # noqa: S608
        sorted(TIPOS_SEM_PRESIDENTE_LOCAL),
    )


def _semear_tipos_evento(conn) -> None:
    """Garante os tipos padrão e os já usados em datas especiais.

    O que o usuário removeu não volta: a data antiga continua com o nome do
    evento gravado, mas o tipo não é recriado como opção.
    """
    cursor = conn.cursor()
    usados = [linha[0] for linha in cursor.execute("SELECT DISTINCT tipo FROM datas_especiais")]
    removidos = {
        linha[0] for linha in cursor.execute("SELECT nome FROM tipos_evento_removidos")
    }
    for nome in [*TIPOS_EVENTO_PADRAO, *usados]:
        if nome and nome not in removidos:
            cursor.execute(
                "INSERT OR IGNORE INTO tipos_evento_especial (nome, tem_presidente) "
                "VALUES (?, ?)",
                (nome, 0 if nome in TIPOS_SEM_PRESIDENTE_LOCAL else 1),
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


# A versão do esquema fica gravada no próprio arquivo do banco (PRAGMA
# user_version): é o que diz, sem adivinhação, até onde aquele banco foi
# migrado. Bancos criados antes disso vêm com 0.


def versao_esquema(conn) -> int:
    """Em que versão do esquema está este arquivo de banco."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _marcar_esquema(conn, versao: int) -> None:
    conn.execute(f"PRAGMA user_version = {int(versao)}")
    conn.commit()


# Migrações numeradas. Cada entrada é (versão, função) e roda uma única vez,
# em ordem, nos bancos que ainda não chegaram nela. As mudanças de esquema
# ANTERIORES a esta lista continuam no bloco idempotente de _criar_e_migrar:
# elas se descobrem sozinhas olhando as colunas existentes, e reescrevê-las
# como migrações numeradas exigiria adivinhar em que ponto está cada banco
# instalado por aí.
#
# Daqui para frente é aqui que entra mudança de esquema: uma função nova, o
# próximo número, e o banco de quem atualiza passa por ela uma vez só.
def _migracao_2_convite_enviado(conn) -> None:
    """Quando o convite da designação foi mandado.

    Sem isso, "aguardando confirmação" não dizia desde quando: um convite de
    ontem e um de três semanas atrás eram a mesma linha na tela.
    """
    colunas = [linha[1] for linha in conn.execute("PRAGMA table_info(arranjo_oradores)")]
    if "convidado_em" not in colunas:
        conn.execute("ALTER TABLE arranjo_oradores ADD COLUMN convidado_em TEXT")
    conn.commit()


def _migracao_5_visita_superintendente(conn) -> None:
    """A visita do superintendente: o nome dele e o discurso final.

    O superintendente é sempre o mesmo orador durante a visita, e digitar o
    nome de novo a cada data era trabalho repetido. E a visita tem dois
    discursos — o público e o final —, que o quadro precisa mostrar.
    """
    colunas_config = [linha[1] for linha in conn.execute("PRAGMA table_info(configuracoes)")]
    if "superintendente_circuito" not in colunas_config:
        conn.execute(
            "ALTER TABLE configuracoes "
            "ADD COLUMN superintendente_circuito TEXT DEFAULT ''"
        )
    colunas_especiais = [linha[1] for linha in conn.execute("PRAGMA table_info(datas_especiais)")]
    if "tema_final" not in colunas_especiais:
        conn.execute("ALTER TABLE datas_especiais ADD COLUMN tema_final TEXT")
    conn.commit()


def _migracao_6_sem_arranjo_local(conn) -> None:
    """"Arranjo Local" deixa de ser um tipo de evento especial.

    Não é um evento à parte: é a reunião normal, com o discurso de um orador
    daqui e o presidente da semana já escalado. Como tipo, só rendia uma fila
    vazia na aba de datas especiais. As datas já cadastradas continuam onde
    estão, com o nome gravado.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tipos_evento_removidos (nome TEXT PRIMARY KEY)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO tipos_evento_removidos (nome) VALUES ('Arranjo Local')"
    )
    conn.execute("DELETE FROM tipos_evento_especial WHERE nome = 'Arranjo Local'")
    conn.commit()


MIGRACOES: list[tuple[int, Callable[[sqlite3.Connection], None]]] = [
    (2, _migracao_2_convite_enviado),
    (3, _migracao_3_rodizio_por_tipo),
    (4, _migracao_4_presidente_arquivado),
    (5, _migracao_5_visita_superintendente),
    (6, _migracao_6_sem_arranjo_local),
]

ESQUEMA_ATUAL = MIGRACOES[-1][0] if MIGRACOES else 1


def create_tables(conn):
    """Cria as tabelas e traz o banco até o esquema desta versão do app.

    Roda a cada abertura: o bloco idempotente cria o que falta e levanta
    bancos antigos, as migrações numeradas rodam as pendentes, e o número da
    versão fica gravado no arquivo (``PRAGMA user_version``).
    """
    _criar_e_migrar(conn)
    _aplicar_migracoes_numeradas(conn)
    _marcar_esquema(conn, ESQUEMA_ATUAL)


def _aplicar_migracoes_numeradas(conn) -> None:
    """Roda, em ordem, as migrações que este banco ainda não viu."""
    versao = versao_esquema(conn)
    for numero, migracao in MIGRACOES:
        if versao < numero:
            migracao(conn)
            _marcar_esquema(conn, numero)


def _criar_e_migrar(conn):
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
                CHECK(categoria IN ('Ancião', 'Servo Ministerial')),
            -- Duas escalas independentes. Quem preside a Celebração ou a
            -- visita do superintendente não é necessariamente quem entra no
            -- rodízio de todo fim de semana, e vice-versa: há quem esteja no
            -- cadastro SÓ para as datas especiais.
            preside_normais INTEGER NOT NULL DEFAULT 1,
            preside_especiais INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presidentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            presidente_id INTEGER,
            nome_avulso TEXT,
            FOREIGN KEY (presidente_id) REFERENCES presidentes_cadastro(id)
        )
    """)

    _migrar_presidentes_para_cadastro(conn)
    _migrar_presidentes_avulsos(conn)

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
            -- Na visita do superintendente há dois discursos: o público (o
            -- `tema` acima) e o final. Só a visita usa esta coluna.
            tema_final TEXT,
            presidente_id INTEGER,
            -- Quem presidiu sem estar no cadastro (saiu da congregação, ou
            -- nunca entrou na escala). Mesmo papel do nome_avulso da semana
            -- comum: o nome aparece, mas fica fora dos rodízios.
            presidente_avulso TEXT,
            FOREIGN KEY (presidente_id) REFERENCES presidentes_cadastro(id)
        )
    """)

    # Tipo de evento que o usuário removeu. Sem esta lista ele voltava sozinho
    # na abertura seguinte: a semeadura recria os tipos padrão e todos os que
    # ainda aparecem em alguma data especial já cadastrada.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tipos_evento_removidos (
            nome TEXT PRIMARY KEY
        )
    """)

    # Anotações de um dia: "ligar para o Fulano", "confirmar o orador". São do
    # calendário, e aparecem nas pendências do Início quando a data chega.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anotacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            texto TEXT NOT NULL,
            feita INTEGER NOT NULL DEFAULT 0,
            criada_em TEXT
        )
    """)

    # A congregação muda de dia e/ou horário de reunião de tempos em tempos
    # (a cada dois anos, mais ou menos). A configuração guarda só o vigente, e
    # com isso os meses antigos eram montados no dia de hoje: 2021 era domingo,
    # e a Programação daquele ano procurava sábados. Aqui fica a linha do tempo.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reuniao_historico (
            inicio TEXT PRIMARY KEY,          -- 'AAAA-MM' a partir do qual vale
            dia_semana TEXT NOT NULL,
            horario TEXT NOT NULL DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tipos_evento_especial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            tem_presidente INTEGER NOT NULL DEFAULT 1
        )
    """)
    colunas_tipos = [linha[1] for linha in cursor.execute("PRAGMA table_info(tipos_evento_especial)")]
    if "tem_presidente" not in colunas_tipos:
        cursor.execute(
            "ALTER TABLE tipos_evento_especial "
            "ADD COLUMN tem_presidente INTEGER NOT NULL DEFAULT 1"
        )
        # Só nesta migração: quem já tinha o banco começa com Assembleia,
        # Congresso e Reunião Especial desligados. Depois disso a escolha é do
        # usuário, e rodar de novo não desfaz o que ele mudou.
        _aplicar_padrao_presidente_por_tipo(cursor)
    _semear_tipos_evento(conn)
    _derivar_reuniao_historico(conn)
    _migrar_oradores_fantasma(conn)

    colunas_oradores = [linha[1] for linha in cursor.execute("PRAGMA table_info(oradores)")]
    if "ativo" not in colunas_oradores:
        cursor.execute("ALTER TABLE oradores ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")
    # Nem todo orador é aprovado para discursar FORA da congregação: alguns
    # fazem só o discurso local. Quem só faz local não pode ser oferecido ao
    # montar uma designação enviada. Padrão 1 para não mudar quem já existe.
    if "aprovado_fora" not in colunas_oradores:
        cursor.execute(
            "ALTER TABLE oradores ADD COLUMN aprovado_fora INTEGER NOT NULL DEFAULT 1"
        )

    # O índice de nome único vale só para quem está ATIVO — precisa vir depois
    # da coluna `ativo` existir. Excluir um orador com histórico não apaga o
    # registro, arquiva; o índice antigo pegava todas as linhas e deixava esse
    # arquivado segurando o nome para sempre, então cadastrar de novo (ou
    # renomear alguém para aquele nome) batia num "já existe" apontando para
    # quem não aparece em lugar nenhum.
    criado = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
        ("idx_oradores_nome_congregacao",),
    ).fetchone()
    if criado and "ativo" not in (criado[0] or ""):
        cursor.execute("DROP INDEX idx_oradores_nome_congregacao")
        criado = None
    if not criado:
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_oradores_nome_congregacao
            ON oradores(nome, congregacao_id)
            WHERE COALESCE(ativo, 1) = 1
            """
        )

    # Temas prioritários para a minha congregação (escolha assistida de recebidos).
    colunas_temas = [linha[1] for linha in cursor.execute("PRAGMA table_info(temas)")]
    if "prioritario" not in colunas_temas:
        cursor.execute("ALTER TABLE temas ADD COLUMN prioritario INTEGER NOT NULL DEFAULT 0")


    colunas_especiais = [linha[1] for linha in cursor.execute("PRAGMA table_info(datas_especiais)")]
    if "congregacao_id" not in colunas_especiais:
        cursor.execute("ALTER TABLE datas_especiais ADD COLUMN congregacao_id INTEGER")
    if "presidente_avulso" not in colunas_especiais:
        cursor.execute("ALTER TABLE datas_especiais ADD COLUMN presidente_avulso TEXT")
    _recuperar_presidente_avulso_especiais(cursor)

    colunas_cadastro = [linha[1] for linha in cursor.execute("PRAGMA table_info(presidentes_cadastro)")]
    if "ordem" not in colunas_cadastro:
        cursor.execute("ALTER TABLE presidentes_cadastro ADD COLUMN ordem INTEGER")
        _semear_ordem_presidentes(conn)
    # Telefone: usado para mandar a mensagem da presidência pelo WhatsApp.
    if "telefone" not in colunas_cadastro:
        cursor.execute("ALTER TABLE presidentes_cadastro ADD COLUMN telefone TEXT")
    # Vínculo com um contato da agenda do celular: guardamos a chave estável do
    # contato para reler nome/telefone/foto quando ele mudar no aparelho.
    if "contato_id" not in colunas_cadastro:
        cursor.execute("ALTER TABLE presidentes_cadastro ADD COLUMN contato_id TEXT")
    # Quem já estava no cadastro presidia o fim de semana; e a escala das datas
    # especiais era "os anciãos do cadastro". A migração congela exatamente
    # isso, para nada mudar de comportamento na atualização — daí em diante
    # quem decide são as duas marcações na tela.
    if "preside_normais" not in colunas_cadastro:
        cursor.execute(
            "ALTER TABLE presidentes_cadastro "
            "ADD COLUMN preside_normais INTEGER NOT NULL DEFAULT 1"
        )
    if "preside_especiais" not in colunas_cadastro:
        cursor.execute(
            "ALTER TABLE presidentes_cadastro "
            "ADD COLUMN preside_especiais INTEGER NOT NULL DEFAULT 0"
        )
        _aplicar_padrao_escala_especiais(cursor)
    if "contato_id" not in colunas_oradores:
        cursor.execute("ALTER TABLE oradores ADD COLUMN contato_id TEXT")

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
            circuito TEXT DEFAULT '',
            superintendente_circuito TEXT DEFAULT ''
        )
    """)

    migrar_configuracoes(conn)
    migrar_oradores(conn)
    migrar_arranjos(conn)
    migrar_arranjo_oradores(conn)

    # Status de confirmação das designações (pendente/confirmado/recusado).
    # Registros já existentes são históricos: marcados como confirmados; novos
    # nascem como "pendente" (o coordenador confirma quando o orador responde).
    # Acessibilidade: escala de fonte escolhida pelo usuário.
    colunas_config = [linha[1] for linha in cursor.execute("PRAGMA table_info(configuracoes)")]
    if "escala_fonte" not in colunas_config:
        cursor.execute(
            "ALTER TABLE configuracoes ADD COLUMN escala_fonte REAL NOT NULL DEFAULT 1.0"
        )

    colunas_ao = [linha[1] for linha in cursor.execute("PRAGMA table_info(arranjo_oradores)")]
    if "status" not in colunas_ao:
        cursor.execute(
            "ALTER TABLE arranjo_oradores ADD COLUMN status TEXT NOT NULL DEFAULT 'pendente'"
        )
        cursor.execute("UPDATE arranjo_oradores SET status = 'confirmado'")
    # Simpósio: o mesmo discurso dividido entre dois oradores da congregação.
    # É UM compromisso (uma data, um tema, uma confirmação), então mora numa
    # linha só — antes virava duas, com data e tema repetidos na tela e no
    # quadro impresso.
    if "orador_2_id" not in colunas_ao:
        cursor.execute("ALTER TABLE arranjo_oradores ADD COLUMN orador_2_id INTEGER")

    conn.commit()


def migrar_oradores(conn) -> None:
    """Funde oradores duplicados por nome/congregação — só entre os ATIVOS.

    Um arquivado (``ativo = 0``) pode legitimamente repetir o nome de alguém
    ativo: é o registro antigo, guardado só para as designações passadas não
    perderem o nome. Fundir os dois juntaria históricos de pessoas que podem
    nem ser a mesma, e é justamente o par que o índice único agora permite.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT o2.id, o1.id
        FROM oradores o1
        JOIN oradores o2
          ON o1.nome = o2.nome
         AND COALESCE(o1.congregacao_id, -1) = COALESCE(o2.congregacao_id, -1)
         AND o1.id < o2.id
        WHERE COALESCE(o1.ativo, 1) = 1 AND COALESCE(o2.ativo, 1) = 1
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
        # As designações do arranjo apontam para o orador por chave
        # estrangeira; sem transferir, o DELETE abaixo falha e a abertura do
        # app morre com "FOREIGN KEY constraint failed".
        cursor.execute(
            "UPDATE OR IGNORE arranjo_oradores SET orador_id = ? WHERE orador_id = ?",
            (keep_id, dup_id),
        )
        cursor.execute(
            "UPDATE OR IGNORE arranjo_oradores SET orador_2_id = ? WHERE orador_2_id = ?",
            (keep_id, dup_id),
        )
        cursor.execute("DELETE FROM arranjo_oradores WHERE orador_id = ?", (dup_id,))
        cursor.execute(
            "UPDATE arranjo_oradores SET orador_2_id = NULL WHERE orador_2_id = ?",
            (dup_id,),
        )
        cursor.execute("DELETE FROM oradores WHERE id = ?", (dup_id,))

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


def registrar_convite_enviado(registro_id: int, quando: str | None = None) -> None:
    """Anota que o convite desta designação acabou de ser mandado.

    Só marca a data; quem responde é o orador, e a confirmação continua sendo
    o selo que o coordenador toca quando a resposta chega.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE arranjo_oradores SET convidado_em = ? WHERE id = ?",
            (quando or datetime.now().isoformat(timespec="seconds"), registro_id),
        )
        conn.commit()
    finally:
        conn.close()


def contar_convites_sem_resposta(ano: int, dias: int, hoje: date | None = None) -> int:
    """Quantas designações do ano esperam resposta há ``dias`` ou mais."""
    limite = (hoje or date.today()) - timedelta(days=dias)
    conn = get_connection()
    try:
        linha = conn.execute(
            """
            SELECT COUNT(*)
            FROM arranjo_oradores
            WHERE COALESCE(status, 'pendente') = 'pendente'
              AND convidado_em IS NOT NULL
              AND substr(convidado_em, 1, 10) <= ?
              AND substr(data, 7, 4) = ?
            """,
            (limite.isoformat(), str(ano)),
        ).fetchone()
        return int(linha[0] or 0)
    finally:
        conn.close()


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
                   COALESCE(ao.status, 'pendente') AS status,
                   ao.convidado_em,
                   COALESCE(o.nome, '') AS orador_nome,
                   ao.orador_2_id,
                   COALESCE(o2.nome, '') AS orador_2_nome,
                   COALESCE(t.titulo, '') AS tema_titulo,
                   COALESCE(c.nome, '') AS congregacao_nome
            FROM arranjo_oradores ao
            JOIN oradores o ON ao.orador_id = o.id
            LEFT JOIN oradores o2 ON ao.orador_2_id = o2.id
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
    orador_2_id: int | None = None,
) -> None:
    """Adiciona orador recebido ou enviado em um arranjo mensal.

    ``orador_2_id`` marca um SIMPÓSIO: o mesmo discurso dividido entre dois
    oradores da congregação. É um compromisso só (uma data, um tema, uma
    confirmação), por isso ocupa uma linha só.
    """
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
                arranjo_id, tipo, orador_id, tema_nr, congregacao_id, data,
                orador_2_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (arranjo_id, tipo, orador_id, tema_nr, congregacao_id, data,
             orador_2_id),
        )
        conn.commit()
        sincronizar_uso_temas(conn)
    finally:
        conn.close()


def sincronizar_uso_temas(conn=None) -> int:
    """Reflete no catálogo de Temas os discursos RECEBIDOS já programados.

    Um orador recebido apresenta o tema na nossa congregação, então a data
    aparece na coluna do ano correspondente (formato MM/AAAA) — é o que o
    coordenador vê em "Último uso". Designações enviadas não contam: o tema foi
    apresentado em outra congregação.

    Não apaga nada que já esteja preenchido (uso histórico importado da
    planilha/S-99): só grava as datas vindas dos arranjos, mantendo a mais
    recente quando há mais de uma no mesmo ano. Devolve quantas células gravou.
    """
    proprio = conn is None
    conn = get_connection() if proprio else conn
    try:
        cursor = conn.cursor()
        linhas = cursor.execute(
            """
            SELECT tema_nr, data
            FROM arranjo_oradores
            WHERE tipo = 'recebido' AND tema_nr IS NOT NULL
              AND data IS NOT NULL AND length(data) = 10
            """
        ).fetchall()

        # Por (tema, ano), guarda o mês mais recente.
        melhor: dict[tuple[int, int], str] = {}
        for tema_nr, data in linhas:
            try:
                mes, ano = int(data[3:5]), int(data[6:10])
            except ValueError:
                continue
            chave = (int(tema_nr), ano)
            if chave not in melhor or mes > int(melhor[chave][:2]):
                melhor[chave] = f"{mes:02d}/{ano}"

        gravadas = 0
        for (tema_nr, ano), valor in melhor.items():
            # A coluna do ano precisa existir para aparecer na tela de Temas.
            cursor.execute(
                """
                INSERT INTO temas_anos_colunas (ano, visivel, ordem)
                VALUES (?, 1, (SELECT COALESCE(MAX(ordem), -1) + 1 FROM temas_anos_colunas))
                ON CONFLICT(ano) DO NOTHING
                """,
                (ano,),
            )
            cursor.execute(
                """
                INSERT INTO tema_uso_por_ano (tema_nr, ano_coluna, data_uso)
                VALUES (?, ?, ?)
                ON CONFLICT(tema_nr, ano_coluna) DO UPDATE SET data_uso = excluded.data_uso
                """,
                (tema_nr, ano, valor),
            )
            gravadas += 1
        conn.commit()
        return gravadas
    finally:
        if proprio:
            conn.close()


def realocar_uso_para_ano_da_data(conn=None) -> int:
    """Põe cada data de uso na coluna do ano a que ela pertence.

    A carga vinda da planilha/S-99 gravava as datas em colunas posicionais
    ("1ª data usada", "2ª data usada"), então um uso de 04/2025 podia acabar
    embaixo de 2023 — e sumia da grade quando essa coluna era ocultada, dando
    a impressão de que o tema nunca foi feito.

    Cada registro passa a ficar na coluna do próprio ano. Como a tabela guarda
    uma data por ano, quando o tema tem mais de um uso no mesmo ano fica o mais
    recente. Devolve quantos registros mudaram de coluna.
    """
    proprio = conn is None
    conn = get_connection() if proprio else conn
    try:
        cursor = conn.cursor()
        linhas = cursor.execute(
            "SELECT tema_nr, ano_coluna, data_uso FROM tema_uso_por_ano"
        ).fetchall()

        # Por (tema, ano da data), guarda a data mais recente.
        melhor: dict[tuple[int, int], str] = {}
        fora_do_lugar = 0
        origens: list[tuple[int, int]] = []
        for tema_nr, ano_coluna, data_uso in linhas:
            chave = _chave_mes_ano(data_uso)
            if not chave:
                # Texto que não é data (ou célula vazia): fica onde está.
                continue
            ano = int(chave[0:4])
            origens.append((int(tema_nr), int(ano_coluna)))
            if int(ano_coluna) != ano:
                fora_do_lugar += 1
            alvo = (int(tema_nr), ano)
            if alvo not in melhor or chave > melhor[alvo]:
                melhor[alvo] = chave

        if not fora_do_lugar:
            return 0

        for tema_nr, ano_coluna in origens:
            cursor.execute(
                "DELETE FROM tema_uso_por_ano WHERE tema_nr = ? AND ano_coluna = ?",
                (tema_nr, ano_coluna),
            )
        for (tema_nr, ano), chave in melhor.items():
            # A coluna do ano precisa existir para o uso aparecer na tela.
            cursor.execute(
                """
                INSERT INTO temas_anos_colunas (ano, visivel, ordem)
                VALUES (?, 1, (SELECT COALESCE(MAX(ordem), -1) + 1 FROM temas_anos_colunas))
                ON CONFLICT(ano) DO NOTHING
                """,
                (ano,),
            )
            cursor.execute(
                """
                INSERT INTO tema_uso_por_ano (tema_nr, ano_coluna, data_uso)
                VALUES (?, ?, ?)
                ON CONFLICT(tema_nr, ano_coluna) DO UPDATE SET data_uso = excluded.data_uso
                """,
                (tema_nr, ano, f"{chave[5:7]}/{chave[0:4]}"),
            )
        conn.commit()
        return fora_do_lugar
    finally:
        if proprio:
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
    orador_2_id: int | None = None,
) -> None:
    """Atualiza data, tema, congregação e o 2º orador (simpósio) do registro."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE arranjo_oradores
            SET tema_nr = ?, congregacao_id = ?, data = ?, orador_2_id = ?
            WHERE id = ?
            """,
            (tema_nr, congregacao_id, data, orador_2_id, registro_id),
        )
        conn.commit()
        sincronizar_uso_temas(conn)
    finally:
        conn.close()


def trocar_datas_designacoes(id_a: int, id_b: int) -> None:
    """Troca as datas entre dois registros de arranjo_oradores (swap).

    Feito em três passos na mesma transação por causa da UNIQUE
    (arranjo_id, tipo, orador_id, data).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        linha_a = cursor.execute(
            "SELECT data FROM arranjo_oradores WHERE id = ?", (id_a,)
        ).fetchone()
        linha_b = cursor.execute(
            "SELECT data FROM arranjo_oradores WHERE id = ?", (id_b,)
        ).fetchone()
        if not linha_a or not linha_b:
            return
        data_a, data_b = linha_a[0], linha_b[0]
        cursor.execute("UPDATE arranjo_oradores SET data = NULL WHERE id = ?", (id_a,))
        cursor.execute("UPDATE arranjo_oradores SET data = ? WHERE id = ?", (data_a, id_b))
        cursor.execute("UPDATE arranjo_oradores SET data = ? WHERE id = ?", (data_b, id_a))
        conn.commit()
    finally:
        conn.close()


def atualizar_data_designacao(registro_id: int, data: str | None) -> None:
    """Move um registro de arranjo_oradores para outra data."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE arranjo_oradores SET data = ? WHERE id = ?",
            (data, registro_id),
        )
        conn.commit()
    finally:
        conn.close()


def redistribuir_datas_designacoes(pares: list[tuple[int, str]]) -> None:
    """Regrava de uma vez a data de várias designações.

    Passa todas por NULL antes de gravar: com o mesmo orador em duas datas do
    mês, uma troca esbarraria no índice único (arranjo, tipo, orador, data) no
    meio do caminho, mesmo que o resultado final seja válido.
    """
    if not pares:
        return
    conn = get_connection()
    try:
        ids = [int(registro_id) for registro_id, _ in pares]
        marcadores = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE arranjo_oradores SET data = NULL WHERE id IN ({marcadores})",  # noqa: S608
            ids,
        )
        for registro_id, data in pares:
            conn.execute(
                "UPDATE arranjo_oradores SET data = ? WHERE id = ?",
                (data, int(registro_id)),
            )
        conn.commit()
    finally:
        conn.close()


STATUS_DESIGNACAO = ("pendente", "confirmado", "recusado")


def atualizar_status_orador_arranjo(registro_id: int, status: str) -> None:
    """Define o status de confirmação de uma designação (pendente/confirmado/recusado)."""
    if status not in STATUS_DESIGNACAO:
        status = "pendente"
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE arranjo_oradores SET status = ? WHERE id = ?",
            (status, registro_id),
        )
        conn.commit()
    finally:
        conn.close()


def contar_designacoes_por_status(ano: int) -> dict[str, int]:
    """Conta as designações do ano por status (pendente/confirmado/recusado)."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT COALESCE(ao.status, 'pendente') AS status, COUNT(*)
            FROM arranjo_oradores ao
            JOIN arranjos a ON ao.arranjo_id = a.id
            WHERE a.ano = ?
            GROUP BY COALESCE(ao.status, 'pendente')
            """,
            (ano,),
        )
        return {linha[0]: int(linha[1]) for linha in cursor.fetchall()}
    finally:
        conn.close()


def ultima_data_discurso_por_orador() -> dict[int, str]:
    """Última data (DD/MM/AAAA) em que cada orador foi enviado para discursar.

    Considera os registros do tipo 'enviado' (oradores da minha congregação
    mandados a outra). Usado para sugerir quem está há mais tempo sem discursar.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT orador_id, data
            FROM arranjo_oradores
            WHERE tipo = 'enviado' AND data IS NOT NULL AND data <> ''
            """
        )
        ultima: dict[int, str] = {}
        for orador_id, data in cursor.fetchall():
            chave = (data[6:10], data[3:5], data[0:2])
            atual = ultima.get(orador_id)
            if atual is None or chave > (atual[6:10], atual[3:5], atual[0:2]):
                ultima[orador_id] = data
        return ultima
    finally:
        conn.close()


def relatorio_frequencia_oradores(congregacao_id: int | None = None) -> list[dict]:
    """Frequência de discursos (enviados) por orador ativo.

    Retorna [{nome, quantidade, ultima_data}] ordenado de quem discursou menos
    (e há mais tempo) para o que mais discursou. Se ``congregacao_id`` for dado,
    limita aos oradores daquela congregação (ex.: a minha).
    """
    conn = get_connection()
    try:
        query = """
            SELECT o.id, o.nome,
                   COUNT(ao.id) AS quantidade,
                   MAX(
                       substr(ao.data, 7, 4) || substr(ao.data, 4, 2)
                       || substr(ao.data, 1, 2)
                   ) AS ultima_chave
            FROM oradores o
            LEFT JOIN arranjo_oradores ao
                ON ao.orador_id = o.id AND ao.tipo = 'enviado'
                   AND ao.data IS NOT NULL AND ao.data <> ''
            WHERE COALESCE(o.ativo, 1) = 1
        """
        params: list = []
        if congregacao_id is not None:
            query += " AND o.congregacao_id = ?"
            params.append(congregacao_id)
        query += " GROUP BY o.id, o.nome"
        linhas = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    def _data_de_chave(chave: str | None) -> str:
        if not chave or len(chave) != 8:
            return ""
        return f"{chave[6:8]}/{chave[4:6]}/{chave[0:4]}"

    resultado = [
        {
            "id": _id,
            "nome": nome,
            "quantidade": int(quantidade or 0),
            "ultima_data": _data_de_chave(ultima_chave),
            "_ordem": ultima_chave or "",
        }
        for _id, nome, quantidade, ultima_chave in linhas
    ]
    # Menos discursos primeiro; empate: quem discursou há mais tempo (ou nunca).
    resultado.sort(key=lambda r: (r["quantidade"], r["_ordem"], r["nome"]))
    for item in resultado:
        del item["_ordem"]
    return resultado


def _data_de_chave_ordenavel(chave: str | None) -> str:
    """Converte a chave AAAAMMDD usada nas agregações de volta em DD/MM/AAAA."""
    if not chave or len(chave) != 8:
        return ""
    return f"{chave[6:8]}/{chave[4:6]}/{chave[0:4]}"


def listar_vinculos_de_contato() -> list[dict]:
    """Quem está vinculado a um contato da agenda, para reler do aparelho.

    Devolve ``[{tabela, id, contato_id, nome, telefone}]`` juntando oradores e
    presidentes — quem chama pergunta ao celular e manda de volta em
    ``atualizar_por_contato``.
    """
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT 'oradores', id, contato_id, nome, COALESCE(telefone, '')
            FROM oradores
            WHERE contato_id IS NOT NULL AND contato_id <> ''
            UNION ALL
            SELECT 'presidentes_cadastro', id, contato_id, nome, COALESCE(telefone, '')
            FROM presidentes_cadastro
            WHERE contato_id IS NOT NULL AND contato_id <> ''
            """
        ).fetchall()
        return [
            {
                "tabela": linha[0],
                "id": linha[1],
                "contato_id": linha[2],
                "nome": linha[3],
                "telefone": linha[4],
            }
            for linha in linhas
        ]
    finally:
        conn.close()


def definir_contato_vinculado(
    tabela: str, registro_id: int, contato_id: str | None
) -> None:
    """Amarra (ou solta) uma pessoa a um contato da agenda."""
    if tabela not in ("oradores", "presidentes_cadastro"):
        raise ValueError(f"Tabela inválida para vínculo de contato: {tabela}")
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE {tabela} SET contato_id = ? WHERE id = ?",  # noqa: S608 — nome validado acima
            (contato_id or None, registro_id),
        )
        conn.commit()
    finally:
        conn.close()


def atualizar_telefone_por_contato(tabela: str, registro_id: int, telefone: str) -> int:
    """Grava o telefone que veio da agenda; devolve 1 se algo mudou.

    Só escreve quando o número realmente mudou — assim a sincronização silenciosa
    não fica marcando o banco como alterado a cada abertura do app.
    """
    if tabela not in ("oradores", "presidentes_cadastro"):
        raise ValueError(f"Tabela inválida para vínculo de contato: {tabela}")
    conn = get_connection()
    try:
        atual = conn.execute(
            f"SELECT COALESCE(telefone, '') FROM {tabela} WHERE id = ?",  # noqa: S608
            (registro_id,),
        ).fetchone()
        if not atual or atual[0] == telefone:
            return 0
        conn.execute(
            f"UPDATE {tabela} SET telefone = ? WHERE id = ?",  # noqa: S608
            (telefone, registro_id),
        )
        conn.commit()
        return 1
    finally:
        conn.close()


def relatorio_presidencias(ano: int | None = None) -> list[dict]:
    """Quantas vezes cada presidente já presidiu, e quando foi a última.

    Sem ``ano``, conta a vida toda; com ``ano``, só aquele. Ordena de quem
    presidiu menos (e há mais tempo) para quem presidiu mais — é a leitura que
    mostra o desequilíbrio do rodízio de relance.
    """
    conn = get_connection()
    try:
        # O filtro do ano vai no JOIN (e não no WHERE) para quem ainda não
        # presidiu continuar aparecendo, com zero. A subconsulta junta as
        # semanas normais com as datas especiais que têm presidente — presidir
        # o discurso especial conta igual.
        filtro_ano = " AND substr(p.data, 7, 4) = ?" if ano is not None else ""
        params = [str(ano)] if ano is not None else []
        linhas = conn.execute(
            f"""
            SELECT c.id, c.nome, c.categoria,
                   COUNT(p.data) AS quantidade,
                   MAX(
                       substr(p.data, 7, 4) || substr(p.data, 4, 2)
                       || substr(p.data, 1, 2)
                   ) AS ultima_chave
            FROM presidentes_cadastro c
            LEFT JOIN (
                SELECT data, presidente_id FROM presidentes
                UNION
                SELECT data, presidente_id FROM datas_especiais
                WHERE presidente_id IS NOT NULL
            ) p ON p.presidente_id = c.id{filtro_ano}
            GROUP BY c.id, c.nome, c.categoria
            """,  # noqa: S608 — filtro_ano é literal fixo, sem dado do usuário
            params,
        ).fetchall()
    finally:
        conn.close()

    resultado = [
        {
            "id": _id,
            "nome": nome,
            "categoria": categoria or "",
            "quantidade": int(quantidade or 0),
            "ultima_data": _data_de_chave_ordenavel(ultima_chave),
            "_ordem": ultima_chave or "",
        }
        for _id, nome, categoria, quantidade, ultima_chave in linhas
    ]
    resultado.sort(key=lambda r: (r["quantidade"], r["_ordem"], r["nome"]))
    for item in resultado:
        del item["_ordem"]
    return resultado


def carregar_designacoes_ano(ano: int) -> list[dict]:
    """Todos os registros (recebido/enviado) do ano com data e orador.

    Usado para detectar conflitos (mesmo orador na mesma data). O segundo
    orador do simpósio entra como uma linha própria: ele também não pode estar
    designado em dois lugares no mesmo dia.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT ao.data, ao.orador_id, ao.tipo, COALESCE(o.nome, '') AS orador_nome
            FROM arranjo_oradores ao
            JOIN arranjos a ON ao.arranjo_id = a.id
            JOIN oradores o ON ao.orador_id = o.id
            WHERE a.ano = ? AND ao.data IS NOT NULL AND ao.data <> ''
            UNION ALL
            SELECT ao.data, ao.orador_2_id, ao.tipo, COALESCE(o2.nome, '')
            FROM arranjo_oradores ao
            JOIN arranjos a ON ao.arranjo_id = a.id
            JOIN oradores o2 ON ao.orador_2_id = o2.id
            WHERE a.ano = ? AND ao.data IS NOT NULL AND ao.data <> ''
            """,
            (ano, ano),
        )
        colunas = [desc[0] for desc in cursor.description]
        return [dict(zip(colunas, row)) for row in cursor.fetchall()]
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


def carregar_arranjos_por_ano(ano: int | None) -> list[dict]:
    """Carrega arranjos de um ano com dados da congregação anfitriã.

    Sem ``ano``, traz os de todos os anos — é o que a busca da Programação
    usa para saber quais meses já existem.
    """
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
            WHERE (? IS NULL OR a.ano = ?)
            ORDER BY a.ano, a.mes_inicio
            """,
            (ano, ano),
        )
        colunas = [desc[0] for desc in cursor.description]
        return [dict(zip(colunas, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def listar_itens_programacao(ano: int | None = None) -> list[dict]:
    """Tudo o que está marcado na programação, em uma lista só.

    Serve à busca da tela de Programação: orador recebido, designação
    enviada, presidente da semana e data especial viram linhas do mesmo
    formato, para procurar por nome, tema ou congregação sem abrir mês por
    mês. Sem ``ano``, traz todos.
    """
    filtro_ano = "" if ano is None else " AND substr({coluna}, 7, 4) = :ano"
    parametros = {} if ano is None else {"ano": str(ano)}
    conn = get_connection()
    try:
        itens: list[dict] = []
        for linha in conn.execute(
            f"""
            SELECT ao.data,
                   ao.tipo,
                   COALESCE(o.nome, '') AS orador,
                   COALESCE(o2.nome, '') AS orador_2,
                   ao.tema_nr,
                   COALESCE(t.titulo, '') AS tema_titulo,
                   COALESCE(c.nome, '') AS congregacao
            FROM arranjo_oradores ao
            LEFT JOIN oradores o ON ao.orador_id = o.id
            LEFT JOIN oradores o2 ON ao.orador_2_id = o2.id
            LEFT JOIN temas t ON ao.tema_nr = t.nr
            LEFT JOIN congregacoes c ON ao.congregacao_id = c.id
            WHERE length(COALESCE(ao.data, '')) = 10
            {filtro_ano.format(coluna="ao.data")}
            """,  # noqa: S608 — o filtro é fixo, o ano vai por parâmetro
            parametros,
        ):
            nome = linha[2]
            if linha[3]:
                nome = f"{nome}{SEPARADOR_SIMPOSIO}{linha[3]}"
            itens.append(
                {
                    "data": linha[0],
                    "categoria": (
                        "Orador recebido" if linha[1] == "recebido"
                        else "Designação enviada"
                    ),
                    "pessoa": nome,
                    "tema_nr": linha[4],
                    "tema_titulo": linha[5],
                    "congregacao": linha[6],
                }
            )

        for linha in conn.execute(
            f"""
            SELECT p.data, COALESCE(pc.nome, p.nome_avulso, '')
            FROM presidentes p
            LEFT JOIN presidentes_cadastro pc ON p.presidente_id = pc.id
            WHERE length(COALESCE(p.data, '')) = 10
            {filtro_ano.format(coluna="p.data")}
            """,  # noqa: S608
            parametros,
        ):
            itens.append(
                {
                    "data": linha[0],
                    "categoria": "Presidente",
                    "pessoa": linha[1],
                    "tema_nr": None,
                    "tema_titulo": "",
                    "congregacao": "",
                }
            )

        for linha in conn.execute(
            f"""
            SELECT e.data, e.tipo,
                   COALESCE(e.orador, ''),
                   COALESCE(e.tema, ''),
                   COALESCE(e.tema_final, ''),
                   COALESCE(cong.nome, ''),
                   COALESCE(pc.nome, e.presidente_avulso, '')
            FROM datas_especiais e
            LEFT JOIN congregacoes cong ON e.congregacao_id = cong.id
            LEFT JOIN presidentes_cadastro pc ON e.presidente_id = pc.id
            WHERE length(COALESCE(e.data, '')) = 10
            {filtro_ano.format(coluna="e.data")}
            """,  # noqa: S608
            parametros,
        ):
            tema = " · ".join(parte for parte in (linha[3], linha[4]) if parte)
            pessoa = " · ".join(parte for parte in (linha[2], linha[6]) if parte)
            itens.append(
                {
                    "data": linha[0],
                    "categoria": linha[1],
                    "pessoa": pessoa,
                    "tema_nr": None,
                    "tema_titulo": tema,
                    "congregacao": linha[5],
                }
            )
        return sorted(itens, key=lambda i: (i["data"][6:10], i["data"][3:5], i["data"][0:2]))
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
                   COALESCE(t.titulo, '') AS tema,
                   COALESCE(c.nome, '') AS congregacao
            FROM arranjo_oradores ao
            JOIN oradores o ON ao.orador_id = o.id
            LEFT JOIN temas t ON ao.tema_nr = t.nr
            LEFT JOIN congregacoes c ON ao.congregacao_id = c.id
            WHERE ao.tipo = 'recebido' AND substr(ao.data, 7, 4) = ?
            """,
            (str(ano),),
        ).fetchall()
        return {
            linha[0]: {
                "orador": linha[1],
                "tema_nr": linha[2],
                "tema": linha[3],
                # De onde o orador vem — vai na mensagem da presidência.
                "congregacao": linha[4],
            }
            for linha in linhas
        }
    finally:
        conn.close()


def carregar_escala_fonte() -> float:
    """Escala de fonte salva (1.0 = padrão). Defensiva: nunca quebra a abertura."""
    try:
        conn = get_connection()
        try:
            linha = conn.execute(
                "SELECT COALESCE(escala_fonte, 1.0) FROM configuracoes WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()
        return float(linha[0]) if linha and linha[0] else 1.0
    except Exception:  # noqa: BLE001 — banco antigo/sem a coluna: usa o padrão
        return 1.0


def salvar_escala_fonte(escala: float) -> None:
    """Guarda a escala de fonte escolhida pelo usuário.

    Upsert: um UPDATE puro não gravaria nada enquanto a linha única de
    `configuracoes` (id = 1) ainda não existisse — caso de instalação nova.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO configuracoes (id, escala_fonte) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET escala_fonte = excluded.escala_fonte
            """,
            (float(escala),),
        )
        conn.commit()
    finally:
        conn.close()


def definir_tema_prioritario(nr: int, prioritario: bool) -> None:
    """Marca/desmarca um tema como prioritário para a minha congregação."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE temas SET prioritario = ? WHERE nr = ?",
            (1 if prioritario else 0, nr),
        )
        conn.commit()
    finally:
        conn.close()


def oradores_com_temas_da_congregacao(congregacao_id: int) -> list[dict]:
    """Oradores ativos de uma congregação, com os temas que podem fazer.

    Retorna [{id, nome, observacoes, temas: [nr, ...]}] — base da escolha
    assistida de recebidos (a lista que o irmão da anfitriã envia fica
    registrada no cadastro de oradores dela).
    """
    conn = get_connection()
    try:
        oradores = conn.execute(
            """
            SELECT id, nome, COALESCE(observacoes, '') AS observacoes
            FROM oradores
            WHERE congregacao_id = ? AND COALESCE(ativo, 1) = 1
            ORDER BY nome
            """,
            (congregacao_id,),
        ).fetchall()
        temas_por_orador: dict[int, list[int]] = {}
        for orador_id, tema_nr in conn.execute(
            """
            SELECT ot.orador_id, ot.tema_nr
            FROM orador_temas ot
            JOIN oradores o ON o.id = ot.orador_id
            WHERE o.congregacao_id = ?
            ORDER BY ot.tema_nr
            """,
            (congregacao_id,),
        ):
            temas_por_orador.setdefault(orador_id, []).append(int(tema_nr))
        return [
            {
                "id": int(oid),
                "nome": nome,
                "observacoes": obs,
                "temas": temas_por_orador.get(int(oid), []),
            }
            for oid, nome, obs in oradores
        ]
    finally:
        conn.close()


def carregar_enviados_por_ano(ano: int) -> dict[str, list[dict]]:
    """Designações enviadas no ano, indexadas por data (DD/MM/AAAA).

    Cada data pode ter mais de um envio (oradores em congregações diferentes),
    por isso o valor é uma lista.
    """
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT ao.data,
                   COALESCE(o.nome, '') AS orador,
                   ao.tema_nr,
                   COALESCE(t.titulo, '') AS tema,
                   COALESCE(c.nome, '') AS congregacao,
                   COALESCE(ao.status, 'pendente') AS status
            FROM arranjo_oradores ao
            JOIN oradores o ON ao.orador_id = o.id
            LEFT JOIN temas t ON ao.tema_nr = t.nr
            LEFT JOIN congregacoes c ON ao.congregacao_id = c.id
            WHERE ao.tipo = 'enviado' AND substr(ao.data, 7, 4) = ?
            ORDER BY o.nome
            """,
            (str(ano),),
        ).fetchall()
        resultado: dict[str, list[dict]] = {}
        for data, orador, tema_nr, tema, congregacao, status in linhas:
            resultado.setdefault(data, []).append(
                {
                    "orador": orador,
                    "tema_nr": tema_nr,
                    "tema": tema,
                    "congregacao": congregacao,
                    "status": status,
                }
            )
        return resultado
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


def carregar_temas_com_titulo_de_orador(orador_id: int) -> list[tuple[int, str]]:
    """Temas que o orador tem preparados, com título — [(nr, titulo)].

    O número sozinho não diz nada para quem está montando o arranjo; é o
    título que responde "ele pode fazer este discurso?".
    """
    conn = get_connection()
    try:
        return [
            (int(nr), titulo or "")
            for nr, titulo in conn.execute(
                """
                SELECT ot.tema_nr, t.titulo
                FROM orador_temas ot
                LEFT JOIN temas t ON t.nr = ot.tema_nr
                WHERE ot.orador_id = ?
                ORDER BY ot.tema_nr
                """,
                (orador_id,),
            )
        ]
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
    contato_id: str | None = None,
    aprovado_fora: bool = True,
) -> int:
    """Cria ou atualiza um orador e os temas que ele pode apresentar.

    ``contato_id`` amarra o orador a um contato da agenda do celular, para o
    telefone acompanhar sozinho o que mudar lá.

    ``aprovado_fora=False`` marca quem faz só o discurso local: ele fica de
    fora da lista de oradores oferecida a outras congregações (no arranjo do
    mês continua disponível).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if orador_id:
            cursor.execute(
                """
                UPDATE oradores
                SET nome = ?, telefone = ?, categoria = ?, congregacao_id = ?,
                    observacoes = ?, contato_id = ?, aprovado_fora = ?
                WHERE id = ?
                """,
                (nome, telefone, categoria, congregacao_id, observacoes,
                 contato_id or None, 1 if aprovado_fora else 0, orador_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO oradores (
                    nome, telefone, categoria, congregacao_id, observacoes,
                    contato_id, aprovado_fora
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (nome, telefone, categoria, congregacao_id, observacoes,
                 contato_id or None, 1 if aprovado_fora else 0),
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
        # `orador_2_id` é a segunda metade de um simpósio: quem só apareceu
        # ali também tem histórico, e apagá-lo deixaria a designação sem nome.
        tem_historico = conn.execute(
            """
            SELECT EXISTS(
                    SELECT 1 FROM arranjo_oradores
                    WHERE orador_id = ? OR orador_2_id = ?
                )
                OR EXISTS(SELECT 1 FROM designacoes WHERE orador_id = ? OR presidente_id = ?)
            """,
            (orador_id, orador_id, orador_id, orador_id),
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
    """Retorna os presidentes designados no ano, indexados por data (DD/MM/AAAA).

    Inclui os avulsos (nome digitado à mão, de quem não está no cadastro):
    eles vêm com ``presidente_id`` nulo, ``avulso=True`` e sem telefone.
    """
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT p.id, p.data, p.presidente_id,
                   COALESCE(c.nome, p.nome_avulso, '') AS nome,
                   COALESCE(c.telefone, '') AS telefone
            FROM presidentes p
            LEFT JOIN presidentes_cadastro c ON p.presidente_id = c.id
            WHERE substr(p.data, 7, 4) = ?
              AND (c.id IS NOT NULL OR COALESCE(p.nome_avulso, '') <> '')
            """,
            (str(ano),),
        ).fetchall()
        return {
            linha[1]: {
                "id": linha[0],
                "data": linha[1],
                "presidente_id": linha[2],
                "nome": linha[3],
                # Destino da mensagem da presidência enviada da tela inicial.
                "telefone": linha[4],
                "avulso": linha[2] is None,
            }
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
            INSERT INTO presidentes (data, presidente_id, nome_avulso)
            VALUES (?, ?, NULL)
            ON CONFLICT(data) DO UPDATE SET
                presidente_id = excluded.presidente_id,
                nome_avulso = NULL
            """,
            (data, presidente_id),
        )
        conn.commit()
    finally:
        conn.close()


def salvar_presidente_avulso(data: str, nome: str) -> None:
    """Grava um presidente pelo NOME, para quem não está no cadastro.

    Serve para tapar a semana de quem saiu da congregação: o nome aparece na
    programação e no quadro, mas fica FORA do revezamento — não conta como
    "presidiu" para o rodízio nem para o relatório de presidências, porque
    essa pessoa não está mais na escala.
    """
    nome_limpo = (nome or "").strip()
    if not nome_limpo:
        raise ValueError("O nome do presidente avulso não pode ser vazio.")
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO presidentes (data, presidente_id, nome_avulso)
            VALUES (?, NULL, ?)
            ON CONFLICT(data) DO UPDATE SET
                presidente_id = NULL,
                nome_avulso = excluded.nome_avulso
            """,
            (data, nome_limpo),
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


def listar_presidentes_cadastro(
    escala: str | None = None, incluir_arquivados: bool = False
) -> list[dict]:
    """Lista o cadastro de presidentes na ordem da rotação.

    ``escala`` filtra por quem serve para quê: ``"normais"`` traz quem preside
    a reunião de todo fim de semana, ``"especiais"`` traz quem preside a
    Celebração, a visita do superintendente e afins. Sem ``escala``, traz o
    cadastro inteiro — é o que a tela de Presidentes mostra.

    Quem foi arquivado (mudou de congregação, por exemplo) fica de fora, a não
    ser que ``incluir_arquivados`` peça o contrário. O histórico dele continua
    intacto: os nomes das semanas e das datas especiais vêm por junção, não
    desta lista.
    """
    filtros = {
        "normais": "COALESCE(preside_normais, 1) = 1",
        "especiais": "COALESCE(preside_especiais, 0) = 1",
    }
    condicoes = [filtros[escala]] if escala in filtros else []
    if not incluir_arquivados:
        condicoes.append("COALESCE(ativo, 1) = 1")
    onde = f" WHERE {' AND '.join(condicoes)}" if condicoes else ""
    conn = get_connection()
    try:
        linhas = conn.execute(
            "SELECT id, nome, categoria, ordem, COALESCE(telefone, ''), "
            "COALESCE(contato_id, ''), COALESCE(preside_normais, 1), "
            "COALESCE(preside_especiais, 0), COALESCE(ativo, 1) "
            f"FROM presidentes_cadastro{onde} "  # noqa: S608 — literal fixo
            "ORDER BY COALESCE(ordem, 999999), nome"
        ).fetchall()
        return [
            {
                "id": linha[0],
                "nome": linha[1],
                "categoria": linha[2],
                "ordem": linha[3],
                "telefone": linha[4],
                "contato_id": linha[5],
                "preside_normais": bool(linha[6]),
                "preside_especiais": bool(linha[7]),
                "ativo": bool(linha[8]),
            }
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


def carregar_todas_designacoes_presidente() -> dict[str, int | None]:
    """Todas as vezes que alguém presidiu: {data (DD/MM/AAAA): presidente_id}.

    Inclui as **datas especiais** com presidente (discurso especial, visita do
    superintendente). Sem elas o rodízio ficava cego: quem presidiu o discurso
    especial parecia não presidir há muito tempo e era escolhido logo na semana
    seguinte. Se a mesma data estiver nos dois lugares, vale a data especial —
    é lá que ela é gerenciada.

    Os presidentes **avulsos** (nome digitado, fora do cadastro) entram com
    ``None``: a data conta como ocupada — o rodízio não tenta preenchê-la de
    novo — mas ninguém do revezamento fica "devendo" por ela.
    """
    conn = get_connection()
    try:
        designacoes = {
            linha[0]: linha[1]
            for linha in conn.execute(
                "SELECT data, presidente_id FROM presidentes "
                "WHERE presidente_id IS NOT NULL OR COALESCE(nome_avulso, '') <> ''"
            )
        }
        designacoes.update(
            {
                linha[0]: linha[1]
                for linha in conn.execute(
                    "SELECT data, presidente_id FROM datas_especiais "
                    "WHERE presidente_id IS NOT NULL "
                    "   OR COALESCE(presidente_avulso, '') <> ''"
                )
            }
        )
        return designacoes
    finally:
        conn.close()


def listar_anotacoes(data: str | None = None, incluir_feitas: bool = True) -> list[dict]:
    """Anotações de um dia (DD/MM/AAAA) ou de todos, em ordem de calendário."""
    condicoes, params = [], []
    if data:
        condicoes.append("data = ?")
        params.append(data)
    if not incluir_feitas:
        condicoes.append("COALESCE(feita, 0) = 0")
    onde = f" WHERE {' AND '.join(condicoes)}" if condicoes else ""
    conn = get_connection()
    try:
        return [
            {"id": linha[0], "data": linha[1], "texto": linha[2], "feita": bool(linha[3])}
            for linha in conn.execute(
                "SELECT id, data, texto, COALESCE(feita, 0) FROM anotacoes"  # noqa: S608
                f"{onde} ORDER BY substr(data, 7, 4) || substr(data, 4, 2) "
                "|| substr(data, 1, 2), id",
                params,
            )
        ]
    finally:
        conn.close()


def anotacoes_ate(data_limite: str) -> list[dict]:
    """Anotações ainda não feitas cuja data já chegou (ou passou).

    ``data_limite`` em DD/MM/AAAA. É o que o Início cobra: uma anotação para
    ontem que ninguém marcou como feita continua sendo uma pendência.
    """
    chave = data_limite[6:10] + data_limite[3:5] + data_limite[0:2]
    conn = get_connection()
    try:
        return [
            {"id": linha[0], "data": linha[1], "texto": linha[2], "feita": False}
            for linha in conn.execute(
                """
                SELECT id, data, texto FROM anotacoes
                WHERE COALESCE(feita, 0) = 0
                  AND substr(data, 7, 4) || substr(data, 4, 2)
                      || substr(data, 1, 2) <= ?
                ORDER BY substr(data, 7, 4) || substr(data, 4, 2)
                         || substr(data, 1, 2), id
                """,
                (chave,),
            )
        ]
    finally:
        conn.close()


def salvar_anotacao(data: str, texto: str) -> int:
    """Cria uma anotação para um dia. Retorna o id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO anotacoes (data, texto, feita, criada_em) VALUES (?, ?, 0, ?)",
            (data, texto.strip(), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def marcar_anotacao(anotacao_id: int, feita: bool = True) -> None:
    """Marca (ou desmarca) uma anotação como feita."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE anotacoes SET feita = ? WHERE id = ?",
            (1 if feita else 0, anotacao_id),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_anotacao(anotacao_id: int) -> None:
    """Apaga uma anotação."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM anotacoes WHERE id = ?", (anotacao_id,))
        conn.commit()
    finally:
        conn.close()


def historico_discursos_do_orador(orador_id: int) -> list[dict]:
    """Tudo que este orador fez, do mais recente para trás.

    Traz os discursos enviados (ele foi a outra congregação) e os locais, com
    a data, o tema e para onde foi. É o detalhe por trás do número do
    relatório: "5 discursos" não diz quando, nem onde.

    Um simpósio conta para os dois oradores, por isso a busca olha as duas
    colunas de orador.
    """
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT ao.data,
                   ao.tipo,
                   COALESCE(c.nome, '') AS congregacao,
                   ao.tema_nr,
                   COALESCE(t.titulo, '') AS tema,
                   COALESCE(ao.status, 'pendente') AS status
            FROM arranjo_oradores ao
            LEFT JOIN congregacoes c ON ao.congregacao_id = c.id
            LEFT JOIN temas t ON ao.tema_nr = t.nr
            WHERE (ao.orador_id = ? OR ao.orador_2_id = ?)
              AND ao.data IS NOT NULL AND ao.data <> ''
            ORDER BY substr(ao.data, 7, 4) || substr(ao.data, 4, 2)
                     || substr(ao.data, 1, 2) DESC
            """,
            (orador_id, orador_id),
        ).fetchall()
        return [
            {
                "data": linha[0],
                "tipo": linha[1],
                "congregacao": linha[2],
                "tema_nr": linha[3],
                "tema": linha[4],
                "status": linha[5],
            }
            for linha in linhas
        ]
    finally:
        conn.close()


def historico_presidencias_da_pessoa(presidente_id: int) -> list[dict]:
    """Todas as vezes que esta pessoa presidiu, do mais recente para trás.

    Junta as semanas comuns e as datas especiais, que é como o rodízio conta:
    quem presidiu o discurso especial de setembro presidiu naquele mês.
    """
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            -- O ORDER BY com expressão não enxerga as colunas de um UNION;
            -- por isso a união vem primeiro, como subconsulta.
            SELECT data, tipo FROM (
                SELECT data, 'Reunião de fim de semana' AS tipo FROM presidentes
                WHERE presidente_id = ?
                UNION ALL
                SELECT data, tipo FROM datas_especiais WHERE presidente_id = ?
            )
            ORDER BY substr(data, 7, 4) || substr(data, 4, 2)
                     || substr(data, 1, 2) DESC
            """,
            (presidente_id, presidente_id),
        ).fetchall()
        return [{"data": linha[0], "tipo": linha[1]} for linha in linhas]
    finally:
        conn.close()


def historico_presidentes_por_tipo_de_evento() -> dict[str, dict[str, int]]:
    """Quem presidiu cada data especial, agrupado por tipo de evento.

    ``{tipo: {data: presidente_id}}``, de todos os anos. É a memória dos
    rodízios das datas especiais, e vem separada por tipo porque cada evento
    tem a sua fila: quem presidiu a Celebração deste ano não perde a vez na
    visita do superintendente por causa disso.

    Separado de ``carregar_todas_designacoes_presidente`` de propósito: lá a
    pergunta é "quem presidiu alguma coisa"; aqui é "de quem é a vez do
    próximo evento DESTE tipo", e as semanas comuns não entram na conta.
    """
    conn = get_connection()
    try:
        historico: dict[str, dict[str, int]] = {}
        for data, presidente_id, tipo in conn.execute(
            "SELECT data, presidente_id, tipo FROM datas_especiais "
            "WHERE presidente_id IS NOT NULL"
        ):
            historico.setdefault(tipo, {})[data] = presidente_id
        return historico
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
              AND presidente_id IS NOT NULL
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


def salvar_presidente_cadastro(
    nome: str,
    categoria: str,
    cadastro_id: int | None = None,
    telefone: str = "",
    contato_id: str | None = None,
    preside_normais: bool = True,
    preside_especiais: bool | None = None,
) -> int:
    """Cria ou atualiza um presidente no cadastro; retorna o ID.

    ``preside_normais`` e ``preside_especiais`` são independentes: dá para
    estar só numa das escalas, nas duas, ou em nenhuma (fica no cadastro sem
    entrar em rodízio nenhum). ``preside_especiais=None`` segue o privilégio
    (ancião entra), que é o mesmo critério da migração.
    """
    if preside_especiais is None:
        preside_especiais = categoria == "Ancião"
    conn = get_connection()
    try:
        if cadastro_id:
            conn.execute(
                "UPDATE presidentes_cadastro SET nome = ?, categoria = ?, "
                "telefone = ?, contato_id = ?, preside_normais = ?, "
                "preside_especiais = ? WHERE id = ?",
                (nome, categoria, telefone, contato_id or None,
                 1 if preside_normais else 0, 1 if preside_especiais else 0,
                 cadastro_id),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO presidentes_cadastro (
                    nome, categoria, telefone, contato_id,
                    preside_normais, preside_especiais, ordem
                ) VALUES (?, ?, ?, ?, ?, ?,
                    (SELECT COALESCE(MAX(ordem), 0) + 1 FROM presidentes_cadastro))
                """,
                (nome, categoria, telefone, contato_id or None,
                 1 if preside_normais else 0, 1 if preside_especiais else 0),
            )
            cadastro_id = int(cursor.lastrowid)
        conn.commit()
        return cadastro_id
    finally:
        conn.close()


def presidente_tem_historico(cadastro_id: int) -> bool:
    """Se este presidente já presidiu (ou está escalado para) alguma coisa."""
    conn = get_connection()
    try:
        for consulta in (
            "SELECT 1 FROM presidentes WHERE presidente_id = ? LIMIT 1",
            "SELECT 1 FROM datas_especiais WHERE presidente_id = ? LIMIT 1",
        ):
            if conn.execute(consulta, (cadastro_id,)).fetchone():
                return True
        return False
    finally:
        conn.close()


def arquivar_presidente_cadastro(cadastro_id: int, arquivar: bool = True) -> None:
    """Tira (ou devolve) um presidente da escala, sem tocar no histórico.

    É o caminho para quem se mudou de congregação: some do rodízio e das
    listas, e continua com o nome nas semanas e nas datas que presidiu.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE presidentes_cadastro SET ativo = ? WHERE id = ?",
            (0 if arquivar else 1, cadastro_id),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_presidente_cadastro(cadastro_id: int) -> None:
    """Remove um presidente do cadastro sem apagar o que ele presidiu.

    O nome é gravado nas semanas e nas datas especiais dele antes da exclusão
    (vira um "avulso", como quem presidiu sem estar no cadastro): o quadro
    daqueles meses continua com o nome certo, e o registro não fica órfão.
    Quem nunca presidiu nada simplesmente sai.
    """
    conn = get_connection()
    try:
        linha = conn.execute(
            "SELECT nome FROM presidentes_cadastro WHERE id = ?", (cadastro_id,)
        ).fetchone()
        nome = (linha[0] if linha else "") or ""
        if nome:
            conn.execute(
                "UPDATE presidentes SET nome_avulso = ?, presidente_id = NULL "
                "WHERE presidente_id = ?",
                (nome, cadastro_id),
            )
            conn.execute(
                "UPDATE datas_especiais SET presidente_avulso = ?, presidente_id = NULL "
                "WHERE presidente_id = ?",
                (nome, cadastro_id),
            )
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


def listar_datas_especiais_por_ano(ano: int | None = None) -> dict[str, dict]:
    """Datas especiais indexadas por data (Assembleia, Congresso…).

    Sem ``ano``, traz as de todos os anos — é o que a aba de presidentes de
    datas especiais mostra, porque a fila de cada tipo é medida contra o
    histórico inteiro, não contra um ano.
    """
    conn = get_connection()
    try:
        linhas = conn.execute(
            """
            SELECT e.id, e.data, e.tipo,
                   COALESCE(e.orador, '') AS orador,
                   COALESCE(e.tema, '') AS tema,
                   COALESCE(e.tema_final, '') AS tema_final,
                   e.presidente_id,
                   -- Do cadastro, ou o nome digitado à mão.
                   COALESCE(c.nome, e.presidente_avulso, '') AS presidente_nome,
                   e.congregacao_id,
                   COALESCE(cong.nome, '') AS congregacao_nome,
                   COALESCE(e.presidente_avulso, '') AS presidente_avulso
            FROM datas_especiais e
            LEFT JOIN presidentes_cadastro c ON e.presidente_id = c.id
            LEFT JOIN congregacoes cong ON e.congregacao_id = cong.id
            WHERE (? IS NULL OR substr(e.data, 7, 4) = ?)
            """,
            (None if ano is None else str(ano), None if ano is None else str(ano)),
        ).fetchall()
        return {
            linha[1]: {
                "id": linha[0],
                "data": linha[1],
                "tipo": linha[2],
                "orador": linha[3],
                "tema": linha[4],
                "tema_final": linha[5],
                "presidente_id": linha[6],
                "presidente_nome": linha[7],
                "congregacao_id": linha[8],
                "congregacao_nome": linha[9],
                "presidente_avulso": linha[10],
            }
            for linha in linhas
        }
    finally:
        conn.close()


def definir_presidente_avulso_data_especial(registro_id: int, nome: str) -> None:
    """Grava quem presidiu uma data especial sem estar no cadastro."""
    nome_limpo = (nome or "").strip()
    if not nome_limpo:
        raise ValueError("O nome do presidente avulso não pode ser vazio.")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE datas_especiais SET presidente_id = NULL, presidente_avulso = ? "
            "WHERE id = ?",
            (nome_limpo, registro_id),
        )
        conn.commit()
    finally:
        conn.close()


def definir_presidente_data_especial(registro_id: int, presidente_id: int | None) -> None:
    """Grava só o presidente de uma data especial, sem tocar no resto.

    O rodízio preenche a presidência de datas que já existem (com tipo, orador
    e tema preenchidos); reescrever tudo por causa de um campo só é caminho
    para apagar o que estava lá.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE datas_especiais SET presidente_id = ?, presidente_avulso = NULL "
            "WHERE id = ?",
            (presidente_id, registro_id),
        )
        conn.commit()
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
    presidente_avulso: str = "",
    tema_final: str = "",
) -> None:
    """Cria ou atualiza uma data especial (substitui se a data já existir).

    ``presidente_avulso`` é o nome de quem presidiu sem estar no cadastro; os
    dois se excluem, e quem está no cadastro tem preferência.

    ``tema_final`` é o discurso final da visita do superintendente, que tem
    dois discursos na mesma reunião.
    """
    avulso = (presidente_avulso or "").strip() or None
    if presidente_id:
        avulso = None
    conn = get_connection()
    try:
        if registro_id:
            conn.execute(
                """
                UPDATE datas_especiais
                SET data = ?, tipo = ?, orador = ?, tema = ?, tema_final = ?,
                    presidente_id = ?, congregacao_id = ?, presidente_avulso = ?
                WHERE id = ?
                """,
                (data, tipo, orador or None, tema or None,
                 (tema_final or "").strip() or None, presidente_id,
                 congregacao_id, avulso, registro_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO datas_especiais
                    (data, tipo, orador, tema, tema_final, presidente_id,
                     congregacao_id, presidente_avulso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(data) DO UPDATE SET
                    tipo = excluded.tipo,
                    orador = excluded.orador,
                    tema = excluded.tema,
                    tema_final = excluded.tema_final,
                    presidente_id = excluded.presidente_id,
                    congregacao_id = excluded.congregacao_id,
                    presidente_avulso = excluded.presidente_avulso
                """,
                (data, tipo, orador or None, tema or None,
                 (tema_final or "").strip() or None, presidente_id,
                 congregacao_id, avulso),
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


def listar_reuniao_historico() -> list[dict]:
    """Linha do tempo do dia/horário da reunião, do mais antigo para o atual."""
    conn = get_connection()
    try:
        return [
            {"inicio": linha[0], "dia_semana": linha[1], "horario": linha[2]}
            for linha in conn.execute(
                "SELECT inicio, dia_semana, COALESCE(horario, '') "
                "FROM reuniao_historico ORDER BY inicio"
            )
        ]
    finally:
        conn.close()


def salvar_reuniao_historico(inicio: str, dia_semana: str, horario: str = "") -> None:
    """Grava (ou substitui) o período que começa em ``inicio`` ('AAAA-MM')."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO reuniao_historico (inicio, dia_semana, horario) "
            "VALUES (?, ?, ?) ON CONFLICT(inicio) DO UPDATE SET "
            "dia_semana = excluded.dia_semana, horario = excluded.horario",
            (inicio, dia_semana, horario or ""),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_reuniao_historico(inicio: str) -> None:
    """Remove um período da linha do tempo."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM reuniao_historico WHERE inicio = ?", (inicio,))
        conn.commit()
    finally:
        conn.close()


def reuniao_em(ano: int, mes: int) -> dict | None:
    """Dia e horário da reunião naquele mês, ou ``None`` se não houver registro.

    Vale o período mais recente que já tinha começado. Sem histórico (ou para
    meses anteriores ao primeiro período), devolve ``None`` e quem chama cai
    na configuração atual.
    """
    alvo = f"{ano:04d}-{mes:02d}"
    conn = get_connection()
    try:
        linha = conn.execute(
            "SELECT dia_semana, COALESCE(horario, '') FROM reuniao_historico "
            "WHERE inicio <= ? ORDER BY inicio DESC LIMIT 1",
            (alvo,),
        ).fetchone()
    finally:
        conn.close()
    return {"dia_semana": linha[0], "horario": linha[1]} if linha else None


def _derivar_reuniao_historico(conn) -> None:
    """Monta a linha do tempo a partir das datas já gravadas.

    Rodada uma vez, na criação da tabela. As datas que já estão no banco dizem
    em que dia a reunião era: um mês cheio de domingos era domingo. Deduzir
    disso evita perguntar ao usuário o que o próprio histórico já responde —
    e evita chutar, que era a alternativa.
    """
    cursor = conn.cursor()
    if cursor.execute("SELECT COUNT(*) FROM reuniao_historico").fetchone()[0]:
        return

    # Um voto por data registrada (presidentes e oradores recebidos). As duas
    # tabelas podem ainda não existir: esta função roda no meio da criação do
    # esquema, e num banco novo não há histórico nenhum para derivar.
    existentes = {
        linha[0] for linha in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    votos: dict[str, dict[int, int]] = {}
    for tabela, consulta in (
        ("presidentes", "SELECT data FROM presidentes"),
        ("arranjo_oradores",
         "SELECT data FROM arranjo_oradores WHERE tipo = 'recebido'"),
    ):
        if tabela not in existentes:
            continue
        for (data,) in cursor.execute(consulta):
            if not data or len(data) != 10:
                continue
            try:
                dia = date(int(data[6:10]), int(data[3:5]), int(data[0:2]))
            except ValueError:
                continue
            mes = f"{dia.year:04d}-{dia.month:02d}"
            votos.setdefault(mes, {})
            votos[mes][dia.weekday()] = votos[mes].get(dia.weekday(), 0) + 1

    if not votos:
        return

    nomes = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
             "Sexta-feira", "Sábado", "Domingo"]
    anterior = None
    for mes in sorted(votos):
        # Datas especiais caem em dias avulsos (a Celebração numa quinta); o
        # dia da reunião é o que mais se repete no mês.
        weekday = max(votos[mes], key=lambda w: (votos[mes][w], -w))
        if weekday == anterior:
            continue
        cursor.execute(
            "INSERT OR IGNORE INTO reuniao_historico (inicio, dia_semana, horario) "
            "VALUES (?, ?, '')",
            (mes, nomes[weekday]),
        )
        anterior = weekday
    conn.commit()


def listar_tipos_evento() -> list[dict]:
    """Tipos de evento especial disponíveis (ordenados por nome).

    ``tem_presidente`` diz se aquele evento tem reunião no salão, com alguém
    presidindo — numa Assembleia a congregação está fora, e o rodízio das
    datas especiais não deve gastar a vez de um ancião ali.
    """
    conn = get_connection()
    try:
        return [
            {
                "id": linha[0],
                "nome": linha[1],
                "tem_presidente": bool(linha[2]),
                "entra_rodizio": bool(linha[3]),
            }
            for linha in conn.execute(
                "SELECT id, nome, COALESCE(tem_presidente, 1), COALESCE(entra_rodizio, 1) "
                "FROM tipos_evento_especial ORDER BY nome"
            )
        ]
    finally:
        conn.close()


def tipos_evento_sem_presidente() -> set[str]:
    """Nomes dos tipos marcados como SEM presidente local.

    A pergunta é pelo avesso de propósito. Excluir um tipo do cadastro não
    apaga as datas que já o usavam ("Discurso Especial" some da lista, a data
    de setembro continua lá), e perguntando "quais têm presidente?" essa data
    cairia fora do rodízio sem ninguém notar. Perguntando quais NÃO têm, tipo
    desconhecido pede presidente — que é o caso comum e o erro barato.
    """
    conn = get_connection()
    try:
        return {
            linha[0]
            for linha in conn.execute(
                "SELECT nome FROM tipos_evento_especial "
                "WHERE COALESCE(tem_presidente, 1) = 0"
            )
        }
    finally:
        conn.close()


def tipos_fora_do_rodizio_especiais() -> set[str]:
    """Nomes dos tipos que não entram na fila dos presidentes de datas especiais.

    Pergunta pelo avesso, como ``tipos_evento_sem_presidente``: tipo novo ou
    desconhecido entra no rodízio, que é o caso comum.

    O que foi removido entra aqui também: uma data antiga não pode ressuscitar
    a fila de um tipo que não existe mais.
    """
    conn = get_connection()
    try:
        return {
            nome
            for (nome,) in conn.execute(
                "SELECT nome FROM tipos_evento_especial WHERE COALESCE(entra_rodizio, 1) = 0"
                " UNION SELECT nome FROM tipos_evento_removidos"
            )
        }
    finally:
        conn.close()


def definir_tipo_evento_entra_rodizio(tipo_id: int, entra: bool) -> None:
    """Liga/desliga a participação do tipo no rodízio das datas especiais."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE tipos_evento_especial SET entra_rodizio = ? WHERE id = ?",
            (1 if entra else 0, tipo_id),
        )
        conn.commit()
    finally:
        conn.close()


def definir_tipo_evento_tem_presidente(tipo_id: int, tem_presidente: bool) -> None:
    """Liga/desliga o presidente local de um tipo de evento."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE tipos_evento_especial SET tem_presidente = ? WHERE id = ?",
            (1 if tem_presidente else 0, tipo_id),
        )
        conn.commit()
    finally:
        conn.close()


def adicionar_tipo_evento(nome: str) -> None:
    """Adiciona um tipo de evento especial (idempotente).

    Nasce com presidente local: a maioria dos eventos tem reunião no salão, e
    desligar o que não tem é um clique na própria tela. Cadastrar de novo um
    tipo removido desfaz a remoção.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO tipos_evento_especial (nome, tem_presidente) "
            "VALUES (?, 1)",
            (nome.strip(),),
        )
        conn.execute("DELETE FROM tipos_evento_removidos WHERE nome = ?", (nome.strip(),))
        conn.commit()
    finally:
        conn.close()


def excluir_tipo_evento(tipo_id: int) -> None:
    """Remove um tipo de evento (datas já cadastradas mantêm o texto).

    O nome fica marcado como removido para não ser recriado na abertura
    seguinte, nem pela lista de tipos padrão nem pelas datas antigas.
    """
    conn = get_connection()
    try:
        linha = conn.execute(
            "SELECT nome FROM tipos_evento_especial WHERE id = ?", (tipo_id,)
        ).fetchone()
        if linha:
            conn.execute(
                "INSERT OR IGNORE INTO tipos_evento_removidos (nome) VALUES (?)",
                (linha[0],),
            )
        conn.execute("DELETE FROM tipos_evento_especial WHERE id = ?", (tipo_id,))
        conn.commit()
    finally:
        conn.close()


def tipos_evento_removidos() -> set[str]:
    """Nomes de tipos que o usuário removeu — não voltam como opção nem fila."""
    conn = get_connection()
    try:
        return {
            nome for (nome,) in conn.execute("SELECT nome FROM tipos_evento_removidos")
        }
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
            "SELECT nr, titulo, notas, data_limite_uso, categoria, "
            "COALESCE(prioritario, 0) FROM temas WHERE nr = ?",
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
            "prioritario": bool(row[5]),
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


ABREVIACOES_MESES = [
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def _exibir_chave_mes_ano(chave: str) -> str:
    """Chave "AAAA-MM" vira "Mmm/AAAA" (ex.: 2024-12 -> Dez/2024)."""
    return f"{ABREVIACOES_MESES[int(chave[5:7])]}/{chave[0:4]}"


def formatar_mes_ano(data_uso) -> str:
    """Exibe "MM/AAAA" como "Mmm/AAAA"; o que não for data volta como está."""
    chave = _chave_mes_ano(data_uso)
    if not chave:
        return str(data_uso or "").strip()
    return _exibir_chave_mes_ano(chave)


def carregar_dataframe_temas(apenas_anos_visiveis: bool = True):
    """Monta a tabela de temas com uma coluna por ano (como na planilha)."""
    from tabela import Tabela

    conn = get_connection()
    try:
        anos = listar_anos_colunas(apenas_visiveis=apenas_anos_visiveis)
        temas = Tabela.de_consulta(
            conn,
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
                   END AS tem_observacao,
                   COALESCE(prioritario, 0) AS prioritario
            FROM temas
            ORDER BY nr
            """,
        )
        usos = conn.execute(
            "SELECT tema_nr, ano_coluna, data_uso FROM tema_uso_por_ano"
        ).fetchall()
    finally:
        conn.close()

    # Último uso considera todos os anos registrados, mesmo colunas ocultas.
    ultimo_uso: dict[int, str] = {}
    # Uso por (tema, ano) só das colunas visíveis, para virar coluna na tela.
    anos_visiveis = {item["ano"] for item in anos}
    por_ano: dict[tuple[int, int], str] = {}
    for tema_nr, ano_coluna, data_uso in usos:
        chave = _chave_mes_ano(data_uso)
        if not chave:
            continue
        tema_nr = int(tema_nr)
        if chave > ultimo_uso.get(tema_nr, ""):
            ultimo_uso[tema_nr] = chave
        if ano_coluna in anos_visiveis:
            por_ano[(tema_nr, int(ano_coluna))] = data_uso

    colunas_ano = [str(item["ano"]) for item in anos]
    for linha in temas.linhas:
        nr = int(linha["nr"])
        chave = ultimo_uso.get(nr, "")
        linha["ultimo_uso_chave"] = chave
        linha["ultimo_uso"] = _exibir_chave_mes_ano(chave) if chave else "Nunca"
        for item in anos:
            valor = por_ano.get((nr, item["ano"]))
            linha[str(item["ano"])] = formatar_mes_ano(valor) if valor else "—"

    temas.colunas = [
        "nr", "titulo", "assunto", *colunas_ano, "ultimo_uso",
        "restricoes", "data_limite_uso", "restrito", "tem_observacao",
        "ultimo_uso_chave", "prioritario",
    ]
    return temas


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
# O backup é um JSON versionado e autodescritivo, para que qualquer
# plataforma (computador, celular) importe os dados sem depender do
# arquivo SQLite: {"app", "versao_backup", "gerado_em", "tabelas"}.

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
    "reuniao_historico",
    "anotacoes",
    "tipos_evento_removidos",
]


def nome_do_aparelho() -> str:
    """De onde saiu o backup, em duas palavras: "Celular" ou "Computador (Windows)".

    Serve para o aviso da restauração dizer de qual ponta veio o arquivo. Não
    carrega nome de máquina nem nada que identifique a pessoa.
    """
    import platform

    from armazenamento import eh_mobile

    if eh_mobile():
        return "Celular"
    sistema = (platform.system() or "").strip()
    return f"Computador ({sistema})" if sistema else "Computador"


def resumo_backup(caminho: str | Path) -> dict[str, str]:
    """O que o arquivo diz sobre si mesmo: quando e onde foi gerado.

    Backups antigos não trazem o aparelho; nesse caso o campo volta vazio.
    """
    import json

    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"gerado_em": "", "aparelho": ""}
    if not isinstance(dados, dict):
        return {"gerado_em": "", "aparelho": ""}
    return {
        "gerado_em": str(dados.get("gerado_em") or ""),
        "aparelho": str(dados.get("aparelho") or ""),
    }


def alterado_em_local() -> str:
    """Quando o banco deste aparelho mudou pela última vez (ISO, hora local)."""
    try:
        modificado = Path(DB_PATH).stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(modificado).isoformat(timespec="seconds")


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
        "aparelho": nome_do_aparelho(),
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
        # Backup gerado antes do "tem_presidente" traz o tipo sem essa coluna,
        # que então cai no DEFAULT 1 — e a Assembleia voltaria a pedir
        # presidente no rodízio. Só nesse caso o padrão por nome é reaplicado;
        # um backup que já traz a coluna manda no que o usuário escolheu.
        linhas_tipos = tabelas.get("tipos_evento_especial") or []
        if linhas_tipos and not any("tem_presidente" in linha for linha in linhas_tipos):
            _aplicar_padrao_presidente_por_tipo(cursor)
        # Mesma história com a escala das datas especiais: sem a coluna, ela
        # cairia no DEFAULT 0 e o rodízio das especiais ficaria sem ninguém.
        linhas_cadastro = tabelas.get("presidentes_cadastro") or []
        if linhas_cadastro and not any(
            "preside_especiais" in linha for linha in linhas_cadastro
        ):
            _aplicar_padrao_escala_especiais(cursor)
        conn.commit()
        # Backup anterior à linha do tempo do dia de reunião: remonta a partir
        # das datas que acabaram de entrar, senão os anos antigos voltariam a
        # ser montados no dia de hoje até a próxima abertura do app.
        _derivar_reuniao_historico(conn)
        # Idem para o presidente avulso da data especial: o backup pode ser
        # anterior à coluna, e o nome está na semana comum da mesma data.
        cursor = conn.cursor()
        _recuperar_presidente_avulso_especiais(cursor)
        conn.commit()
        # A aba Temas só conta o que está em tema_uso_por_ano, e a coluna de
        # cada ano nasce daí. Sem isso, restaurar um backup com anos antigos
        # deixava esses anos sem coluna e sem contagem até a próxima abertura
        # do app — parecia que os discursos daqueles anos não existiam.
        realocar_uso_para_ano_da_data(conn)
        sincronizar_uso_temas(conn)
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
