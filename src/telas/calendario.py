"""Tela Calendário: o ano inteiro numa grade, mês a mês.

Mostra em que dias há orador recebido, designação enviada, presidente
definido e data especial, e abre os detalhes de um dia no clique. Primeira
tela a sair do main.py: depende só do banco, do tema e dos componentes
comuns, sem nada que a prenda ao resto da interface.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Callable

import flet as ft

from armazenamento import eh_mobile
from database import (
    carregar_enviados_por_ano,
    carregar_presidentes_por_ano,
    carregar_recebidos_por_ano,
    excluir_anotacao,
    listar_anotacoes,
    listar_datas_especiais_por_ano,
    marcar_anotacao,
    salvar_anotacao,
)
from tema import (
    BORDA_SUAVE,
    COR_AVISO,
    COR_DESTAQUE,
    COR_DESTAQUE_CLARA,
    COR_SUCESSO,
    FUNDO_CARD,
    TEXTO_PRIMARIO,
    TEXTO_SECUNDARIO,
    fonte,
)
from ui_comuns import _largura_dialog, criar_cabecalho_tela
from util import NOMES_MESES


def tela_calendario(page: ft.Page, recarregar: Callable[[], None]) -> ft.Control:
    """Calendário mensal: reuniões, oradores recebidos e eventos especiais."""
    hoje = date.today()
    estado = {"ano": hoje.year, "mes": hoje.month}
    corpo = ft.Column(spacing=6, tight=True)
    titulo_mes = ft.Text("", size=fonte(16), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO)
    dias_semana = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

    def render():
        ano, mes = estado["ano"], estado["mes"]
        titulo_mes.value = f"{NOMES_MESES[mes]} de {ano}"
        recebidos = carregar_recebidos_por_ano(ano)
        enviados = carregar_enviados_por_ano(ano)
        presidentes = carregar_presidentes_por_ano(ano)
        especiais = listar_datas_especiais_por_ano(ano)

        semanas = calendar.Calendar(firstweekday=6).monthdayscalendar(ano, mes)
        # No celular a grade é só número + bolinhas, então cabe bem menor.
        altura = 52 if eh_mobile() else 96

        def abrir_dia(data_str: str):
            esp = especiais.get(data_str)
            rec = recebidos.get(data_str)
            envs = enviados.get(data_str) or []
            pres = presidentes.get(data_str)

            def linha_detalhe(icone, cor, titulo, texto):
                return ft.Row(
                    [
                        ft.Icon(icone, size=fonte(16), color=cor),
                        ft.Column(
                            [
                                ft.Text(titulo, size=fonte(11), color=TEXTO_SECUNDARIO),
                                ft.Text(texto, size=fonte(13), color=TEXTO_PRIMARIO),
                            ],
                            spacing=0,
                            tight=True,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )

            detalhes: list[ft.Control] = []
            if esp:
                partes = " · ".join(
                    p
                    for p in (esp.get("orador") or "", esp.get("tema") or "")
                    if p
                )
                detalhes.append(
                    linha_detalhe(
                        ft.Icons.STAR_OUTLINE, COR_AVISO,
                        esp.get("tipo") or "Evento especial",
                        partes or "—",
                    )
                )
            if rec:
                tema = rec.get("tema") or ""
                if rec.get("tema_nr") and tema:
                    tema = f"{rec['tema_nr']} - {tema}"
                detalhes.append(
                    linha_detalhe(
                        ft.Icons.RECORD_VOICE_OVER_OUTLINED, COR_SUCESSO,
                        "Orador recebido",
                        f"{rec.get('orador', '')}\n{tema}".strip(),
                    )
                )
            for env in envs:
                tema = env.get("tema") or ""
                if env.get("tema_nr") and tema:
                    tema = f"{env['tema_nr']} - {tema}"
                destino = env.get("congregacao") or "?"
                rotulo_status = {
                    "confirmado": " · confirmado",
                    "recusado": " · recusado",
                    "pendente": " · aguardando confirmação",
                }.get(env.get("status") or "pendente", "")
                detalhes.append(
                    linha_detalhe(
                        ft.Icons.SEND_OUTLINED, COR_DESTAQUE_CLARA,
                        f"Enviado para {destino}{rotulo_status}",
                        f"{env.get('orador', '')}\n{tema}".strip(),
                    )
                )
            if pres:
                detalhes.append(
                    linha_detalhe(
                        ft.Icons.CO_PRESENT_OUTLINED, COR_DESTAQUE,
                        "Presidente", pres["nome"],
                    )
                )
            if not detalhes:
                detalhes = [
                    ft.Text(
                        "Nada agendado para este dia.",
                        size=fonte(13),
                        color=TEXTO_SECUNDARIO,
                        italic=True,
                    )
                ]


            # Anotações do dia: o que você quer lembrar de fazer nesta data,
            # que não é orador nem presidente — "ligar para o Fulano".
            lista_anotacoes = ft.Column(spacing=0, tight=True)
            campo_anotacao = ft.TextField(
                hint_text="Anotar para este dia",
                expand=True,
                dense=True,
                border_color=BORDA_SUAVE,
                focused_border_color=COR_DESTAQUE,
            )

            def montar_anotacoes():
                anotadas = listar_anotacoes(data_str)
                if not anotadas:
                    lista_anotacoes.controls = [
                        ft.Text(
                            "Nenhuma anotação para este dia.",
                            size=fonte(12), color=TEXTO_SECUNDARIO, italic=True,
                        )
                    ]
                    return

                def linha_anotacao(item: dict) -> ft.Control:
                    def alternar(e, anotacao=item):
                        marcar_anotacao(anotacao["id"], bool(e.control.value))
                        montar_anotacoes()
                        recarregar()
                        page.update()

                    def apagar(_=None, anotacao=item):
                        excluir_anotacao(anotacao["id"])
                        montar_anotacoes()
                        recarregar()
                        page.update()

                    return ft.Row(
                        [
                            ft.Checkbox(
                                value=item["feita"],
                                on_change=alternar,
                                tooltip="Marcar como feita",
                            ),
                            ft.Text(
                                item["texto"],
                                size=fonte(13),
                                color=TEXTO_SECUNDARIO if item["feita"] else TEXTO_PRIMARIO,
                                italic=item["feita"],
                                expand=True,
                                max_lines=3,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=fonte(16),
                                icon_color=TEXTO_SECUNDARIO,
                                tooltip="Apagar anotação",
                                on_click=apagar,
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )

                lista_anotacoes.controls = [linha_anotacao(item) for item in anotadas]

            def anotar(_=None):
                texto = (campo_anotacao.value or "").strip()
                if not texto:
                    return
                salvar_anotacao(data_str, texto)
                campo_anotacao.value = ""
                montar_anotacoes()
                recarregar()
                page.update()

            campo_anotacao.on_submit = anotar
            montar_anotacoes()

            detalhes += [
                ft.Container(height=4),
                ft.Divider(height=1, color=BORDA_SUAVE),
                ft.Text("Anotações", size=fonte(12), color=TEXTO_SECUNDARIO,
                        weight=ft.FontWeight.W_600),
                lista_anotacoes,
                ft.Row(
                    [
                        campo_anotacao,
                        ft.IconButton(
                            icon=ft.Icons.ADD,
                            icon_color=COR_DESTAQUE,
                            tooltip="Anotar",
                            on_click=anotar,
                        ),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ]

            page.show_dialog(
                ft.AlertDialog(
                    modal=True,
                    title=ft.Text(data_str, size=fonte(16), weight=ft.FontWeight.W_600),
                    content=ft.Container(
                        width=_largura_dialog(page, 380),
                        content=ft.Column(
                            detalhes, spacing=12, tight=True,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    ),
                    actions=[
                        ft.TextButton("Fechar", on_click=lambda _: page.pop_dialog())
                    ],
                )
            )

        def celula(dia: int) -> ft.Control:
            if dia == 0:
                return ft.Container(expand=True)
            data_str = f"{dia:02d}/{mes:02d}/{ano}"
            esp = especiais.get(data_str)
            rec = recebidos.get(data_str)
            envs = enviados.get(data_str) or []
            pres = presidentes.get(data_str)
            eh_hoje = (ano, mes, dia) == (hoje.year, hoje.month, hoje.day)

            marcadores: list[ft.Control] = []
            if esp:
                marcadores.append(
                    ft.Text(
                        esp.get("tipo") or "Evento",
                        size=fonte(10),
                        color=COR_AVISO,
                        weight=ft.FontWeight.W_600,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    )
                )
            if rec and not esp:
                marcadores.append(
                    ft.Text(
                        rec.get("orador") or "",
                        size=fonte(10),
                        color=COR_SUCESSO,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    )
                )
            for env in envs[:2]:
                marcadores.append(
                    ft.Text(
                        f"→ {env.get('orador', '')}",
                        size=fonte(10),
                        color=COR_DESTAQUE_CLARA,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    )
                )
            if len(envs) > 2:
                marcadores.append(
                    ft.Text(
                        f"+{len(envs) - 2} envio(s)",
                        size=fonte(9),
                        color=TEXTO_SECUNDARIO,
                    )
                )
            if pres and not esp:
                marcadores.append(
                    ft.Text(
                        f"P: {pres['nome']}",
                        size=fonte(9),
                        color=TEXTO_SECUNDARIO,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    )
                )
            tem_conteudo = bool(esp or rec or envs or pres)

            if eh_mobile():
                # Sete colunas num celular deixam ~45px por dia: nome nenhum
                # cabe ("Laer…", "P: Gi…"). Na grade ficam só o número e
                # bolinhas coloridas; os nomes vão na lista logo abaixo.
                pontos = []
                if esp:
                    pontos.append(COR_AVISO)
                if rec:
                    pontos.append(COR_SUCESSO)
                if envs:
                    pontos.append(COR_DESTAQUE_CLARA)
                conteudo_celula = ft.Column(
                    [
                        ft.Text(
                            str(dia),
                            size=fonte(13),
                            weight=ft.FontWeight.W_700 if eh_hoje else ft.FontWeight.W_500,
                            color=COR_DESTAQUE if eh_hoje else TEXTO_PRIMARIO,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Row(
                            [
                                ft.Container(
                                    width=6, height=6, bgcolor=cor, border_radius=3
                                )
                                for cor in pontos[:3]
                            ],
                            spacing=3,
                            alignment=ft.MainAxisAlignment.CENTER,
                            tight=True,
                        ),
                    ],
                    spacing=3,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            else:
                conteudo_celula = ft.Column(
                    [
                        ft.Text(
                            str(dia),
                            size=fonte(12),
                            weight=ft.FontWeight.W_700 if eh_hoje else ft.FontWeight.W_500,
                            color=COR_DESTAQUE if eh_hoje else TEXTO_PRIMARIO,
                        ),
                        *marcadores,
                    ],
                    spacing=1,
                    tight=True,
                )

            return ft.Container(
                content=conteudo_celula,
                bgcolor=ft.Colors.with_opacity(0.08, COR_DESTAQUE)
                if tem_conteudo
                else FUNDO_CARD,
                border=ft.Border.all(
                    2 if eh_hoje else 1, COR_DESTAQUE if eh_hoje else BORDA_SUAVE
                ),
                border_radius=8,
                padding=6,
                expand=True,
                height=altura,
                on_click=lambda e, d=data_str: abrir_dia(d),
                ink=True,
                tooltip="Ver detalhes do dia",
            )

        cabecalho = ft.Row(
            [
                ft.Container(
                    content=ft.Text(
                        d,
                        size=fonte(11),
                        weight=ft.FontWeight.W_600,
                        color=TEXTO_SECUNDARIO,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    expand=True,
                )
                for d in dias_semana
            ],
            spacing=6,
        )
        corpo.controls = [
            cabecalho,
            *[
                ft.Row([celula(d) for d in semana], spacing=6 if not eh_mobile() else 4)
                for semana in semanas
            ],
        ]

        if eh_mobile():
            # A grade dá a visão do mês; os nomes ficam legíveis aqui embaixo.
            itens_agenda: list[ft.Control] = []
            for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
                data_str = f"{dia:02d}/{mes:02d}/{ano}"
                esp = especiais.get(data_str)
                rec = recebidos.get(data_str)
                envs = enviados.get(data_str) or []
                pres = presidentes.get(data_str)
                if not (esp or rec or envs):
                    continue
                linhas: list[ft.Control] = []
                if esp:
                    linhas.append(
                        ft.Text(esp.get("tipo") or "Evento especial",
                                size=fonte(12), color=COR_AVISO,
                                weight=ft.FontWeight.W_600)
                    )
                if rec:
                    linhas.append(
                        ft.Text(rec.get("orador") or "", size=fonte(13),
                                color=COR_SUCESSO, weight=ft.FontWeight.W_600)
                    )
                for env in envs:
                    destino = env.get("congregacao") or "?"
                    linhas.append(
                        ft.Text(f"→ {env.get('orador', '')} · {destino}",
                                size=fonte(12), color=COR_DESTAQUE_CLARA,
                                max_lines=2)
                    )
                if pres:
                    linhas.append(
                        ft.Text(f"Presidente: {pres['nome']}", size=fonte(11),
                                color=TEXTO_SECUNDARIO)
                    )
                itens_agenda.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text(
                                        f"{dia:02d}",
                                        size=fonte(16),
                                        weight=ft.FontWeight.W_700,
                                        color=COR_DESTAQUE,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    width=fonte(38),
                                ),
                                ft.Column(linhas, spacing=1, tight=True, expand=True),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                        bgcolor=FUNDO_CARD,
                        border=ft.Border.all(1, BORDA_SUAVE),
                        border_radius=10,
                        on_click=lambda e, d=data_str: abrir_dia(d),
                        ink=True,
                    )
                )
            corpo.controls += [
                ft.Container(height=8),
                ft.Text(f"Programação de {NOMES_MESES[mes].lower()}",
                        size=fonte(13), weight=ft.FontWeight.W_600,
                        color=TEXTO_PRIMARIO),
                *(itens_agenda or [
                    ft.Text("Nada programado neste mês.", size=fonte(12),
                            color=TEXTO_SECUNDARIO, italic=True)
                ]),
            ]
        page.update()

    def mudar_mes(delta: int):
        m, a = estado["mes"] + delta, estado["ano"]
        if m < 1:
            m, a = 12, a - 1
        elif m > 12:
            m, a = 1, a + 1
        estado["mes"], estado["ano"] = m, a
        render()

    def ir_hoje(_=None):
        estado["ano"], estado["mes"] = hoje.year, hoje.month
        render()

    barra = ft.Row(
        [
            ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=lambda _: mudar_mes(-1)),
            titulo_mes,
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=lambda _: mudar_mes(1)),
            ft.Container(expand=True),
            ft.TextButton("Hoje", icon=ft.Icons.TODAY, on_click=ir_hoje),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def item_legenda(cor: str, rotulo: str) -> ft.Control:
        return ft.Row(
            [
                ft.Container(width=10, height=10, bgcolor=cor, border_radius=3),
                ft.Text(rotulo, size=fonte(11), color=TEXTO_SECUNDARIO),
            ],
            spacing=5,
            tight=True,
        )

    legenda = ft.Row(
        [
            item_legenda(COR_SUCESSO, "Orador recebido"),
            item_legenda(
                COR_DESTAQUE_CLARA,
                "Enviado" if eh_mobile() else "→ Enviado da minha congregação",
            ),
            item_legenda(COR_AVISO, "Evento especial"),
            item_legenda(TEXTO_SECUNDARIO, "P: presidente"),
        ],
        spacing=16,
        wrap=True,
    )

    render()
    return ft.Column(
        [
            criar_cabecalho_tela(
                "Calendário",
                "Recebidos, enviados e eventos do mês. Clique num dia para ver os detalhes",
            ),
            barra,
            corpo,
            legenda,
        ],
        spacing=12,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
