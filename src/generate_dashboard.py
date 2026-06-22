from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "raw" / "prova_idea.xlsx"
OUT_DIR = BASE_DIR / "docs"
OUT_FILE = OUT_DIR / "index.html"


def money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


def num(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def prepare_data() -> dict:
    df = pd.read_excel(RAW_FILE, sheet_name="base")
    df.columns = [c.lower() for c in df.columns]
    df["periodo"] = pd.to_datetime(df["periodo"])
    df["ano_mes"] = df["periodo"].dt.to_period("M").astype(str)

    for col in ["tipo", "vertical", "cidade", "uf", "regiao", "produto"]:
        df[col] = df[col].astype(str).str.strip().str.upper()

    df = df[~((df["receita"] == 0) & (df["custo"] == 0))].copy()

    def aggregate(group_cols: list[str]) -> pd.DataFrame:
        out = (
            df.groupby(group_cols, dropna=False)
            .agg(
                total_vidas=("vidas", "sum"),
                total_receita=("receita", "sum"),
                total_custo=("custo", "sum"),
                total_usuarios=("usuarios", "sum"),
                total_procedimentos=("procedimentos", "sum"),
            )
            .reset_index()
        )
        out["receita_media_por_vida"] = out["total_receita"] / out["total_vidas"].replace(0, pd.NA)
        out["custo_medio_por_vida"] = out["total_custo"] / out["total_vidas"].replace(0, pd.NA)
        out["sinistralidade_pct"] = out["total_custo"] / out["total_receita"].replace(0, pd.NA) * 100
        out["margem_operacional_pct"] = (
            (out["total_receita"] - out["total_custo"]) / out["total_receita"].replace(0, pd.NA) * 100
        )
        out["frequencia_utilizacao"] = out["total_usuarios"] / out["total_vidas"].replace(0, pd.NA)
        return out.fillna(0)

    monthly = aggregate(["ano_mes"]).sort_values("ano_mes")
    by_product = aggregate(["ano_mes", "produto"]).sort_values(["ano_mes", "produto"])
    by_region = aggregate(["ano_mes", "regiao"]).sort_values(["ano_mes", "regiao"])
    by_type = aggregate(["ano_mes", "tipo"]).sort_values(["ano_mes", "tipo"])

    latest_month = monthly["ano_mes"].max()
    latest = monthly[monthly["ano_mes"] == latest_month].iloc[0]
    product_latest = by_product[by_product["ano_mes"] == latest_month].copy()
    region_latest = by_region[by_region["ano_mes"] == latest_month].copy()
    type_latest = by_type[by_type["ano_mes"] == latest_month].copy()

    product_latest["deficitario"] = (
        (product_latest["sinistralidade_pct"] > 100) | (product_latest["margem_operacional_pct"] < 0)
    )

    product_trend = by_product.sort_values(["produto", "ano_mes"]).copy()
    product_trend["custo_mes_anterior"] = product_trend.groupby("produto")["custo_medio_por_vida"].shift(1)
    product_trend["variacao_custo_pct"] = (
        (product_trend["custo_medio_por_vida"] - product_trend["custo_mes_anterior"])
        / product_trend["custo_mes_anterior"].replace(0, pd.NA)
        * 100
    )
    cost_alerts = product_trend[
        (product_trend["variacao_custo_pct"] > 10) & (product_trend["total_vidas"] >= 30)
    ].copy()

    product_trend["vidas_anterior"] = product_trend.groupby("produto")["total_vidas"].shift(1)
    growth_alerts = product_trend[
        (product_trend["sinistralidade_pct"] > 90)
        & (product_trend["total_vidas"] > product_trend["vidas_anterior"])
        & (product_trend["vidas_anterior"] > 0)
    ].copy()
    growth_alerts["crescimento_vidas_pct"] = (
        (growth_alerts["total_vidas"] - growth_alerts["vidas_anterior"])
        / growth_alerts["vidas_anterior"]
        * 100
    )

    low_lives = product_latest[product_latest["total_vidas"] < 30].sort_values(
        ["total_vidas", "sinistralidade_pct"], ascending=[True, False]
    )

    return {
        "meta": {
            "latestMonth": latest_month,
            "generatedFrom": str(RAW_FILE.name),
        },
        "cards": [
            {"label": "Vidas", "value": num(latest["total_vidas"]), "hint": f"Competencia {latest_month}"},
            {"label": "Receita total", "value": money(latest["total_receita"]), "hint": "Premios/receitas no periodo"},
            {"label": "Custo total", "value": money(latest["total_custo"]), "hint": "Eventos assistenciais"},
            {"label": "Sinistralidade", "value": pct(latest["sinistralidade_pct"]), "hint": "Custo / Receita"},
            {"label": "Margem operacional", "value": pct(latest["margem_operacional_pct"]), "hint": "(Receita - Custo) / Receita"},
            {"label": "Frequencia", "value": f"{latest['frequencia_utilizacao']:.3f}", "hint": "Usuarios / Vidas"},
        ],
        "monthly": monthly.to_dict(orient="records"),
        "productLatest": product_latest.sort_values("sinistralidade_pct", ascending=False).to_dict(orient="records"),
        "regionLatest": region_latest.sort_values("sinistralidade_pct", ascending=False).to_dict(orient="records"),
        "typeLatest": type_latest.sort_values("tipo").to_dict(orient="records"),
        "deficitProducts": product_latest[product_latest["deficitario"]]
        .sort_values("sinistralidade_pct", ascending=False)
        .to_dict(orient="records"),
        "lowLives": low_lives.head(10).to_dict(orient="records"),
        "costAlerts": cost_alerts.sort_values("variacao_custo_pct", ascending=False).head(10).to_dict(orient="records"),
        "growthAlerts": growth_alerts.sort_values("sinistralidade_pct", ascending=False).head(10).to_dict(orient="records"),
    }


def build_html(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Indicadores Operadora de Saúde</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #f6f7f9;
      --ink: #17202a;
      --muted: #65717f;
      --line: #d9dee7;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-2: #b45309;
      --danger: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, Segoe UI, Arial, sans-serif;
      letter-spacing: 0;
    }}
    header {{
      padding: 28px 32px 18px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(1.5rem, 2.5vw, 2.25rem); }}
    h2 {{ margin: 0 0 14px; font-size: 1.05rem; }}
    h3 {{ margin: 0 0 8px; font-size: .98rem; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.45; }}
    main {{ padding: 20px 32px 40px; max-width: 1400px; margin: 0 auto; }}
    .grid {{ display: grid; gap: 16px; }}
    .cards {{ grid-template-columns: repeat(6, minmax(140px, 1fr)); }}
    .two {{ grid-template-columns: minmax(0, 1.4fr) minmax(320px, .8fr); }}
    .three {{ grid-template-columns: repeat(3, minmax(220px, 1fr)); }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .card {{ padding: 14px; min-height: 104px; }}
    .card .label {{ color: var(--muted); font-size: .78rem; text-transform: uppercase; font-weight: 700; }}
    .card .value {{ margin-top: 10px; font-size: 1.45rem; font-weight: 800; white-space: nowrap; }}
    .card .hint {{ margin-top: 8px; color: var(--muted); font-size: .8rem; }}
    .panel {{ padding: 16px; min-width: 0; }}
    .section {{ margin-top: 18px; }}
    .chart {{ height: 360px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid #edf0f4; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ color: var(--muted); font-size: .75rem; text-transform: uppercase; }}
    pre {{
      margin: 10px 0 10px;
      padding: 12px;
      overflow-x: auto;
      background: #101828;
      color: #eef2f7;
      border-radius: 8px;
      font-size: .82rem;
      line-height: 1.45;
    }}
    code {{
      font-family: Consolas, Monaco, "Courier New", monospace;
      font-size: .9em;
    }}
    p code {{
      padding: 1px 5px;
      background: #edf2f7;
      color: #243244;
      border-radius: 4px;
    }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 999px; background: #eef8f6; color: var(--accent); font-weight: 700; }}
    .danger {{ color: var(--danger); font-weight: 800; }}
    .qa {{ display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 12px; }}
    .qa article {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .qa p {{ color: #344050; }}
    @media (max-width: 1100px) {{
      .cards {{ grid-template-columns: repeat(3, minmax(160px, 1fr)); }}
      .two, .three, .qa {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      .cards {{ grid-template-columns: 1fr 1fr; }}
      .card .value {{ font-size: 1.1rem; white-space: normal; }}
      .chart {{ height: 320px; }}
      table {{ font-size: .78rem; }}
      th, td {{ padding: 8px 5px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Indicadores da Operadora de Saúde</h1>
    <p>Dashboard estático gerado a partir da base tratada. Última competência: <strong id="latest"></strong>.</p>
  </header>
  <main>
    <section class="grid cards" id="cards"></section>

    <section class="section grid two">
      <div class="panel">
        <h2>Evolução mensal</h2>
        <div id="trendChart" class="chart"></div>
      </div>
      <div class="panel">
        <h2>Comparativo por contrato</h2>
        <div id="typeChart" class="chart"></div>
      </div>
    </section>

    <section class="section grid two">
      <div class="panel">
        <h2>Produtos por sinistralidade</h2>
        <div id="productChart" class="chart"></div>
      </div>
      <div class="panel">
        <h2>Desempenho regional</h2>
        <div id="regionChart" class="chart"></div>
      </div>
    </section>

    <section class="section grid three">
      <div class="panel">
        <h2>Produtos deficitários</h2>
        <table id="deficitTable"></table>
      </div>
      <div class="panel">
        <h2>Aumento de custo por vida</h2>
        <table id="costTable"></table>
      </div>
      <div class="panel">
        <h2>Baixo volume de vidas</h2>
        <table id="lowLivesTable"></table>
      </div>
    </section>

    <section class="section panel">
      <h2>Respostas analíticas</h2>
      <div class="qa" id="qa"></div>
    </section>
  </main>

  <script>
    const DATA = {data};
    const brMoney = v => new Intl.NumberFormat('pt-BR', {{ style: 'currency', currency: 'BRL' }}).format(v || 0);
    const brInt = v => new Intl.NumberFormat('pt-BR', {{ maximumFractionDigits: 0 }}).format(v || 0);
    const brPct = v => `${{(v || 0).toFixed(1).replace('.', ',')}}%`;
    const fmt = {{displayModeBar: false, responsive: true}};
    const layoutBase = () => ({{
      margin: {{ l: 54, r: 20, t: 12, b: 46 }},
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
      font: {{ family: 'Inter, Segoe UI, Arial, sans-serif', color: '#17202a' }},
      xaxis: {{ gridcolor: '#edf0f4', automargin: true }},
      yaxis: {{ gridcolor: '#edf0f4', automargin: true }}
    }});

    document.getElementById('latest').textContent = DATA.meta.latestMonth;
    document.getElementById('cards').innerHTML = DATA.cards.map(card => `
      <article class="card">
        <div class="label">${{card.label}}</div>
        <div class="value">${{card.value}}</div>
        <div class="hint">${{card.hint}}</div>
      </article>
    `).join('');

    Plotly.newPlot('trendChart', [
      {{ x: DATA.monthly.map(d => d.ano_mes), y: DATA.monthly.map(d => d.sinistralidade_pct), name: 'Sinistralidade %', type: 'scatter', mode: 'lines+markers', line: {{ color: '#0f766e', width: 3 }} }},
      {{ x: DATA.monthly.map(d => d.ano_mes), y: DATA.monthly.map(d => d.margem_operacional_pct), name: 'Margem %', type: 'scatter', mode: 'lines+markers', line: {{ color: '#b45309', width: 3 }} }}
    ], {{ ...layoutBase(), xaxis: {{ ...layoutBase().xaxis, type: 'category' }}, yaxis: {{ ...layoutBase().yaxis, ticksuffix: '%', type: 'linear' }}, legend: {{ orientation: 'h', y: 1.12 }} }}, fmt);

    Plotly.newPlot('typeChart', [
      {{ x: DATA.typeLatest.map(d => d.tipo), y: DATA.typeLatest.map(d => d.receita_media_por_vida), name: 'Receita/vida', type: 'bar', marker: {{ color: '#2563eb' }} }},
      {{ x: DATA.typeLatest.map(d => d.tipo), y: DATA.typeLatest.map(d => d.custo_medio_por_vida), name: 'Custo/vida', type: 'bar', marker: {{ color: '#dc2626' }} }}
    ], {{ ...layoutBase(), barmode: 'group', xaxis: {{ ...layoutBase().xaxis, type: 'category' }}, yaxis: {{ ...layoutBase().yaxis, tickprefix: 'R$ ', type: 'linear' }}, legend: {{ orientation: 'h', y: 1.12 }} }}, fmt);

    const productTop = DATA.productLatest.filter(d => d.total_vidas >= 30).slice(0, 12).reverse();
    Plotly.newPlot('productChart', [
      {{
        y: productTop.map(d => d.produto),
        x: productTop.map(d => d.sinistralidade_pct),
        type: 'bar',
        orientation: 'h',
        text: productTop.map(d => `${{d.sinistralidade_pct.toFixed(1).replace('.', ',')}}%`),
        textposition: 'outside',
        cliponaxis: false,
        marker: {{ color: productTop.map(d => d.sinistralidade_pct > 100 ? '#b91c1c' : '#0f766e') }},
        hovertemplate: '<b>%{{y}}</b><br>Sinistralidade: %{{x:.1f}}%<br>Vidas: %{{customdata:,}}<extra></extra>',
        customdata: productTop.map(d => d.total_vidas)
      }}
    ], {{ ...layoutBase(), xaxis: {{ ...layoutBase().xaxis, ticksuffix: '%', type: 'linear' }}, yaxis: {{ ...layoutBase().yaxis, type: 'category', tickfont: {{ size: 11 }} }}, margin: {{ l: 150, r: 70, t: 12, b: 46 }} }}, fmt);

    Plotly.newPlot('regionChart', [
      {{ x: DATA.regionLatest.map(d => d.regiao), y: DATA.regionLatest.map(d => d.sinistralidade_pct), name: 'Sinistralidade', type: 'bar', marker: {{ color: '#0f766e' }} }},
      {{ x: DATA.regionLatest.map(d => d.regiao), y: DATA.regionLatest.map(d => d.margem_operacional_pct), name: 'Margem', type: 'scatter', mode: 'lines+markers', line: {{ color: '#b45309', width: 3 }} }}
    ], {{ ...layoutBase(), xaxis: {{ ...layoutBase().xaxis, type: 'category' }}, yaxis: {{ ...layoutBase().yaxis, ticksuffix: '%', type: 'linear' }}, legend: {{ orientation: 'h', y: 1.12 }} }}, fmt);

    function table(el, rows, columns, emptyText = 'Sem alertas na última competência.') {{
      const html = rows.length ? `
        <thead><tr>${{columns.map(c => `<th>${{c.label}}</th>`).join('')}}</tr></thead>
        <tbody>${{rows.map(r => `<tr>${{columns.map(c => `<td>${{c.format ? c.format(r[c.key], r) : (r[c.key] ?? '')}}</td>`).join('')}}</tr>`).join('')}}</tbody>
      ` : `<tbody><tr><td>${{emptyText}}</td></tr></tbody>`;
      document.getElementById(el).innerHTML = html;
    }}

    table('deficitTable', DATA.deficitProducts, [
      {{ key: 'produto', label: 'Produto' }},
      {{ key: 'total_vidas', label: 'Vidas', format: brInt }},
      {{ key: 'sinistralidade_pct', label: 'Sinist.', format: v => `<span class="danger">${{brPct(v)}}</span>` }},
      {{ key: 'margem_operacional_pct', label: 'Margem', format: brPct }}
    ]);
    table('costTable', DATA.costAlerts, [
      {{ key: 'produto', label: 'Produto' }},
      {{ key: 'ano_mes', label: 'Mês' }},
      {{ key: 'custo_medio_por_vida', label: 'Custo/vida', format: brMoney }},
      {{ key: 'variacao_custo_pct', label: 'Var.', format: brPct }}
    ]);
    table('lowLivesTable', DATA.lowLives, [
      {{ key: 'produto', label: 'Produto' }},
      {{ key: 'total_vidas', label: 'Vidas', format: brInt }},
      {{ key: 'sinistralidade_pct', label: 'Sinist.', format: brPct }}
    ]);

    const qa = [
      ['1. Indicadores', 'Receita média por vida mede o ticket médio mensal por beneficiário: <code>receita / vidas</code>. Custo médio por vida mede o gasto assistencial médio: <code>custo / vidas</code>. Margem operacional indica quanto sobra da receita após o custo assistencial: <code>(receita - custo) / receita</code>. Sinistralidade mostra o peso do custo sobre a receita: <code>custo / receita</code>. Frequência de utilização mede a proporção de vidas que utilizaram o plano no período: <code>usuários / vidas</code>.'],
      ['2. Baixo número de vidas', 'Em produtos com poucas vidas, a sinistralidade fica estatisticamente instável: um único evento caro pode elevar muito o percentual. Por isso, é importante aplicar volume mínimo de vidas, analisar mais de um período, usar média móvel, separar outliers e sinalizar a confiabilidade do indicador antes de concluir que o produto é ruim.'],
      ['3. Produtos deficitários', 'Um produto pode ser classificado como deficitário quando apresenta sinistralidade acima de 100%, margem operacional negativa ou custo médio por vida superior à receita média por vida. A análise fica mais forte quando o problema se repete por várias competências e ocorre em volume relevante de vidas.'],
      ['4. Desempenho regional', 'Para comparar regiões, eu usaria total de vidas, receita média por vida, custo médio por vida, sinistralidade, margem operacional, frequência de utilização e tendência mensal. Isso permite separar regiões com problema de preço, regiões com maior uso assistencial e regiões com baixa escala operacional.'],
      ['5. Coletivo x Individual', 'A comparação entre Coletivo e Individual deve considerar volume de vidas, ticket médio, custo por vida, frequência de utilização, sinistralidade e margem. O Coletivo pode ter escala maior e preço menor por vida; o Individual pode ter receita média maior, mas também perfil de uso diferente. A leitura correta depende do mix, da região, do produto e da recorrência dos resultados.'],
      ['6. Pseudo-SQL', `<pre><code>SELECT
    produto,
    DATE_FORMAT(periodo, '%Y-%m') AS ano_mes,
    SUM(receita) AS receita_total,
    SUM(custo) AS custo_total,
    ROUND(SUM(custo) / NULLIF(SUM(receita), 0) * 100, 2) AS sinistralidade_pct
FROM fato_assistencial
GROUP BY
    produto,
    DATE_FORMAT(periodo, '%Y-%m')
ORDER BY
    ano_mes,
    produto;</code></pre><p>A lógica agrupa os registros por produto e competência, soma receita e custo do período e calcula a sinistralidade pela razão entre custo total e receita total. O <code>NULLIF</code> evita divisão por zero quando a receita total do grupo for igual a zero.</p>`],
      ['7. Aumento de custo', 'Para identificar aumento relevante de custo por vida, calcule o custo por vida mensal por produto e compare com o mês anterior usando <code>LAG</code>. Um alerta pode ser criado quando a variação mensal superar 10%, desde que o produto tenha volume mínimo de vidas para evitar falso positivo por baixa base.'],
      ['8. Modelo dimensional', 'O modelo dimensional teria uma tabela fato assistencial com medidas como receita, custo, vidas, usuários e procedimentos. As dimensões seriam tempo, produto, tipo de contrato, região/localidade, vertical e, se disponível, prestador ou rede. Esse desenho facilita análises por período, produto, contrato e território.'],
      ['9. Decisão estratégica', 'Os indicadores suportam decisões de reajuste, revisão de preço, redesenho de produto, negociação com rede credenciada, gestão de utilização, expansão ou retração regional e priorização comercial. Eles também ajudam a diferenciar problema estrutural de preço de um evento pontual de custo.'],
      ['10. Crescimento + sinistralidade > 90%', 'Quando um produto cresce em vidas e passa de 90% de sinistralidade, eu analisaria perfil das novas vidas, região de entrada, canal de venda, carência, tipos de procedimento, eventos de alto custo, prestadores utilizados, faixa etária e suficiência do preço. Também avaliaria se o aumento é pontual ou tendência de deterioração da carteira.']
    ];
    document.getElementById('qa').innerHTML = qa.map(([title, text]) => {{
      const body = text.trim().startsWith('<') ? text : `<p>${{text}}</p>`;
      return `<article><h3>${{title}}</h3>${{body}}</article>`;
    }}).join('');
  </script>
</body>
</html>
"""


def main() -> None:
    payload = prepare_data()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(build_html(payload), encoding="utf-8")
    print(f"Dashboard salvo em: {OUT_FILE}")


if __name__ == "__main__":
    main()
