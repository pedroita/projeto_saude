-- ============================================================
-- indicadores.sql
-- Queries para análise de indicadores — Operadora de Saúde
-- Banco: saude.duckdb  |  Tabela: fato_assistencial
-- ============================================================


-- ── Q1: Indicadores base ──────────────────────────────────────────────────
-- Receita Média por Vida, Custo Médio por Vida, Sinistralidade,
-- Margem Operacional e Frequência de Utilização por produto e período

SELECT
    ano_mes,
    produto,
    total_vidas,
    ROUND(receita_media_por_vida,  2) AS receita_media_por_vida,
    ROUND(custo_medio_por_vida,    2) AS custo_medio_por_vida,
    ROUND(sinistralidade_pct,      1) AS sinistralidade_pct,
    ROUND(margem_operacional_pct,  1) AS margem_operacional_pct,
    ROUND(frequencia_utilizacao,   4) AS frequencia_utilizacao
FROM vw_indicadores
ORDER BY ano_mes, sinistralidade_pct DESC;


-- ── Q2: Produtos com baixo número de vidas (instabilidade estatística) ────
-- Cuidado: sinistralidade oscila muito com poucos beneficiários

SELECT
    produto,
    ano_mes,
    total_vidas,
    ROUND(sinistralidade_pct, 1) AS sinistralidade_pct
FROM vw_indicadores
WHERE total_vidas < 30
  AND sinistralidade_pct IS NOT NULL
ORDER BY total_vidas ASC, sinistralidade_pct DESC;


-- ── Q3: Produtos financeiramente deficitários ─────────────────────────────
-- Critério: sinistralidade > 100% OU margem negativa

SELECT
    produto,
    ano_mes,
    total_vidas,
    ROUND(total_receita, 2)          AS total_receita,
    ROUND(total_custo,   2)          AS total_custo,
    ROUND(sinistralidade_pct,   1)   AS sinistralidade_pct,
    ROUND(margem_operacional_pct, 1) AS margem_operacional_pct
FROM vw_indicadores
WHERE sinistralidade_pct > 100
   OR margem_operacional_pct < 0
ORDER BY sinistralidade_pct DESC;


-- ── Q4: Comparação de desempenho regional ────────────────────────────────

SELECT
    regiao,
    ano_mes,
    total_vidas,
    ROUND(total_receita, 2)         AS total_receita,
    ROUND(total_custo,   2)         AS total_custo,
    ROUND(sinistralidade_pct,   1)  AS sinistralidade_pct,
    ROUND(margem_pct,           1)  AS margem_pct
FROM vw_resumo_regional
ORDER BY ano_mes, sinistralidade_pct DESC;


-- ── Q5: COLETIVO vs INDIVIDUAL ────────────────────────────────────────────

SELECT
    tipo,
    ano_mes,
    total_vidas,
    ROUND(receita_media_por_vida, 2) AS receita_media_por_vida,
    ROUND(custo_medio_por_vida,   2) AS custo_medio_por_vida,
    ROUND(sinistralidade_pct,     1) AS sinistralidade_pct,
    ROUND(frequencia_utilizacao,  4) AS frequencia_utilizacao
FROM vw_tipo_contrato
ORDER BY ano_mes, tipo;


-- ── Q6: Sinistralidade por produto e período (lógica SQL principal) ───────

SELECT
    STRFTIME(periodo, '%Y-%m')           AS ano_mes,
    produto,
    SUM(receita)                          AS receita_total,
    SUM(custo)                            AS custo_total,
    SUM(custo) / NULLIF(SUM(receita), 0) * 100 AS sinistralidade_pct
FROM fato_assistencial
GROUP BY STRFTIME(periodo, '%Y-%m'), produto
ORDER BY ano_mes, sinistralidade_pct DESC;


-- ── Q7: Tendência de custo por vida ao longo do tempo ─────────────────────
-- Identifica aumento relevante: variação > 10% mês a mês

WITH mensal AS (
    SELECT
        produto,
        ano_mes,
        SUM(custo) / NULLIF(SUM(vidas), 0) AS custo_por_vida
    FROM fato_assistencial
    GROUP BY produto, ano_mes
),
com_lag AS (
    SELECT
        produto,
        ano_mes,
        custo_por_vida,
        LAG(custo_por_vida) OVER (PARTITION BY produto ORDER BY ano_mes) AS custo_mes_anterior,
        (custo_por_vida - LAG(custo_por_vida) OVER (PARTITION BY produto ORDER BY ano_mes))
            / NULLIF(LAG(custo_por_vida) OVER (PARTITION BY produto ORDER BY ano_mes), 0) * 100
            AS variacao_pct
    FROM mensal
)
SELECT
    produto,
    ano_mes,
    ROUND(custo_por_vida,    2) AS custo_por_vida,
    ROUND(custo_mes_anterior, 2) AS custo_mes_anterior,
    ROUND(variacao_pct,       1) AS variacao_pct
FROM com_lag
WHERE variacao_pct > 10
ORDER BY variacao_pct DESC;


-- ── Q10: Produto com crescimento de vidas + sinistralidade > 90% ─────────
-- Análises adicionais recomendadas

WITH crescimento AS (
    SELECT
        produto,
        ano_mes,
        total_vidas,
        sinistralidade_pct,
        LAG(total_vidas) OVER (PARTITION BY produto ORDER BY ano_mes) AS vidas_anterior
    FROM vw_indicadores
)
SELECT
    produto,
    ano_mes,
    total_vidas,
    vidas_anterior,
    ROUND((total_vidas - vidas_anterior) / NULLIF(vidas_anterior, 0) * 100, 1) AS crescimento_vidas_pct,
    ROUND(sinistralidade_pct, 1) AS sinistralidade_pct
FROM crescimento
WHERE sinistralidade_pct > 90
  AND total_vidas > vidas_anterior
ORDER BY sinistralidade_pct DESC;z