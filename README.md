# Projeto Saude - Indicadores Operadora

Projeto desenvolvido para analisar indicadores de uma operadora de planos de saude, com foco em receita, custo, sinistralidade, margem operacional, frequencia de utilizacao, comparativos por produto, tipo de contrato e regiao.

## Links da entrega

- Dashboard no Metabase: https://n8n-metabase.lsgq1d.easypanel.host/public/dashboard/30a40ebf-faaf-4811-b39c-f97453b911f5
- Dashboard estatico com dados extraidos e embutidos: https://projeto-saude-pi.vercel.app/
- Repositorio GitHub: https://github.com/pedroita/projeto_saude

## Objetivo

O objetivo da solucao foi transformar a base bruta em indicadores de negocio e disponibilizar a analise de duas formas:

1. Dashboard em Metabase conectado a um banco PostgreSQL na VPS.
2. Dashboard estatico publicado na web, gerado a partir dos dados extraidos e embutidos no HTML.

A versao em Metabase e a principal para analise dinamica. A versao estatica funciona como alternativa publica simples, sem dependencia de Power BI ou de conexao direta com banco.

## Estrutura do projeto

```text
data/
  raw/
    prova_idea.xlsx              # Base original
  processed/
    saude.duckdb                 # Banco local usado no processo inicial

docs/
  index.html                     # Dashboard estatico gerado

outputs/
  postgres/
    fato_assistencial.csv        # CSV tratado para carga no PostgreSQL

scripts/
  load_postgres.ps1              # Carga no Postgres a partir do Windows
  load_postgres.sh               # Carga no Postgres a partir da VPS/Linux

sql/
  indicadores.sql                # Consultas analiticas iniciais
  postgres_schema.sql            # Schema, indices e views no PostgreSQL
  postgres_import.sql            # Exemplo de importacao via psql

src/
  etl.py                         # ETL inicial para DuckDB
  export_postgres_csv.py         # Exporta CSV tratado para PostgreSQL
  generate_dashboard.py          # Gera o dashboard estatico em docs/index.html

requirements.txt                 # Dependencias Python
```

## Fonte dos dados

A fonte original esta em:

```text
data/raw/prova_idea.xlsx
```

A aba utilizada e:

```text
base
```

Campos principais usados:

- `PERIODO`
- `TIPO`
- `VERTICAL`
- `CIDADE`
- `UF`
- `REGIAO`
- `PRODUTO`
- `VIDAS`
- `RECEITA`
- `CUSTO`
- `USUARIOS`
- `PROCEDIMENTOS`

## Indicadores calculados

Os principais indicadores calculados foram:

- Receita media por vida: `receita / vidas`
- Custo medio por vida: `custo / vidas`
- Sinistralidade (%): `custo / receita * 100`
- Margem operacional (%): `(receita - custo) / receita * 100`
- Frequencia de utilizacao: `usuarios / vidas`

Tambem foram criados alertas e analises para:

- Produtos financeiramente deficitarios.
- Produtos com baixo volume de vidas.
- Aumento relevante de custo por vida ao longo do tempo.
- Comparacao entre contratos Coletivo e Individual.
- Comparacao de desempenho regional.

## Pipeline de dados

### 1. Leitura e tratamento

O arquivo `src/export_postgres_csv.py` le a planilha original, padroniza os nomes das colunas e cria campos auxiliares de tempo:

- `ano`
- `mes`
- `ano_mes`

Tambem padroniza campos textuais para maiusculo e remove linhas sem movimento, isto e, linhas com receita e custo iguais a zero.

### 2. Exportacao para CSV

Para gerar o CSV tratado:

```bash
python src/export_postgres_csv.py
```

Saida gerada:

```text
outputs/postgres/fato_assistencial.csv
```

Na carga executada na VPS, o arquivo gerado teve:

```text
8.580 linhas
```

### 3. Carga no PostgreSQL

O banco PostgreSQL foi criado na VPS via EasyPanel.

String de conexao usada na rede interna:

```text
postgres://postgres:251288@n8n_saudde:5432/n8n?sslmode=disable
```

Como o host `n8n_saudde` e interno da rede Docker/EasyPanel, a carga foi executada dentro da VPS usando um container temporario com a imagem `postgres:17`.

Schema criado:

```text
sql/postgres_schema.sql
```

Esse script cria:

- Tabela `fato_assistencial`
- Indices por periodo, competencia, produto, regiao e tipo
- View `vw_indicadores`
- View `vw_resumo_regional`
- View `vw_tipo_contrato`

### 4. Views usadas no Metabase

As visualizacoes do Metabase foram construidas principalmente sobre as views:

```text
vw_indicadores
vw_resumo_regional
vw_tipo_contrato
```

Isso evita repetir regras de calculo em todos os graficos e deixa a analise mais consistente.

## Banco de dados

Tabela principal:

```text
fato_assistencial
```

Essa tabela armazena a base tratada em nivel analitico.

Views:

```text
vw_indicadores
```

View principal por competencia, produto, tipo, vertical, regiao e UF. Contem totais e KPIs.

```text
vw_resumo_regional
```

Resumo mensal por regiao, usado para comparar sinistralidade e margem regional.

```text
vw_tipo_contrato
```

Resumo mensal por tipo de contrato, usado para comparar Coletivo e Individual.

## Dashboard no Metabase

Link:

```text
https://n8n-metabase.lsgq1d.easypanel.host/public/dashboard/30a40ebf-faaf-4811-b39c-f97453b911f5
```

O dashboard no Metabase foi criado com SQL nativo sobre as views do PostgreSQL.

Visualizacoes criadas:

