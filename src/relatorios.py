"""Monta o conteúdo dos relatórios de cada tela, pronto para virar PDF.

Cada tela do app tem um botão que exporta o que ela mostra. Aqui ficam só os
dados — cada função devolve uma lista de **seções** no formato que o
``pdf_relatorios`` sabe desenhar::

    {"titulo": str, "descricao": str, "cabecalhos": [str],
     "larguras": [int], "linhas": [[str]], "vazio": str}

Separar isso do ``main.py`` (que é UI) e do ``pdf_relatorios`` (que é
desenho) deixa o conteúdo testável sem abrir janela nem gerar arquivo.
"""

from __future__ import annotations

from database import (
    carregar_arranjos_por_ano,
    carregar_dataframe_temas,
    carregar_oradores_arranjo,
    carregar_presidentes_por_ano,
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


def _ordenar_por_data(registros: list[dict]) -> list[dict]:
    """Ordena por data DD/MM/AAAA (o texto sozinho ordenaria pelo dia)."""
    def chave(registro: dict) -> str:
        data = registro.get("data") or ""
        return data[6:10] + data[3:5] + data[0:2] if len(data) == 10 else data
    return sorted(registros, key=chave)


def _secao(titulo, descricao, cabecalhos, larguras, linhas, vazio) -> dict:
    return {
        "titulo": titulo,
        "descricao": descricao,
        "cabecalhos": cabecalhos,
        "larguras": larguras,
        "linhas": linhas,
        "vazio": vazio,
    }


def secoes_programacao(ano: int) -> list[dict]:
    """A programação do ano inteiro, mês a mês.

    Um bloco por mês com arranjo: quem vem discursar, quem foi enviado, quem
    preside cada semana e as datas especiais. É o retrato que o coordenador
    leva impresso.
    """
    secoes: list[dict] = []
    presidentes = carregar_presidentes_por_ano(ano)
    especiais = listar_datas_especiais_por_ano(ano)
    arranjos = carregar_arranjos_por_ano(ano)

    if not arranjos:
        return [
            _secao(
                f"Programação de {ano}", "", ["Mês"], [470], [],
                "Nenhum arranjo cadastrado neste ano.",
            )
        ]

    for arranjo in arranjos:
        mes = int(arranjo.get("mes_inicio") or 0)
        nome_mes = NOMES_MESES[mes] if 1 <= mes <= 12 else str(mes)
        anfitria = arranjo.get("congregacao") or "sem congregação anfitriã"
        reuniao = " ".join(
            parte for parte in (arranjo.get("dia_semana"), arranjo.get("horario")) if parte
        )
        registros = carregar_oradores_arranjo(int(arranjo["id"]))
        recebidos = _ordenar_por_data([r for r in registros if r["tipo"] == "recebido"])
        enviados = _ordenar_por_data([r for r in registros if r["tipo"] == "enviado"])

        secoes.append(
            _secao(
                f"{nome_mes} de {ano} — {anfitria}",
                reuniao,
                ["Data", "Orador recebido", "Tema", "Congregação"],
                [60, 150, 180, 80],
                [
                    [
                        (r.get("data") or "")[:5],
                        r.get("orador_nome", ""),
                        f"{r['tema_nr']} - {r.get('tema_titulo', '')}"
                        if r.get("tema_nr") else (r.get("tema_titulo") or "—"),
                        r.get("congregacao_nome") or "—",
                    ]
                    for r in recebidos
                ],
                "Nenhum orador recebido neste mês.",
            )
        )
        secoes.append(
            _secao(
                "",
                "",
                ["Data", "Orador enviado", "Tema", "Destino", "Situação"],
                [55, 120, 145, 90, 60],
                [
                    [
                        (r.get("data") or "")[:5],
                        r.get("orador_nome", ""),
                        f"{r['tema_nr']} - {r.get('tema_titulo', '')}"
                        if r.get("tema_nr") else (r.get("tema_titulo") or "—"),
                        r.get("congregacao_nome") or "—",
                        _ROTULO_STATUS.get(r.get("status", ""), r.get("status", "")),
                    ]
                    for r in enviados
                ],
                "Nenhuma designação enviada neste mês.",
            )
        )

        linhas_pres = []
        for data_str, registro in sorted(
            presidentes.items(), key=lambda item: item[0][6:10] + item[0][3:5] + item[0][0:2]
        ):
            if len(data_str) == 10 and int(data_str[3:5]) == mes:
                linhas_pres.append(
                    [
                        data_str[:5],
                        registro.get("nome", ""),
                        "fora do rodízio" if registro.get("avulso") else "no rodízio",
                    ]
                )
        secoes.append(
            _secao(
                "", "", ["Data", "Preside", "Rodízio"], [70, 300, 100],
                linhas_pres, "Nenhum presidente definido neste mês.",
            )
        )

        linhas_esp = [
            [data_str[:5], reg.get("tipo", ""), reg.get("presidente_nome") or "—"]
            for data_str, reg in sorted(
                especiais.items(), key=lambda item: item[0][6:10] + item[0][3:5] + item[0][0:2]
            )
            if len(data_str) == 10 and int(data_str[3:5]) == mes
        ]
        if linhas_esp:
            secoes.append(
                _secao(
                    "", "", ["Data", "Evento especial", "Preside"], [70, 250, 150],
                    linhas_esp, "",
                )
            )

    return secoes


def secoes_oradores(oradores: list[dict]) -> list[dict]:
    """Cadastro de oradores, agrupado por congregação.

    Recebe a lista pronta (o ``main.py`` já a carrega para a tela) para o
    relatório sair exatamente igual ao que está na tela.
    """
    por_congregacao: dict[str, list[dict]] = {}
    for orador in oradores:
        por_congregacao.setdefault(orador.get("congregacao") or "—", []).append(orador)

    if not por_congregacao:
        return [
            _secao(
                "Oradores", "", ["Nome"], [470], [], "Nenhum orador cadastrado.",
            )
        ]

    secoes = []
    for congregacao in sorted(por_congregacao):
        lista = sorted(por_congregacao[congregacao], key=lambda o: o.get("nome") or "")
        secoes.append(
            _secao(
                congregacao,
                f"{len(lista)} orador(es)",
                ["Nome", "Privilégio", "Telefone", "Temas"],
                [150, 90, 90, 140],
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
            "Congregações",
            f"{len(congregacoes)} congregação(ões) cadastrada(s)",
            ["Congregação", "Responsável", "Telefone", "Reunião", "Endereço"],
            [110, 100, 80, 80, 100],
            [
                [
                    c.get("nome", ""),
                    c.get("responsavel") or "—",
                    c.get("telefone") or "—",
                    " ".join(
                        p for p in (c.get("dia_semana"), c.get("horario")) if p
                    ) or "—",
                    c.get("endereco") or "—",
                ]
                for c in congregacoes
            ],
            "Nenhuma congregação cadastrada.",
        )
    ]


def secoes_temas() -> list[dict]:
    """Catálogo de temas com o último uso — o que dá para repetir e o que não."""
    df = carregar_dataframe_temas(apenas_anos_visiveis=True)
    linhas = [
        [
            str(linha["nr"]),
            linha["titulo"],
            linha["assunto"] if linha["assunto"] != "—" else "",
            linha["ultimo_uso"],
        ]
        for linha in df
    ]
    nunca = sum(1 for linha in linhas if linha[3] == "Nunca")
    return [
        _secao(
            "Temas",
            f"{len(linhas)} tema(s) — {nunca} nunca apresentado(s) aqui",
            ["Nº", "Tema", "Assunto", "Último uso"],
            [35, 250, 110, 75],
            linhas,
            "Nenhum tema cadastrado.",
        )
    ]


def secoes_presidentes() -> list[dict]:
    """Cadastro de presidentes: a ordem do rodízio e quanto cada um presidiu."""
    cadastro = listar_presidentes_cadastro()
    contagem = {item["nome"]: item for item in relatorio_presidencias()}
    return [
        _secao(
            "Presidentes",
            "Na ordem do rodízio. As presidências contam desde o começo.",
            ["#", "Nome", "Privilégio", "Telefone", "Presidiu", "Última"],
            [25, 150, 100, 85, 50, 60],
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
        )
    ]
