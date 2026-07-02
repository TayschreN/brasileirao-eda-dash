# Brasileirão Dashboard — Dash + Plotly

Dashboard interativo da Série A do Campeonato Brasileiro (2003–2024), construído com [Dash](https://dash.plotly.com/) e Plotly. Complementa o [EDA em notebook](../brasileirao_eda.ipynb) do mesmo projeto: aqui o foco é exploração interativa, não storytelling fixo.

## Funcionalidades

- **Filtros:** intervalo de temporadas (slider) e seleção de times (multi-select, opcional)
- **KPIs dinâmicos:** partidas no período, média de gols/partida, % de vitórias do mandante, melhor aproveitamento, maior goleada
- **Insights automáticos:** texto gerado dinamicamente comparando o período/seleção atual com a média histórica da base completa
- **4 gráficos interativos:**
  - Evolução da vantagem de mando de campo (área empilhada: mandante/empate/visitante)
  - Gols por partida ao longo do tempo, com linha de referência da média histórica
  - Ranking de times por aproveitamento (adapta ao filtro de times selecionado)
  - Comparação de desempenho em casa vs. fora

Todos os componentes reagem em tempo real aos filtros — não há necessidade de recarregar a página.

## Como rodar localmente

```bash
cd dashboard
pip install -r requirements.txt
python app.py
```

Depois abra **http://127.0.0.1:8050** no navegador.

## Como fazer deploy (Render)

Este projeto já vem com `Procfile` pronto para deploy no Render (mesmo fluxo que você já usa no bot do Telegram):

1. Suba a pasta `dashboard/` para um repositório no GitHub
2. No Render, crie um novo **Web Service** apontando para o repositório
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:server` (já configurado no `Procfile`)
5. O Render detecta a porta automaticamente via variável de ambiente `PORT`

## Estrutura

```
dashboard/
├── app.py              (aplicação Dash completa)
├── assets/
│   └── custom.css       (estilo visual customizado)
├── data/
│   └── campeonato-brasileiro-full.csv
├── requirements.txt
├── Procfile              (deploy no Render)
└── README.md
```

## Stack

Python · Dash · Plotly · dash-bootstrap-components · pandas · gunicorn

---
*Projeto de portfólio — parte da preparação para vaga de estágio em Dados.*
