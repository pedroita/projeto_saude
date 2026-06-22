DROP VIEW IF EXISTS vw_tipo_contrato;
DROP VIEW IF EXISTS vw_resumo_regional;
DROP VIEW IF EXISTS vw_indicadores;
DROP TABLE IF EXISTS fato_assistencial;

CREATE TABLE fato_assistencial (
    id BIGSERIAL PRIMARY KEY,
    periodo DATE NOT NULL,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    ano_mes CHAR(7) NOT NULL,
    tipo VARCHAR(50),
    vertical VARCHAR(50),
    cidade VARCHAR(120),
    uf CHAR(2),
    regiao VARCHAR(50),
    produto VARCHAR(120),
    vidas INTEGER DEFAULT 0,
    receita NUMERIC(15, 2) DEFAULT 0,
    custo NUMERIC(15, 2) DEFAULT 0,
    usuarios INTEGER DEFAULT 0,
    procedimentos INTEGER DEFAULT 0
);

CREATE INDEX idx_fato_periodo ON fato_assistencial (periodo);
CREATE INDEX idx_fato_ano_mes ON fato_assistencial (ano_mes);
CREATE INDEX idx_fato_produto ON fato_assistencial (produto);
CREATE INDEX idx_fato_regiao ON fato_assistencial (regiao);
CREATE INDEX idx_fato_tipo ON fato_assistencial (tipo);

CREATE OR REPLACE VIEW vw_indicadores AS
SELECT
    ano_mes,
    ano,
    mes,
    tipo,
    vertical,
    regiao,
    uf,
    produto,
    SUM(vidas) AS total_vidas,
    SUM(receita) AS total_receita,
    SUM(custo) AS total_custo,
    SUM(usuarios) AS total_usuarios,
    SUM(procedimentos) AS total_procedimentos,
    SUM(receita) / NULLIF(SUM(vidas), 0) AS receita_media_por_vida,
    SUM(custo) / NULLIF(SUM(vidas), 0) AS custo_medio_por_vida,
    SUM(custo) / NULLIF(SUM(receita), 0) * 100 AS sinistralidade_pct,
    (SUM(receita) - SUM(custo)) / NULLIF(SUM(receita), 0) * 100 AS margem_operacional_pct,
    SUM(usuarios)::NUMERIC / NULLIF(SUM(vidas), 0) AS frequencia_utilizacao
FROM fato_assistencial
GROUP BY ano_mes, ano, mes, tipo, vertical, regiao, uf, produto;

CREATE OR REPLACE VIEW vw_resumo_regional AS
SELECT
    ano_mes,
    regiao,
    SUM(vidas) AS total_vidas,
    SUM(receita) AS total_receita,
    SUM(custo) AS total_custo,
    SUM(custo) / NULLIF(SUM(receita), 0) * 100 AS sinistralidade_pct,
    (SUM(receita) - SUM(custo)) / NULLIF(SUM(receita), 0) * 100 AS margem_pct
FROM fato_assistencial
GROUP BY ano_mes, regiao;

CREATE OR REPLACE VIEW vw_tipo_contrato AS
SELECT
    ano_mes,
    tipo,
    SUM(vidas) AS total_vidas,
    SUM(receita) AS total_receita,
    SUM(custo) AS total_custo,
    SUM(custo) / NULLIF(SUM(receita), 0) * 100 AS sinistralidade_pct,
    SUM(receita) / NULLIF(SUM(vidas), 0) AS receita_media_por_vida,
    SUM(custo) / NULLIF(SUM(vidas), 0) AS custo_medio_por_vida,
    SUM(usuarios)::NUMERIC / NULLIF(SUM(vidas), 0) AS frequencia_utilizacao
FROM fato_assistencial
GROUP BY ano_mes, tipo;
