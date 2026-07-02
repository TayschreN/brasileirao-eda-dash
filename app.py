"""
Dashboard interativo — Campeonato Brasileiro Série A (2003-2024)
Autor: Gabriel

Rodar localmente:
    pip install -r requirements.txt
    python app.py
Depois abrir http://127.0.0.1:8050
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, html, dcc, Input, Output, callback_context
import dash_bootstrap_components as dbc

# ------------------------------------------------------------------
# 1. Carregamento e preparação dos dados
# ------------------------------------------------------------------

df = pd.read_csv('data/campeonato-brasileiro-full.csv')
df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
df['ano'] = df['data'].dt.year
df['total_gols'] = df['mandante_Placar'] + df['visitante_Placar']
df['margem'] = (df['mandante_Placar'] - df['visitante_Placar']).abs()


def resultado(row):
    if row['mandante_Placar'] > row['visitante_Placar']:
        return 'Mandante'
    elif row['mandante_Placar'] < row['visitante_Placar']:
        return 'Visitante'
    return 'Empate'


df['resultado'] = df.apply(resultado, axis=1)

# Formato "longo": uma linha por time por jogo, facilita agregações por time
mandante_rows = df[['ano', 'data', 'mandante', 'visitante', 'mandante_Placar',
                     'visitante_Placar', 'resultado', 'mandante_Estado']].copy()
mandante_rows.columns = ['ano', 'data', 'time', 'adversario', 'gols_pro',
                          'gols_contra', 'resultado_jogo', 'estado']
mandante_rows['mando'] = 'Casa'
mandante_rows['pontos'] = mandante_rows['resultado_jogo'].map({'Mandante': 3, 'Empate': 1, 'Visitante': 0})

visitante_rows = df[['ano', 'data', 'visitante', 'mandante', 'visitante_Placar',
                      'mandante_Placar', 'resultado', 'visitante_Estado']].copy()
visitante_rows.columns = ['ano', 'data', 'time', 'adversario', 'gols_pro',
                           'gols_contra', 'resultado_jogo', 'estado']
visitante_rows['mando'] = 'Fora'
visitante_rows['pontos'] = visitante_rows['resultado_jogo'].map({'Visitante': 3, 'Empate': 1, 'Mandante': 0})

long_df = pd.concat([mandante_rows, visitante_rows], ignore_index=True)
long_df['vitoria'] = long_df['pontos'] == 3

ANO_MIN, ANO_MAX = int(df['ano'].min()), int(df['ano'].max())

# Lista de times ordenada por nº de jogos (mais relevantes primeiro)
times_por_volume = long_df['time'].value_counts()
LISTA_TIMES = sorted(times_por_volume.index.tolist())

# Baselines históricos (dataset completo, sem filtro) — usados para comparação nos insights
HIST_GOLS_MEDIA = df['total_gols'].mean()
HIST_PCT_MANDANTE = (df['resultado'] == 'Mandante').mean() * 100

CORES = {
    'mandante': '#0b6e4f',
    'empate': '#d4a017',
    'visitante': '#b23a2e',
    'casa': '#0b6e4f',
    'fora': '#8a8f8d',
}

TEMPLATE_PLOTLY = 'plotly_white'

# Configuração da barra de ferramentas: habilita o botão de câmera (download)
# em todos os gráficos, já exportando em formato quadrado (1080x1080) para
# facilitar o uso direto em posts (LinkedIn, Instagram, etc.)
CONFIG_DOWNLOAD = {
    'displayModeBar': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d',
                                'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'],
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'grafico_brasileirao',
        'height': 1080,
        'width': 1080,
        'scale': 2,
    },
}


# ------------------------------------------------------------------
# 2. Funções de cálculo (separadas do callback para permitir testes diretos)
# ------------------------------------------------------------------

def filtrar_dados(ano_range, times_selecionados):
    ano_ini, ano_fim = ano_range
    df_f = df[(df['ano'] >= ano_ini) & (df['ano'] <= ano_fim)].copy()
    long_f = long_df[(long_df['ano'] >= ano_ini) & (long_df['ano'] <= ano_fim)].copy()

    if times_selecionados:
        df_f = df_f[(df_f['mandante'].isin(times_selecionados)) | (df_f['visitante'].isin(times_selecionados))]
        long_f = long_f[long_f['time'].isin(times_selecionados)]

    return df_f, long_f


def calcular_kpis(df_f, long_f):
    total_partidas = len(df_f)
    if total_partidas == 0:
        return {
            'total_partidas': 0, 'media_gols': 0, 'pct_mandante': 0,
            'melhor_time': '—', 'melhor_time_pct': 0, 'maior_goleada': '—'
        }

    media_gols = df_f['total_gols'].mean()
    pct_mandante = (df_f['resultado'] == 'Mandante').mean() * 100

    ranking = long_f.groupby('time').agg(jogos=('pontos', 'count'), pontos=('pontos', 'sum'))
    min_jogos = max(5, int(ranking['jogos'].max() * 0.15)) if len(ranking) else 5
    elegiveis = ranking[ranking['jogos'] >= min_jogos].copy()
    if len(elegiveis):
        elegiveis['aproveitamento'] = elegiveis['pontos'] / (elegiveis['jogos'] * 3) * 100
        melhor_time = elegiveis['aproveitamento'].idxmax()
        melhor_time_pct = elegiveis['aproveitamento'].max()
    else:
        melhor_time, melhor_time_pct = '—', 0

    idx_goleada = df_f['margem'].idxmax()
    linha_goleada = df_f.loc[idx_goleada]
    maior_goleada = (f"{linha_goleada['mandante']} {int(linha_goleada['mandante_Placar'])}"
                      f"–{int(linha_goleada['visitante_Placar'])} {linha_goleada['visitante']}")

    return {
        'total_partidas': total_partidas,
        'media_gols': round(media_gols, 2),
        'pct_mandante': round(pct_mandante, 1),
        'melhor_time': melhor_time,
        'melhor_time_pct': round(melhor_time_pct, 1),
        'maior_goleada': maior_goleada,
    }


def calcular_sequencias(long_f, tipo='vitoria'):
    """Calcula a maior sequência (streak) por time no recorte filtrado.
    tipo='vitoria' -> maior sequência de vitórias consecutivas
    tipo='invencibilidade' -> maior sequência sem perder (vitória ou empate)
    """
    if len(long_f) == 0:
        return pd.DataFrame(columns=['time', 'sequencia', 'inicio', 'fim'])

    df_sorted = long_f.sort_values(['time', 'data'])

    registros = []
    for time, grupo in df_sorted.groupby('time', sort=False):
        flag = grupo['vitoria'].values if tipo == 'vitoria' else (grupo['pontos'] >= 1).values
        datas = grupo['data'].values
        melhor_len, melhor_ini, melhor_fim = 0, None, None
        cur_len, cur_ini = 0, None
        for i in range(len(flag)):
            if flag[i]:
                if cur_len == 0:
                    cur_ini = datas[i]
                cur_len += 1
                if cur_len > melhor_len:
                    melhor_len, melhor_ini, melhor_fim = cur_len, cur_ini, datas[i]
            else:
                cur_len = 0
        registros.append({'time': time, 'sequencia': melhor_len, 'inicio': melhor_ini, 'fim': melhor_fim})

    return pd.DataFrame(registros).set_index('time')


def fig_mando_campo(df_f):
    if len(df_f) == 0:
        return go.Figure()
    tab = df_f.groupby(['ano', 'resultado']).size().unstack(fill_value=0)
    for col in ['Mandante', 'Empate', 'Visitante']:
        if col not in tab.columns:
            tab[col] = 0
    pct = tab.div(tab.sum(axis=1), axis=0) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pct.index, y=pct['Mandante'], name='Vitória mandante',
                              mode='lines', stackgroup='one', line=dict(width=0.5, color=CORES['mandante'])))
    fig.add_trace(go.Scatter(x=pct.index, y=pct['Empate'], name='Empate',
                              mode='lines', stackgroup='one', line=dict(width=0.5, color=CORES['empate'])))
    fig.add_trace(go.Scatter(x=pct.index, y=pct['Visitante'], name='Vitória visitante',
                              mode='lines', stackgroup='one', line=dict(width=0.5, color=CORES['visitante'])))
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=10, t=10, b=10),
                       height=300, yaxis_title='% das partidas', xaxis_title=None,
                       legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
                       hovermode='x unified')
    return fig


def fig_gols_por_ano(df_f):
    if len(df_f) == 0:
        return go.Figure()
    media = df_f.groupby('ano')['total_gols'].mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=media.index, y=media.values, mode='lines+markers',
                              line=dict(color=CORES['mandante'], width=3),
                              marker=dict(size=7), name='Gols/partida'))
    fig.add_hline(y=HIST_GOLS_MEDIA, line_dash='dash', line_color='#b0b0b0',
                  annotation_text=f'Média histórica geral: {HIST_GOLS_MEDIA:.2f}',
                  annotation_font_size=10)
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=10, t=10, b=10),
                       height=300, yaxis_title='Gols por partida', xaxis_title=None)
    return fig


def fig_ranking_times(long_f, times_selecionados):
    if len(long_f) == 0:
        return go.Figure()
    ranking = long_f.groupby('time').agg(jogos=('pontos', 'count'), pontos=('pontos', 'sum'))

    if times_selecionados:
        elegiveis = ranking.copy()
    else:
        min_jogos = max(5, int(ranking['jogos'].max() * 0.15)) if len(ranking) else 5
        elegiveis = ranking[ranking['jogos'] >= min_jogos].copy()

    if len(elegiveis) == 0:
        return go.Figure()

    elegiveis['aproveitamento'] = (elegiveis['pontos'] / (elegiveis['jogos'] * 3) * 100).round(1)
    elegiveis = elegiveis.sort_values('aproveitamento', ascending=False).head(15).sort_values('aproveitamento')

    cores_barras = [CORES['mandante'] if t in (times_selecionados or []) else '#9fbfb2' for t in elegiveis.index]
    if not times_selecionados:
        cores_barras = [CORES['mandante']] * len(elegiveis)

    textos_barra = []
    for v in elegiveis['aproveitamento']:
        textos_barra.append(str(v) + '%')

    fig = go.Figure(go.Bar(
        x=elegiveis['aproveitamento'], y=elegiveis.index, orientation='h',
        marker_color=cores_barras,
        text=textos_barra, textposition='outside',
        customdata=elegiveis['jogos'],
        hovertemplate='%{y}<br>Aproveitamento: %{x}%<br>Jogos: %{customdata}<extra></extra>'
    ))
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=30, t=10, b=10),
                       height=420, xaxis_title='Aproveitamento de pontos (%)',
                       xaxis_range=[0, max(elegiveis['aproveitamento'].max() * 1.15, 10)])
    return fig


def fig_casa_fora(long_f, times_selecionados):
    if len(long_f) == 0:
        return go.Figure()
    ranking = long_f.groupby('time').agg(jogos=('pontos', 'count'))
    min_jogos = max(5, int(ranking['jogos'].max() * 0.15)) if len(ranking) else 5

    if times_selecionados:
        alvo = times_selecionados
    else:
        elegiveis = ranking[ranking['jogos'] >= min_jogos]
        totais = long_f[long_f['time'].isin(elegiveis.index)].groupby('time')['pontos'].sum()
        alvo = totais.sort_values(ascending=False).head(8).index.tolist()

    sub = long_f[long_f['time'].isin(alvo)]
    if len(sub) == 0:
        return go.Figure()

    tab = sub.groupby(['time', 'mando']).agg(jogos=('pontos', 'count'), pontos=('pontos', 'sum')).reset_index()
    tab['aproveitamento'] = (tab['pontos'] / (tab['jogos'] * 3) * 100).round(1)

    ordem = tab[tab['mando'] == 'Casa'].sort_values('aproveitamento', ascending=False)['time'].tolist()
    tab['time'] = pd.Categorical(tab['time'], categories=ordem, ordered=True)
    tab = tab.sort_values('time')

    fig = go.Figure()
    for mando, cor in [('Casa', CORES['casa']), ('Fora', CORES['fora'])]:
        sub_m = tab[tab['mando'] == mando]
        fig.add_trace(go.Bar(x=sub_m['time'], y=sub_m['aproveitamento'], name=mando, marker_color=cor))
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=10, t=10, b=10),
                       height=420, yaxis_title='Aproveitamento (%)', barmode='group',
                       legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0))
    return fig


def fig_distribuicao_gols(df_f):
    if len(df_f) == 0:
        return go.Figure()
    contagem = df_f['total_gols'].value_counts().sort_index()
    contagem_pct = (contagem / contagem.sum() * 100).round(1)
    media = df_f['total_gols'].mean()

    textos_barra = []
    for v in contagem_pct.values:
        textos_barra.append(str(v) + '%')

    fig = go.Figure(go.Bar(
        x=contagem_pct.index, y=contagem_pct.values,
        marker_color=CORES['mandante'],
        text=textos_barra, textposition='outside',
        hovertemplate='%{x} gols na partida<br>%{y}%% das partidas<extra></extra>'
    ))
    fig.add_vline(x=media, line_dash='dash', line_color=CORES['visitante'],
                   annotation_text=f'Média: {media:.2f}', annotation_font_size=10)
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=10, t=10, b=10),
                       height=300, xaxis_title='Total de gols na partida', yaxis_title='% das partidas',
                       xaxis=dict(dtick=1))
    return fig


def fig_gols_mandante_visitante(df_f):
    if len(df_f) == 0:
        return go.Figure()
    tab = df_f.groupby('ano').agg(gols_mandante=('mandante_Placar', 'mean'),
                                   gols_visitante=('visitante_Placar', 'mean'))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tab.index, y=tab['gols_mandante'], name='Gols do mandante',
                              mode='lines+markers', line=dict(color=CORES['mandante'], width=3), marker=dict(size=6)))
    fig.add_trace(go.Scatter(x=tab.index, y=tab['gols_visitante'], name='Gols do visitante',
                              mode='lines+markers', line=dict(color=CORES['visitante'], width=3), marker=dict(size=6)))
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=10, t=10, b=10),
                       height=300, yaxis_title='Média de gols marcados', xaxis_title=None,
                       legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
                       hovermode='x unified')
    return fig


def fig_participacao_estados(df_f):
    if len(df_f) == 0:
        return go.Figure()
    estados = pd.concat([
        df_f['mandante_Estado'].rename('estado'),
        df_f['visitante_Estado'].rename('estado'),
    ]).str.strip()
    contagem = estados.value_counts().head(12).sort_values()

    fig = go.Figure(go.Bar(
        x=contagem.values, y=contagem.index, orientation='h',
        marker_color=CORES['mandante'],
        text=contagem.values, textposition='outside',
    ))
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=30, t=10, b=10),
                       height=300, xaxis_title='Nº de participações em partidas',
                       xaxis_range=[0, contagem.max() * 1.15])
    return fig


def fig_sequencias(long_f, times_selecionados):
    if len(long_f) == 0:
        return go.Figure()
    seq = calcular_sequencias(long_f, tipo='invencibilidade')
    jogos_por_time = long_f.groupby('time').size()
    seq['jogos'] = jogos_por_time

    if times_selecionados:
        alvo = seq[seq.index.isin(times_selecionados)]
    else:
        min_jogos = max(10, int(jogos_por_time.max() * 0.1)) if len(jogos_por_time) else 10
        alvo = seq[seq['jogos'] >= min_jogos]

    if len(alvo) == 0:
        return go.Figure()

    alvo = alvo.sort_values('sequencia', ascending=False).head(10).sort_values('sequencia')
    hover_txt = [
        f"{s} jogos sem perder<br>{pd.Timestamp(i_ini).strftime('%d/%m/%Y') if pd.notnull(i_ini) else ''} "
        f"a {pd.Timestamp(i_fim).strftime('%d/%m/%Y') if pd.notnull(i_fim) else ''}"
        for s, i_ini, i_fim in zip(alvo['sequencia'], alvo['inicio'], alvo['fim'])
    ]

    fig = go.Figure(go.Bar(
        x=alvo['sequencia'], y=alvo.index, orientation='h',
        marker_color=CORES['empate'],
        text=alvo['sequencia'], textposition='outside',
        hovertext=hover_txt, hoverinfo='text',
    ))
    fig.update_layout(template=TEMPLATE_PLOTLY, margin=dict(l=10, r=30, t=10, b=10),
                       height=300, xaxis_title='Maior sequência sem perder (nº de jogos)',
                       xaxis_range=[0, alvo['sequencia'].max() * 1.2])
    return fig


def gerar_insights(df_f, long_f, ano_range, times_selecionados):
    if len(df_f) == 0:
        return [html.Div("Nenhuma partida encontrada para os filtros selecionados. Tente ampliar o período ou os times.",
                          className='insight-item')]

    insights = []
    pct_mandante = (df_f['resultado'] == 'Mandante').mean() * 100
    diff_mandante = pct_mandante - HIST_PCT_MANDANTE
    if abs(diff_mandante) < 0.15:
        insights.append(
            f"O mandante venceu {pct_mandante:.1f}% das partidas no período selecionado, "
            f"praticamente em linha com a média histórica geral da base completa."
        )
    else:
        direcao = "acima" if diff_mandante > 0 else "abaixo"
        insights.append(
            f"O mandante venceu {pct_mandante:.1f}% das partidas no período selecionado, "
            f"{abs(diff_mandante):.1f} p.p. {direcao} da média histórica geral ({HIST_PCT_MANDANTE:.1f}%)."
        )

    media_gols = df_f['total_gols'].mean()
    diff_gols = media_gols - HIST_GOLS_MEDIA
    if abs(diff_gols) < 0.02:
        insights.append(
            f"A média foi de {media_gols:.2f} gols por partida, em linha com a média histórica geral."
        )
    else:
        direcao_gols = "mais" if diff_gols > 0 else "menos"
        insights.append(
            f"A média foi de {media_gols:.2f} gols por partida — {direcao_gols} que a média histórica "
            f"de {HIST_GOLS_MEDIA:.2f}."
        )

    ranking = long_f.groupby('time').agg(jogos=('pontos', 'count'), pontos=('pontos', 'sum'))
    min_jogos = max(5, int(ranking['jogos'].max() * 0.15)) if len(ranking) else 5
    elegiveis = ranking[ranking['jogos'] >= min_jogos].copy()
    if len(elegiveis):
        elegiveis['aproveitamento'] = elegiveis['pontos'] / (elegiveis['jogos'] * 3) * 100
        melhor = elegiveis['aproveitamento'].idxmax()
        insights.append(
            f"{melhor} teve o melhor aproveitamento do período ({elegiveis['aproveitamento'].max():.1f}%) "
            f"entre os times com pelo menos {min_jogos} jogos disputados."
        )

    idx_goleada = df_f['margem'].idxmax()
    linha = df_f.loc[idx_goleada]
    insights.append(
        f"A maior goleada do período foi {linha['mandante']} {int(linha['mandante_Placar'])}"
        f"–{int(linha['visitante_Placar'])} {linha['visitante']}, "
        f"em {linha['data'].strftime('%d/%m/%Y')}."
    )

    if times_selecionados and len(times_selecionados) >= 1:
        sub = long_f[long_f['time'].isin(times_selecionados)]
        tab = sub.groupby('mando').agg(jogos=('pontos', 'count'), pontos=('pontos', 'sum'))
        if 'Casa' in tab.index and 'Fora' in tab.index and tab.loc['Casa', 'jogos'] > 0 and tab.loc['Fora', 'jogos'] > 0:
            aprov_casa = tab.loc['Casa', 'pontos'] / (tab.loc['Casa', 'jogos'] * 3) * 100
            aprov_fora = tab.loc['Fora', 'pontos'] / (tab.loc['Fora', 'jogos'] * 3) * 100
            gap = aprov_casa - aprov_fora
            times_txt = ', '.join(times_selecionados) if len(times_selecionados) <= 3 else f"{len(times_selecionados)} times selecionados"
            insights.append(
                f"Para {times_txt}, o aproveitamento em casa ({aprov_casa:.1f}%) é "
                f"{abs(gap):.1f} p.p. {'maior' if gap > 0 else 'menor'} que fora ({aprov_fora:.1f}%)."
            )

    gols_mandante_media = df_f['mandante_Placar'].mean()
    gols_visitante_media = df_f['visitante_Placar'].mean()
    diff_ataque = gols_mandante_media - gols_visitante_media
    insights.append(
        f"O mandante marca em média {gols_mandante_media:.2f} gols por jogo, contra {gols_visitante_media:.2f} do visitante "
        f"— uma vantagem de {diff_ataque:.2f} gol(s), sinal de que o mando de campo pesa também no ataque, não só no resultado final."
    )

    seq_vitorias = calcular_sequencias(long_f, tipo='vitoria')
    if len(seq_vitorias) and seq_vitorias['sequencia'].max() > 0:
        time_seq = seq_vitorias['sequencia'].idxmax()
        linha_seq = seq_vitorias.loc[time_seq]
        ini_fmt = pd.Timestamp(linha_seq['inicio']).strftime('%d/%m/%Y') if pd.notnull(linha_seq['inicio']) else '?'
        fim_fmt = pd.Timestamp(linha_seq['fim']).strftime('%d/%m/%Y') if pd.notnull(linha_seq['fim']) else '?'
        insights.append(
            f"A maior sequência de vitórias consecutivas do período foi do {time_seq}: "
            f"{int(linha_seq['sequencia'])} jogos seguidos vencidos, entre {ini_fmt} e {fim_fmt}."
        )

    return [html.Div(f"• {texto}", className='insight-item') for texto in insights]


# ------------------------------------------------------------------
# 3. Layout
# ------------------------------------------------------------------

app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], title="Brasileirão Dashboard")
server = app.server  # necessário para deploy (gunicorn)

app.layout = dbc.Container([

    html.Div([
        html.H1("⚽ Brasileirão Dashboard"),
        html.P(f"Retrospectiva interativa da Série A — {ANO_MIN} a {ANO_MAX} · {len(df):,} partidas".replace(',', '.')),
    ], className='header-banner'),

    # Filtros
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div("Período (temporadas)", className='filter-label'),
                dcc.RangeSlider(
                    id='filtro-ano', min=ANO_MIN, max=ANO_MAX, value=[ANO_MIN, ANO_MAX],
                    marks={a: str(a) for a in range(ANO_MIN, ANO_MAX + 1, 3)},
                    tooltip={'placement': 'bottom', 'always_visible': False},
                    step=1,
                ),
            ], className='filter-card')
        ], md=7),
        dbc.Col([
            html.Div([
                html.Div("Times (vazio = todos)", className='filter-label'),
                dcc.Dropdown(
                    id='filtro-times', options=[{'label': t, 'value': t} for t in LISTA_TIMES],
                    value=[], multi=True, placeholder="Selecione um ou mais times...",
                ),
            ], className='filter-card')
        ], md=5),
    ]),

    # KPIs
    dbc.Row(id='kpi-row', className='mb-2'),

    # Insights dinâmicos
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H5("💡 Insights do período selecionado"),
                html.Div(id='insights-container'),
            ], className='insight-box')
        ], md=12)
    ], className='mb-3'),

    # Gráficos - linha 1
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H5("Vantagem do mando de campo"),
                html.Div("% de vitórias do mandante, empates e vitórias do visitante, por temporada", className='chart-sub'),
                dcc.Graph(id='grafico-mando', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
        dbc.Col([
            html.Div([
                html.H5("Gols por partida ao longo do tempo"),
                html.Div("Média de gols (mandante + visitante) por temporada", className='chart-sub'),
                dcc.Graph(id='grafico-gols', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
    ]),

    # Gráficos - linha 2
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H5("Ranking por aproveitamento"),
                html.Div("Times ordenados por % de pontos conquistados no período/seleção", className='chart-sub'),
                dcc.Graph(id='grafico-ranking', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
        dbc.Col([
            html.Div([
                html.H5("Desempenho em casa vs. fora"),
                html.Div("Comparação de aproveitamento por mando de campo", className='chart-sub'),
                dcc.Graph(id='grafico-casa-fora', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
    ]),

    # Gráficos - linha 3
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H5("Distribuição de gols por partida"),
                html.Div("% das partidas por total de gols marcados (mandante + visitante)", className='chart-sub'),
                dcc.Graph(id='grafico-distribuicao-gols', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
        dbc.Col([
            html.Div([
                html.H5("Gols do mandante vs. visitante"),
                html.Div("Média de gols marcados por cada lado, por temporada", className='chart-sub'),
                dcc.Graph(id='grafico-gols-mandante-visitante', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
    ]),

    # Gráficos - linha 4
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H5("Participação por estado"),
                html.Div("Top 12 estados por nº de participações em partidas (mandante + visitante)", className='chart-sub'),
                dcc.Graph(id='grafico-estados', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
        dbc.Col([
            html.Div([
                html.H5("Maiores sequências de invencibilidade"),
                html.Div("Top 10 times por maior sequência sem perder no período/seleção", className='chart-sub'),
                dcc.Graph(id='grafico-sequencias', config=CONFIG_DOWNLOAD),
            ], className='chart-card')
        ], md=6),
    ]),

    html.Div([
        "Dashboard construído com Dash + Plotly · Dados: Campeonato Brasileiro Série A 2003–2024 (GitHub, domínio público) · Projeto de portfólio"
    ], className='footer-note'),

], fluid=True, style={'maxWidth': '1300px', 'paddingBottom': '20px'})


# ------------------------------------------------------------------
# 4. Componente de KPI card (helper de layout)
# ------------------------------------------------------------------

def kpi_card(label, value, sub=None, md=True):
    children = [
        html.Div(label, className='kpi-label'),
        html.Div(value, className='kpi-value'),
    ]
    if sub:
        children.append(html.Div(sub, className='kpi-sub'))
    return dbc.Col(html.Div(children, className='kpi-card'), md=True, className='mb-3')


# ------------------------------------------------------------------
# 5. Callback principal
# ------------------------------------------------------------------

@app.callback(
    Output('kpi-row', 'children'),
    Output('insights-container', 'children'),
    Output('grafico-mando', 'figure'),
    Output('grafico-gols', 'figure'),
    Output('grafico-ranking', 'figure'),
    Output('grafico-casa-fora', 'figure'),
    Output('grafico-distribuicao-gols', 'figure'),
    Output('grafico-gols-mandante-visitante', 'figure'),
    Output('grafico-estados', 'figure'),
    Output('grafico-sequencias', 'figure'),
    Input('filtro-ano', 'value'),
    Input('filtro-times', 'value'),
)
def atualizar_dashboard(ano_range, times_selecionados):
    df_f, long_f = filtrar_dados(ano_range, times_selecionados)
    kpis = calcular_kpis(df_f, long_f)

    kpi_cards = [
        kpi_card("Partidas no período", f"{kpis['total_partidas']:,}".replace(',', '.')),
        kpi_card("Média de gols/partida", f"{kpis['media_gols']:.2f}"),
        kpi_card("Vitórias do mandante", f"{kpis['pct_mandante']:.1f}%"),
        kpi_card("Melhor aproveitamento", kpis['melhor_time'], f"{kpis['melhor_time_pct']:.1f}% dos pontos"),
        kpi_card("Maior goleada", kpis['maior_goleada']),
    ]

    insights = gerar_insights(df_f, long_f, ano_range, times_selecionados)

    fig1 = fig_mando_campo(df_f)
    fig2 = fig_gols_por_ano(df_f)
    fig3 = fig_ranking_times(long_f, times_selecionados)
    fig4 = fig_casa_fora(long_f, times_selecionados)
    fig5 = fig_distribuicao_gols(df_f)
    fig6 = fig_gols_mandante_visitante(df_f)
    fig7 = fig_participacao_estados(df_f)
    fig8 = fig_sequencias(long_f, times_selecionados)

    return kpi_cards, insights, fig1, fig2, fig3, fig4, fig5, fig6, fig7, fig8


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8050)