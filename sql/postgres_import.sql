\copy fato_assistencial (
    periodo,
    ano,
    mes,
    ano_mes,
    tipo,
    vertical,
    cidade,
    uf,
    regiao,
    produto,
    vidas,
    receita,
    custo,
    usuarios,
    procedimentos
) FROM 'outputs/postgres/fato_assistencial.csv'
WITH (
    FORMAT csv,
    HEADER true,
    ENCODING 'UTF8'
);
