"""Monta o conteúdo dos relatórios de cada tela, pronto para virar PDF.

Cada tela do app tem um botão que exporta o que ela mostra. Aqui ficam só os
dados — cada função devolve uma lista de **seções** no formato que o
``pdf_relatorios`` sabe desenhar::

    {"titulo": str, "descricao": str, "cabecalhos": [str],
     "larguras": [int], "linhas": [[str]], "vazio": str, "faixa": bool}

``faixa=True`` marca um começo de bloco (um mês, uma congregação): vira uma
tarja colorida. As demais seções viram um rótulo curto e a sua tabela.

Separar isso do ``main.py`` (que é UI) e do ``pdf_relatorios`` (que é
desenho) deixa o conteúdo testável sem abrir janela nem gerar arquivo.
"""

from __future__ import annotations

from database import (
    carregar_arranjos_por_ano,
    carregar_dataframe_temas,
    carregar_oradores_arranjo,
    carregar_presidentes_por_ano,
    get_connection,
    listar_anos_colunas,
    listar_datas_especiais_por_ano,
    listar_presidentes_cadastro,
    relatorio_presidencias,
)

NOMES_MESES = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

_ROTULO_STATUS = {
    "pendente": "Aguardando",
    "confirmado": "Confirmado",
    "recusado": "Recusado",
}

# Largura útil de uma A4 retrato com as margens do relatório.
LARGURA_UTIL = 523


