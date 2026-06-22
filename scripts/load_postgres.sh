#!/usr/bin/env bash
set -euo pipefail

DATABASE_URL="${1:-postgres://postgres:251288@n8n_saudde:5432/n8n?sslmode=disable}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA_FILE="$PROJECT_DIR/sql/postgres_schema.sql"
CSV_FILE="$PROJECT_DIR/outputs/postgres/fato_assistencial.csv"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql nao encontrado. Instale o cliente Postgres ou rode dentro de um container que tenha psql."
  exit 1
fi

if [ ! -f "$SCHEMA_FILE" ]; then
  echo "Schema nao encontrado: $SCHEMA_FILE"
  exit 1
fi

if [ ! -f "$CSV_FILE" ]; then
  echo "CSV nao encontrado: $CSV_FILE"
  exit 1
fi

echo "Criando tabela e views..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$SCHEMA_FILE"

echo "Importando CSV..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "\copy fato_assistencial (periodo, ano, mes, ano_mes, tipo, vertical, cidade, uf, regiao, produto, vidas, receita, custo, usuarios, procedimentos) FROM '$CSV_FILE' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');"

echo "Validando carga..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT COUNT(*) AS total_linhas FROM fato_assistencial;"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT ano_mes, ROUND(SUM(custo) / NULLIF(SUM(receita), 0) * 100, 2) AS sinistralidade_pct FROM fato_assistencial GROUP BY ano_mes ORDER BY ano_mes LIMIT 5;"

echo "Carga concluida."
