CREATE TABLE IF NOT EXISTS fato_assistencial (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    periodo DATE NOT NULL,
    ano INT NOT NULL,
    mes INT NOT NULL,
    ano_mes CHAR(7) NOT NULL,
    tipo VARCHAR(50),
    vertical VARCHAR(50),
    cidade VARCHAR(120),
    uf CHAR(2),
    regiao VARCHAR(50),
    produto VARCHAR(120),
    vidas INT DEFAULT 0,
    receita DECIMAL(15, 2) DEFAULT 0,
    custo DECIMAL(15, 2) DEFAULT 0,
    usuarios INT DEFAULT 0,
    procedimentos INT DEFAULT 0,
    INDEX idx_fato_periodo (periodo),
    INDEX idx_fato_ano_mes (ano_mes),
    INDEX idx_fato_produto (produto),
    INDEX idx_fato_regiao (regiao),
    INDEX idx_fato_tipo (tipo)
);

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
    SUM(usuarios) / NULLIF(SUM(vidas), 0) AS frequencia_utilizacao
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
    SUM(usuarios) / NULLIF(SUM(vidas), 0) AS frequencia_utilizacao
FROM fato_assistencial
GROUP BY ano_mes, tipo;
