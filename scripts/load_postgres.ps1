param(
    [string]$DatabaseUrl = "postgres://postgres:251288@n8n_saudde:5432/n8n?sslmode=disable"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$SchemaFile = Join-Path $ProjectRoot "sql\postgres_schema.sql"
$CsvFile = Join-Path $ProjectRoot "outputs\postgres\fato_assistencial.csv"

if (-not (Test-Path -LiteralPath $Psql)) {
    throw "psql nao encontrado em: $Psql"
}

if (-not (Test-Path -LiteralPath $SchemaFile)) {
    throw "Schema nao encontrado em: $SchemaFile"
}

if (-not (Test-Path -LiteralPath $CsvFile)) {
    throw "CSV nao encontrado em: $CsvFile"
}

Write-Host "Criando tabela e views..."
& $Psql $DatabaseUrl -v ON_ERROR_STOP=1 -f $SchemaFile

$CsvForPsql = $CsvFile.Replace("\", "/")
$CopyCommand = "\copy fato_assistencial (periodo, ano, mes, ano_mes, tipo, vertical, cidade, uf, regiao, produto, vidas, receita, custo, usuarios, procedimentos) FROM '$CsvForPsql' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');"

Write-Host "Importando CSV..."
& $Psql $DatabaseUrl -v ON_ERROR_STOP=1 -c $CopyCommand

Write-Host "Validando carga..."
& $Psql $DatabaseUrl -v ON_ERROR_STOP=1 -c "SELECT COUNT(*) AS total_linhas FROM fato_assistencial;"
& $Psql $DatabaseUrl -v ON_ERROR_STOP=1 -c "SELECT ano_mes, ROUND(SUM(custo) / NULLIF(SUM(receita), 0) * 100, 2) AS sinistralidade_pct FROM fato_assistencial GROUP BY ano_mes ORDER BY ano_mes LIMIT 5;"

Write-Host "Carga concluida."
