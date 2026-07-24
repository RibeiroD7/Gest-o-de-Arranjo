"""Planilha-modelo para carga inicial de dados do aplicativo.

Gera um arquivo .xlsx com abas de Congregações, Oradores e Presidentes para a
congregação preencher, e importa a planilha preenchida para o banco. Os temas
ficam de fora: são importados diretamente dos formulários S-99/S-99a na aba
Temas.

A importação é aditiva: registros já existentes (mesmo nome) são ignorados,
nada é apagado.
"""

import re
from datetime import datetime

from armazenamento import EXPORTS_DIR
from database import get_connection

ABA_LEIA_ME = "Leia-me"
ABA_CONGREGACOES = "Congregações"
ABA_ORADORES = "Oradores"
ABA_PRESIDENTES = "Presidentes"

COLUNAS_CONGREGACOES = [
    "Nome*", "Responsável", "Telefone", "Endereço",
    "Dia da reunião", "Horário", "Observações",
]
COLUNAS_ORADORES = [
    "Nome*", "Telefone", "Categoria", "Congregação",
    "Temas que faz (números separados por vírgula)", "Observações",
]
COLUNAS_PRESIDENTES = ["Nome*", "Categoria"]

CATEGORIAS_VALIDAS = ("Ancião", "Servo Ministerial")

# Título provisório para temas citados na planilha antes do S-99 ser importado;
# a importação do S-99 na aba Temas substitui pelo título oficial.
TITULO_TEMA_PENDENTE = "(título pendente — importe o S-99 na aba Temas)"

INSTRUCOES = [
    "PLANILHA DE DADOS — GESTÃO DE ARRANJO",
    "",
    "Preencha as abas desta planilha e importe o arquivo em Ajustes → "
    "Importar planilha preenchida. Colunas marcadas com * são obrigatórias; "
    "as demais podem ficar em branco.",
    "",
    "A importação apenas ADICIONA dados: nomes que já existem no aplicativo "
    "são ignorados e nada é apagado.",
    "",
    "Aba Congregações — uma linha por congregação do circuito.",
    "   Exemplo: Jardim Primavera | João Silva | (11) 91234-5678 | "
    "Rua das Flores, 100 | Sábado | 19:30 |",
    "",
    "Aba Oradores — uma linha por orador.",
    "   • Categoria: Ancião ou Servo Ministerial (há lista suspensa na célula).",
    "   • Congregação: escreva o nome exatamente como na aba Congregações. "
    "Congregações citadas aqui e ainda não cadastradas serão criadas "
    "automaticamente.",
    "   • Temas que faz: os números dos discursos, separados por vírgula. "
    "Exemplo: 1, 5, 23, 110. Se o orador faz qualquer tema, deixe em branco "
    "e escreva \"Qualquer tema\" em Observações.",
    "",
    "Aba Presidentes — quem pode presidir a reunião de fim de semana.",
    "",
    "Os temas (títulos dos discursos) NÃO entram nesta planilha: importe os "
    "formulários oficiais S-99/S-99a em PDF diretamente na aba Temas.",
]