1. KPIs gerais da ultima competencia.
2. Evolucao mensal de sinistralidade e margem.
3. Receita por vida x custo por vida por tipo de contrato.
4. Produtos por sinistralidade.
5. Desempenho regional.
6. Produtos deficitarios.
7. Aumento de custo por vida.
8. Produtos com baixo volume de vidas.

### Exemplos de consultas usadas

Evolucao mensal:

```sql
SELECT
    ano_mes AS "Competencia",
    ROUND(SUM(total_custo) / NULLIF(SUM(total_receita), 0) * 100, 2) AS "Sinistralidade %",
    ROUND((SUM(total_receita) - SUM(total_custo)) / NULLIF(SUM(total_receita), 0) * 100, 2) AS "Margem %"
FROM vw_indicadores
GROUP BY ano_mes
ORDER BY ano_mes;
```

Produtos por sinistralidade:

```sql
SELECT
    produto AS "Produto",
    SUM(total_vidas) AS "Vidas",
    ROUND(SUM(total_custo) / NULLIF(SUM(total_receita), 0) * 100, 2) AS "Sinistralidade %"
FROM vw_indicadores
WHERE ano_mes = (SELECT MAX(ano_mes) FROM vw_indicadores)
GROUP BY produto
HAVING SUM(total_vidas) >= 30
ORDER BY "Sinistralidade %" DESC
LIMIT 12;
```

Desempenho regional:

```sql
SELECT
    regiao AS "Regiao",
    SUM(total_vidas) AS "Vidas",
    ROUND(SUM(total_custo) / NULLIF(SUM(total_receita), 0) * 100, 2) AS "Sinistralidade %",
    ROUND((SUM(total_receita) - SUM(total_custo)) / NULLIF(SUM(total_receita), 0) * 100, 2) AS "Margem %"
FROM vw_resumo_regional
WHERE ano_mes = (SELECT MAX(ano_mes) FROM vw_resumo_regional)
GROUP BY regiao
ORDER BY "Sinistralidade %" DESC;
```

## Dashboard estatico

Link:

```text
https://projeto-saude-pi.vercel.app/
```

Esse dashboard foi gerado pelo script:

```text
src/generate_dashboard.py
```

Ele le a base original, calcula os indicadores com `pandas` e gera:

```text
docs/index.html
```

Importante: nessa versao, os dados ficam extraidos e embutidos no proprio HTML em uma variavel JavaScript. Por isso, o dashboard estatico nao consulta o banco em tempo real. Ele e uma publicacao simples da analise, com os dados ja preparados.

Para regenerar:

```bash
python src/generate_dashboard.py
```

## Como reproduzir localmente

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Gerar CSV para PostgreSQL:

```bash
python src/export_postgres_csv.py
```

Gerar dashboard estatico:

```bash
python src/generate_dashboard.py
```

## Como carregar no PostgreSQL pela VPS

Na VPS, apos clonar o repositorio e garantir que a base esta em `data/raw/prova_idea.xlsx`, gerar o CSV:

```bash
docker run --rm \
  -v "$PWD:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install pandas openpyxl && python src/export_postgres_csv.py"
```

Criar schema:

```bash
docker run --rm \
  --network easypanel-n8n \
  -v "$PWD:/app" \
  -w /app \
  postgres:17 \
  psql "postgres://postgres:251288@n8n_saudde:5432/n8n?sslmode=disable" \
  -v ON_ERROR_STOP=1 \
  -f sql/postgres_schema.sql
```

Importar CSV:

```bash
docker run --rm \
  --network easypanel-n8n \
  -v "$PWD:/app" \
  -w /app \
  postgres:17 \
  psql "postgres://postgres:251288@n8n_saudde:5432/n8n?sslmode=disable" \
  -v ON_ERROR_STOP=1 \
  -c "\copy fato_assistencial (periodo, ano, mes, ano_mes, tipo, vertical, cidade, uf, regiao, produto, vidas, receita, custo, usuarios, procedimentos) FROM '/app/outputs/postgres/fato_assistencial.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');"
```

Validar carga:

```bash
docker run --rm \
  --network easypanel-n8n \
  postgres:17 \
  psql "postgres://postgres:251288@n8n_saudde:5432/n8n?sslmode=disable" \
  -c "SELECT COUNT(*) FROM fato_assistencial;"
```

Resultado esperado:

```text
8580
```

## Respostas analiticas contempladas

A entrega tambem contempla os pontos analiticos solicitados:

1. Definicao dos indicadores: receita media por vida, custo medio por vida, margem operacional, sinistralidade e frequencia de utilizacao.
2. Cuidados com sinistralidade em produtos com baixo numero de vidas.
3. Identificacao de produtos financeiramente deficitarios.
4. Indicadores para comparar desempenho regional.
5. Comparacao entre contratos Coletivo e Individual.
6. Logica SQL para calcular sinistralidade por produto e periodo.
7. Identificacao de aumento relevante de custo por vida ao longo do tempo.
8. Proposta de modelo dimensional.
9. Uso dos indicadores para decisao estrategica.
10. Analises adicionais para produto com crescimento de vidas e sinistralidade acima de 90%.

## Observacoes

- O dashboard Metabase e a versao recomendada para exploracao dos dados.
- O dashboard estatico e uma versao publicada com dados extraidos e embutidos, sem conexao em tempo real.
- Produtos com baixo numero de vidas devem ser analisados com cuidado, pois a sinistralidade pode oscilar muito com poucos beneficiarios.
- Produtos com sinistralidade acima de 100% ou margem negativa foram tratados como financeiramente deficitarios.