def identificacao_congregacao() -> tuple[str, list[str]]:
    """Nome da congregação e as linhas de contato do coordenador.

    Vai no alto de todo relatório: quem recebe o papel precisa saber de que
    congregação ele é e para quem ligar — é a informação que o coordenador
    mais precisa ter à mão.
    """
    conn = get_connection()
    try:
        linha = conn.execute(
            "SELECT nome_congregacao, coordenador_discursos, telefone_coordenador, "
            "dia_reuniao, horario_reuniao FROM configuracoes WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()
    if not linha:
        return "", []

    nome, coordenador, telefone, dia, horario = (
        (valor or "").strip() for valor in linha
    )
    contato: list[str] = []
    if coordenador:
        contato.append(f"Coordenador de discursos: {coordenador}")
    if telefone:
        contato.append(telefone)
    reuniao = " ".join(p for p in (dia, horario) if p)
    if reuniao:
        contato.append(f"Reunião: {reuniao}")
    return nome, contato


def _ordenar_por_data(registros: list[dict]) -> list[dict]:
    """Ordena por data DD/MM/AAAA (o texto sozinho ordenaria pelo dia)."""
    def chave(registro: dict) -> str:
        data = registro.get("data") or ""
        return data[6:10] + data[3:5] + data[0:2] if len(data) == 10 else data
    return sorted(registros, key=chave)


def _chave_data(data: str) -> str:
    return data[6:10] + data[3:5] + data[0:2]


def _secao(titulo, descricao, cabecalhos, larguras, linhas, vazio, faixa=False) -> dict:
    return {
        "titulo": titulo,
        "descricao": descricao,
        "cabecalhos": cabecalhos,
        "larguras": larguras,
        "linhas": linhas,
        "vazio": vazio,
        "faixa": faixa,
    }


def faixa(titulo: str, apoio: str = "") -> dict:
    """Tarja de separação — usada pelo relatório completo entre as partes."""
    return _secao(titulo, apoio, [], [], [], "", faixa=True)


def _tema_do_registro(registro: dict) -> str:
    if registro.get("tema_nr"):
        return f"{registro['tema_nr']} — {registro.get('tema_titulo', '')}".strip(" —")
    return registro.get("tema_titulo") or "—"


def secoes_programacao(ano: int) -> list[dict]:
    """A programação do ano inteiro, um bloco por mês.

    Cada mês traz quem vem discursar, quem foi enviado, quem preside cada
    semana e as datas especiais — cada tabela com o seu rótulo, para o papel
    não virar uma pilha de grades iguais.
    """
    presidentes = carregar_presidentes_por_ano(ano)
    especiais = listar_datas_especiais_por_ano(ano)
    arranjos = carregar_arranjos_por_ano(ano)

    if not arranjos:
        return [
            _secao(
                f"Programação de {ano}", "", [], [], [],
                "Nenhum arranjo cadastrado neste ano.",
            )
        ]

    secoes: list[dict] = []
    for arranjo in arranjos:
        mes = int(arranjo.get("mes_inicio") or 0)
        nome_mes = NOMES_MESES[mes] if 1 <= mes <= 12 else str(mes)
        anfitria = arranjo.get("congregacao") or "sem congregação anfitriã"
        reuniao = " ".join(
            p for p in (arranjo.get("dia_semana"), arranjo.get("horario")) if p
        )
        registros = carregar_oradores_arranjo(int(arranjo["id"]))
        recebidos = _ordenar_por_data([r for r in registros if r["tipo"] == "recebido"])
        enviados = _ordenar_por_data([r for r in registros if r["tipo"] == "enviado"])

        apoio = f"Anfitriã: {anfitria}"
        if reuniao:
            apoio += f" · Reunião {reuniao}"
        secoes.append(_secao(nome_mes, apoio, [], [], [], "", faixa=True))

        secoes.append(
            _secao(
                "ORADORES RECEBIDOS", "",
                ["Data", "Orador", "Tema", "Congregação"],
                [46, 132, 215, 130],
                [
                    [
                        (r.get("data") or "")[:5],
                        r.get("orador_nome", ""),
                        _tema_do_registro(r),
                        r.get("congregacao_nome") or "—",
                    ]
                    for r in recebidos
                ],
                "Nenhum orador recebido neste mês.",
            )
        )
        secoes.append(
            _secao(
                "DESIGNAÇÕES ENVIADAS", "",
                ["Data", "Orador", "Tema", "Destino", "Situação"],
                [46, 116, 186, 111, 64],
                [
                    [
                        (r.get("data") or "")[:5],
                        r.get("orador_nome", ""),
                        _tema_do_registro(r),
                        r.get("congregacao_nome") or "—",
                        _ROTULO_STATUS.get(r.get("status", ""), r.get("status", "")),
                    ]
                    for r in enviados
                ],
                "Nenhuma designação enviada neste mês.",
            )
        )

        linhas_pres = [
            [
                data_str[:5],
                registro.get("nome", ""),
                "fora do rodízio" if registro.get("avulso") else "",
            ]
            for data_str, registro in sorted(presidentes.items(), key=lambda i: _chave_data(i[0]))
            if len(data_str) == 10 and int(data_str[3:5]) == mes
        ]
        secoes.append(
            _secao(
                "PRESIDENTES", "",
                ["Data", "Preside", "Observação"],
                [46, 337, 140],
                linhas_pres,
                "Nenhum presidente definido neste mês.",
            )
        )

        linhas_esp = [
            [data_str[:5], reg.get("tipo", ""), reg.get("presidente_nome") or "—"]
            for data_str, reg in sorted(especiais.items(), key=lambda i: _chave_data(i[0]))
            if len(data_str) == 10 and int(data_str[3:5]) == mes
        ]
        if linhas_esp:
            secoes.append(
                _secao(
                    "DATAS ESPECIAIS", "",
                    ["Data", "Evento", "Preside"],
                    [46, 287, 190],
                    linhas_esp, "",
                )
            )

    return secoes


def secoes_oradores(oradores: list[dict]) -> list[dict]:
    """Cadastro de oradores, um bloco por congregação.

    Recebe a lista pronta (o ``main.py`` já a carrega para a tela) para o
    relatório sair exatamente igual ao que está filtrado na tela.
    """
    por_congregacao: dict[str, list[dict]] = {}
    for orador in oradores:
        por_congregacao.setdefault(orador.get("congregacao") or "Sem congregação", []).append(orador)

    if not por_congregacao:
        return [_secao("Oradores", "", [], [], [], "Nenhum orador cadastrado.")]

    secoes: list[dict] = []
    for congregacao in sorted(por_congregacao):
        lista = sorted(por_congregacao[congregacao], key=lambda o: o.get("nome") or "")
        secoes.append(
            _secao(
                congregacao,
                f"{len(lista)} orador(es)",
                [], [], [], "", faixa=True,
            )
        )
        secoes.append(
            _secao(
                "", "",
                ["Nome", "Privilégio", "Telefone", "Temas que faz"],
                [150, 92, 96, 185],
                [
                    [
                        o.get("nome", ""),
                        o.get("categoria", ""),
                        o.get("telefone") or "—",
                        o.get("temas") or "—",
                    ]
                    for o in lista
                ],
                "Nenhum orador nesta congregação.",
            )
        )
    return secoes


def secoes_congregacoes(congregacoes: list[dict]) -> list[dict]:
    """Agenda das congregações do circuito: contato, reunião e endereço."""
    return [
        _secao(
            "", f"{len(congregacoes)} congregação(ões) no circuito.",
            ["Congregação", "Responsável", "Telefone", "Reunião", "Endereço"],
            [112, 100, 82, 79, 150],
            [
                [
                    c.get("nome", ""),
                    c.get("responsavel") or "—",
                    c.get("telefone") or "—",
                    " ".join(p for p in (c.get("dia_semana"), c.get("horario")) if p) or "—",
                    c.get("endereco") or "—",
                ]
                for c in congregacoes
            ],
            "Nenhuma congregação cadastrada.",
        ),
    ]


def secoes_temas() -> list[dict]:
    """Catálogo de temas no formato do S-99: uma coluna por ano.

    É a mesma leitura do formulário oficial de onde os temas vêm — número,
    título e, ano a ano, quando cada um foi apresentado aqui. Assim dá para
    conferir o relatório contra o formulário sem traduzir nada.
    """
    df = carregar_dataframe_temas(apenas_anos_visiveis=True)
    anos = [str(item["ano"]) for item in listar_anos_colunas(apenas_visiveis=True)]

    # Número e título fixos; o resto da folha se divide entre os anos.
    largura_anos = max(46, min(70, (LARGURA_UTIL - 34 - 250) // max(1, len(anos))))
    largura_titulo = LARGURA_UTIL - 34 - largura_anos * len(anos)

    linhas = [
        [str(linha["nr"]), linha["titulo"], *[linha.get(a, "—") for a in anos]]
        for linha in df
    ]
    nunca = sum(1 for linha in df if not linha.get("ultimo_uso_chave"))
    return [
        _secao(
            "",
            f"{len(linhas)} tema(s) · {nunca} ainda não apresentado(s) aqui. "
            "Cada coluna é um ano; a data é o mês em que o tema foi apresentado.",
            ["Nº", "Tema", *anos],
            [34, largura_titulo, *[largura_anos] * len(anos)],
            linhas,
            "Nenhum tema cadastrado.",
        ),
    ]


def secoes_presidentes() -> list[dict]:
    """Cadastro de presidentes: a ordem do rodízio e quanto cada um presidiu."""
    cadastro = listar_presidentes_cadastro()
    contagem = {item["nome"]: item for item in relatorio_presidencias()}
    return [
        _secao(
            "",
            f"{len(cadastro)} cadastrado(s). Esta é a ordem do rodízio automático.",
            ["#", "Nome", "Privilégio", "Telefone", "Presidiu", "Última vez"],
            [26, 158, 105, 92, 62, 80],
            [
                [
                    str(indice),
                    item["nome"],
                    item["categoria"],
                    item.get("telefone") or "—",
                    str(contagem.get(item["nome"], {}).get("quantidade", 0)),
                    contagem.get(item["nome"], {}).get("ultima_data") or "nunca",
                ]
                for indice, item in enumerate(cadastro, start=1)
            ],
            "Nenhum presidente cadastrado.",
        ),
    ]


def secoes_resumo_ano(
    resumo: dict, meses: list[dict], frequencia: list[dict], presidencias: list[dict]
) -> list[dict]:
    """O retrato do ano: o que só aparece somando os meses.

    Onde estão os buracos da cobertura, quem está discursando de menos e quem
    está presidindo de menos — é o mesmo conteúdo da tela de Relatórios.
    """
    semanas = int(resumo.get("semanas", 0))
    cobertas = int(resumo.get("cobertas", 0))
    com_presidente = int(resumo.get("presidentes", 0))

    return [
        _secao(
            "NÚMEROS DO ANO", "",
            ["Indicador", "Valor"],
            [380, 143],
            [
                ["Semanas com orador", f"{cobertas} de {semanas}"],
                ["Semanas sem orador", str(max(0, semanas - cobertas))],
                ["Semanas com presidente", f"{com_presidente} de {semanas}"],
                ["Semanas sem presidente", str(max(0, semanas - com_presidente))],
                ["Oradores recebidos", str(int(resumo.get("recebidos", 0)))],
                ["Designações enviadas", str(int(resumo.get("enviados", 0)))],
                ["Aguardando confirmação", str(int(resumo.get("pendentes", 0)))],
                ["Datas especiais", str(int(resumo.get("especiais", 0)))],
            ],
            "",
        ),
        _secao(
            "MÊS A MÊS",
            "Onde estão os buracos: semanas com orador e com presidente em cada mês.",
            ["Mês", "Semanas", "Com orador", "Com presidente"],
            [180, 90, 125, 128],
            [
                [
                    m.get("nome", ""),
                    str(m.get("semanas", 0)),
                    f"{m.get('cobertas', 0)} de {m.get('semanas', 0)}",
                    f"{m.get('presidentes', 0)} de {m.get('semanas', 0)}",
                ]
                for m in meses
            ],
            "Nenhum arranjo cadastrado neste ano.",
        ),
        _secao(
            "ORADORES DA MINHA CONGREGAÇÃO",
            "Discursos enviados, de quem discursou menos (e há mais tempo) para quem mais discursou.",
            ["Orador", "Discursos", "Último"],
            [313, 100, 110],
            [
                [o.get("nome", ""), str(o.get("quantidade", 0)), o.get("ultima_data") or "nunca"]
                for o in frequencia
            ],
            "Nenhum orador cadastrado na sua congregação.",
        ),
        _secao(
            "PRESIDÊNCIAS",
            "Quantas vezes cada um presidiu desde o começo; quem presidiu menos vem primeiro.",
            ["Presidente", "Privilégio", "Vezes", "Última"],
            [203, 120, 90, 110],
            [
                [
                    p.get("nome", ""),
                    p.get("categoria", ""),
                    str(p.get("quantidade", 0)),
                    p.get("ultima_data") or "nunca",
                ]
                for p in presidencias
            ],
            "Nenhum presidente cadastrado.",
        ),
    ]