def gerar_planilha_modelo() -> str:
    """Cria a planilha-modelo em `exports/`; retorna o caminho absoluto."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()

    ws_leia = wb.active
    ws_leia.title = ABA_LEIA_ME
    ws_leia.column_dimensions["A"].width = 100
    for i, linha in enumerate(INSTRUCOES, start=1):
        celula = ws_leia.cell(row=i, column=1, value=linha)
        celula.alignment = Alignment(wrap_text=True, vertical="top")
        if i == 1:
            celula.font = Font(bold=True, size=13)

    fonte_cabecalho = Font(bold=True, color="FFFFFF")
    fundo_cabecalho = PatternFill("solid", fgColor="1F6E62")

    def criar_aba(titulo: str, colunas: list[str], larguras: list[int]) -> None:
        ws = wb.create_sheet(titulo)
        for idx, (nome, largura) in enumerate(zip(colunas, larguras), start=1):
            celula = ws.cell(row=1, column=idx, value=nome)
            celula.font = fonte_cabecalho
            celula.fill = fundo_cabecalho
            ws.column_dimensions[get_column_letter(idx)].width = largura
        ws.freeze_panes = "A2"
        if "Categoria" in colunas:
            col = get_column_letter(colunas.index("Categoria") + 1)
            validacao = DataValidation(
                type="list",
                formula1=f'"{",".join(CATEGORIAS_VALIDAS)}"',
                allow_blank=True,
                showErrorMessage=True,
                errorTitle="Categoria inválida",
                error="Use Ancião ou Servo Ministerial.",
            )
            ws.add_data_validation(validacao)
            validacao.add(f"{col}2:{col}300")

    criar_aba(ABA_CONGREGACOES, COLUNAS_CONGREGACOES, [30, 24, 18, 40, 16, 10, 30])
    criar_aba(ABA_ORADORES, COLUNAS_ORADORES, [30, 18, 18, 30, 44, 30])
    criar_aba(ABA_PRESIDENTES, COLUNAS_PRESIDENTES, [30, 18])

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = EXPORTS_DIR / f"planilha_dados_gestao_arranjo_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    wb.save(caminho)
    return str(caminho.resolve())


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor != valor:  # NaN
        return ""
    return str(valor).strip()


def _normalizar_categoria(valor: str, avisos: list[str], contexto: str) -> str | None:
    texto = _texto(valor)
    if not texto:
        return None
    minusculas = texto.lower()
    if minusculas.startswith("anci"):
        return "Ancião"
    if minusculas.startswith("servo"):
        return "Servo Ministerial"
    avisos.append(f"{contexto}: categoria \"{texto}\" não reconhecida — ficou em branco.")
    return None


def _extrair_numeros_temas(valor, avisos: list[str], contexto: str) -> list[int]:
    texto = _texto(valor)
    if isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor == valor:
        texto = str(int(valor))
    if not texto:
        return []
    numeros: list[int] = []
    for pedaco in re.split(r"[,;/\s]+", texto):
        if not pedaco:
            continue
        try:
            numeros.append(int(pedaco))
        except ValueError:
            avisos.append(f"{contexto}: \"{pedaco}\" não é um número de tema — ignorado.")
    return sorted(set(numeros))


def _ler_aba(caminho: str, aba: str):
    """Lê uma aba da planilha; retorna DataFrame ou None se a aba não existir."""
    import pandas as pd

    try:
        return pd.read_excel(caminho, sheet_name=aba, dtype=str)
    except ValueError as exc:
        if "Worksheet" in str(exc):  # aba ausente; outros ValueError = arquivo inválido
            return None
        raise


def importar_planilha_dados(caminho: str) -> dict:
    """Importa a planilha preenchida. Aditivo: nomes já existentes são ignorados.

    Retorna {"congregacoes": {...}, "oradores": {...}, "presidentes": {...},
    "avisos": [...]}.
    """
    avisos: list[str] = []
    resumo = {
        "congregacoes": {"novas": 0, "ja_existiam": 0},
        "oradores": {"novos": 0, "ja_existiam": 0},
        "presidentes": {"novos": 0, "ja_existiam": 0},
        "avisos": avisos,
    }

    try:
        df_cong = _ler_aba(caminho, ABA_CONGREGACOES)
        df_orad = _ler_aba(caminho, ABA_ORADORES)
        df_pres = _ler_aba(caminho, ABA_PRESIDENTES)
    except Exception as exc:
        raise ValueError("Não foi possível ler o arquivo como planilha .xlsx.") from exc
    if df_cong is None and df_orad is None and df_pres is None:
        raise ValueError(
            "A planilha não tem as abas esperadas (Congregações, Oradores, "
            "Presidentes). Use a planilha-modelo baixada em Ajustes."
        )

    conn = get_connection()
    try:
        cursor = conn.cursor()

        congregacoes: dict[str, int] = {
            nome.strip().lower(): int(cid)
            for cid, nome in cursor.execute("SELECT id, nome FROM congregacoes")
        }

        def obter_congregacao(nome: str) -> int | None:
            """Retorna o id da congregação, criando-a se ainda não existir."""
            chave = nome.strip().lower()
            if not chave:
                return None
            if chave not in congregacoes:
                cursor.execute(
                    "INSERT INTO congregacoes (nome, responsavel, telefone, endereco, "
                    "dia_semana, horario, observacoes) VALUES (?, '', '', '', '', '', '')",
                    (nome.strip(),),
                )
                congregacoes[chave] = int(cursor.lastrowid)
                resumo["congregacoes"]["novas"] += 1
            return congregacoes[chave]

        if df_cong is not None:
            for i, row in df_cong.iterrows():
                nome = _texto(row.get("Nome*"))
                if not nome:
                    continue
                chave = nome.lower()
                if chave in congregacoes:
                    resumo["congregacoes"]["ja_existiam"] += 1
                    continue
                cursor.execute(
                    """
                    INSERT INTO congregacoes (
                        nome, responsavel, telefone, endereco, dia_semana, horario, observacoes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        nome,
                        _texto(row.get("Responsável")),
                        _texto(row.get("Telefone")),
                        _texto(row.get("Endereço")),
                        _texto(row.get("Dia da reunião")),
                        _texto(row.get("Horário")),
                        _texto(row.get("Observações")),
                    ),
                )
                congregacoes[chave] = int(cursor.lastrowid)
                resumo["congregacoes"]["novas"] += 1

        if df_orad is not None:
            oradores_existentes = {
                (nome.strip().lower(), cid)
                for nome, cid in cursor.execute(
                    "SELECT nome, congregacao_id FROM oradores"
                )
            }
            temas_existentes = {
                int(nr) for (nr,) in cursor.execute("SELECT nr FROM temas")
            }
            temas_pendentes_criados = False

            def garantir_tema(nr: int) -> None:
                """Cria um tema provisório para o vínculo orador↔tema não se perder."""
                nonlocal temas_pendentes_criados
                if nr in temas_existentes:
                    return
                cursor.execute(
                    "INSERT INTO temas (nr, titulo) VALUES (?, ?)",
                    (nr, TITULO_TEMA_PENDENTE),
                )
                temas_existentes.add(nr)
                temas_pendentes_criados = True
            for i, row in df_orad.iterrows():
                nome = _texto(row.get("Nome*"))
                if not nome:
                    continue
                contexto = f"Oradores, linha {i + 2}"
                congregacao_id = obter_congregacao(_texto(row.get("Congregação")))
                if (nome.lower(), congregacao_id) in oradores_existentes:
                    resumo["oradores"]["ja_existiam"] += 1
                    continue
                categoria = _normalizar_categoria(row.get("Categoria"), avisos, contexto)
                cursor.execute(
                    """
                    INSERT INTO oradores (nome, telefone, categoria, congregacao_id, observacoes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        nome,
                        _texto(row.get("Telefone")),
                        categoria,
                        congregacao_id,
                        _texto(row.get("Observações")),
                    ),
                )
                orador_id = int(cursor.lastrowid)
                oradores_existentes.add((nome.lower(), congregacao_id))
                resumo["oradores"]["novos"] += 1
                for tema_nr in _extrair_numeros_temas(
                    row.get("Temas que faz (números separados por vírgula)"),
                    avisos,
                    contexto,
                ):
                    garantir_tema(tema_nr)
                    cursor.execute(
                        "INSERT OR IGNORE INTO orador_temas (orador_id, tema_nr) VALUES (?, ?)",
                        (orador_id, tema_nr),
                    )

            if temas_pendentes_criados:
                avisos.append(
                    "Alguns temas citados na planilha ainda não estão cadastrados; "
                    "foram criados com título pendente. Importe o formulário S-99 "
                    "na aba Temas para preencher os títulos oficiais."
                )

        if df_pres is not None:
            presidentes_existentes = {
                nome.strip().lower()
                for (nome,) in cursor.execute("SELECT nome FROM presidentes_cadastro")
            }
            for i, row in df_pres.iterrows():
                nome = _texto(row.get("Nome*"))
                if not nome:
                    continue
                if nome.lower() in presidentes_existentes:
                    resumo["presidentes"]["ja_existiam"] += 1
                    continue
                categoria = _normalizar_categoria(
                    row.get("Categoria"), avisos, f"Presidentes, linha {i + 2}"
                ) or "Ancião"
                cursor.execute(
                    """
                    INSERT INTO presidentes_cadastro (nome, categoria, ordem)
                    VALUES (?, ?, (SELECT COALESCE(MAX(ordem), 0) + 1 FROM presidentes_cadastro))
                    """,
                    (nome, categoria),
                )
                presidentes_existentes.add(nome.lower())
                resumo["presidentes"]["novos"] += 1

        conn.commit()
    finally:
        conn.close()

    return resumo
