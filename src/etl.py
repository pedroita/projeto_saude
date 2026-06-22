"""
etl.py — Pipeline de dados: xlsx → DuckDB
Operadora de Planos de Saúde

Fluxo:
  1. Lê o xlsx bruto
  2. Limpa e padroniza
  3. Carrega no DuckDB (tabela: fato_assistencial)
  4. Cria view com indicadores calculados (vw_indicadores)
"""

import pandas as pd
import duckdb
from pathlib import Path

# ── Caminhos ────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
RAW_FILE   = BASE_DIR / "data" / "raw"   / "prova_idea.xlsx"
DB_FILE    = BASE_DIR / "data" / "processed" / "saude.duckdb"


def extrair(path: Path) -> pd.DataFrame:
    print(f"[ETL] Lendo {path.name} ...")
    df = pd.read_excel(path, sheet_name="base")
    print(f"[ETL] {len(df):,} linhas carregadas.")
    return df


def transformar(df: pd.DataFrame) -> pd.DataFrame:
    print("[ETL] Transformando ...")

    df.columns = [c.lower() for c in df.columns]

    df["periodo"] = pd.to_datetime(df["periodo"])

    df["ano"]  = df["periodo"].dt.year
    df["mes"]  = df["periodo"].dt.month
    df["ano_mes"] = df["periodo"].dt.to_period("M").astype(str)

    for col in ["tipo", "vertical", "cidade", "uf", "regiao", "produto"]:
        df[col] = df[col].str.strip().str.upper()

    antes = len(df)
    df = df[~((df["receita"] == 0) & (df["custo"] == 0))].copy()
    print(f"[ETL] {antes - len(df):,} linhas sem movimento removidas → {len(df):,} restantes.")

    df["vidas_safe"]   = df["vidas"].replace(0, None)
    df["receita_safe"] = df["receita"].replace(0, None)

    df["receita_media_por_vida"]  = df["receita"] / df["vidas_safe"]
    df["custo_medio_por_vida"]    = df["custo"]   / df["vidas_safe"]
    df["sinistralidade_pct"]      = (df["custo"]  / df["receita_safe"]) * 100
    df["margem_operacional_pct"]  = ((df["receita"] - df["custo"]) / df["receita_safe"]) * 100
    df["frequencia_utilizacao"]   = df["usuarios"] / df["vidas_safe"]

    print("[ETL] KPIs calculados.")
    return df


def carregar(df: pd.DataFrame, db_path: Path) -> duckdb.DuckDBPyConnection:
    print(f"[ETL] Carregando no DuckDB → {db_path.name} ...")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))

    con.execute("DROP TABLE IF EXISTS fato_assistencial")
    con.execute("""
        CREATE TABLE fato_assistencial AS
        SELECT * FROM df
    """)

    con.execute("DROP VIEW IF EXISTS vw_indicadores")
    con.execute("""
        CREATE VIEW vw_indicadores AS
        SELECT
            ano_mes,
            ano,
            mes,
            tipo,
            vertical,
            regiao,
            uf,
            produto,

            -- Volumes
            SUM(vidas)         AS total_vidas,
            SUM(receita)       AS total_receita,
            SUM(custo)         AS total_custo,
            SUM(usuarios)      AS total_usuarios,
            SUM(procedimentos) AS total_procedimentos,

            -- KPIs
            SUM(receita) / NULLIF(SUM(vidas),   0) AS receita_media_por_vida,
            SUM(custo)   / NULLIF(SUM(vidas),   0) AS custo_medio_por_vida,
            SUM(custo)   / NULLIF(SUM(receita), 0) * 100 AS sinistralidade_pct,
            (SUM(receita) - SUM(custo)) / NULLIF(SUM(receita), 0) * 100 AS margem_operacional_pct,
            SUM(usuarios) / NULLIF(SUM(vidas),  0) AS frequencia_utilizacao

        FROM fato_assistencial
        GROUP BY ano_mes, ano, mes, tipo, vertical, regiao, uf, produto
    """)

    con.execute("DROP VIEW IF EXISTS vw_resumo_regional")
    con.execute("""
        CREATE VIEW vw_resumo_regional AS
        SELECT
            ano_mes,
            regiao,
            SUM(vidas)    AS total_vidas,
            SUM(receita)  AS total_receita,
            SUM(custo)    AS total_custo,
            SUM(custo)   / NULLIF(SUM(receita), 0) * 100 AS sinistralidade_pct,
            (SUM(receita) - SUM(custo)) / NULLIF(SUM(receita), 0) * 100 AS margem_pct
        FROM fato_assistencial
        GROUP BY ano_mes, regiao
    """)

    con.execute("DROP VIEW IF EXISTS vw_tipo_contrato")
    con.execute("""
        CREATE VIEW vw_tipo_contrato AS
        SELECT
            ano_mes,
            tipo,
            SUM(vidas)    AS total_vidas,
            SUM(receita)  AS total_receita,
            SUM(custo)    AS total_custo,
            SUM(custo)   / NULLIF(SUM(receita), 0) * 100 AS sinistralidade_pct,
            SUM(receita) / NULLIF(SUM(vidas),   0) AS receita_media_por_vida,
            SUM(custo)   / NULLIF(SUM(vidas),   0) AS custo_medio_por_vida,
            SUM(usuarios)/ NULLIF(SUM(vidas),   0) AS frequencia_utilizacao
        FROM fato_assistencial
        GROUP BY ano_mes, tipo
    """)

    n = con.execute("SELECT COUNT(*) FROM fato_assistencial").fetchone()[0]
    print(f"[ETL] ✓ {n:,} registros em fato_assistencial")
    print(f"[ETL] ✓ Views criadas: vw_indicadores | vw_resumo_regional | vw_tipo_contrato")
    return con


def validar(con: duckdb.DuckDBPyConnection):
    print("\n[VALIDAÇÃO] Top 5 produtos por sinistralidade (último período):")
    print(con.execute("""
        SELECT produto, ano_mes, ROUND(sinistralidade_pct, 1) AS sinistralidade_pct
        FROM vw_indicadores
        WHERE ano_mes = (SELECT MAX(ano_mes) FROM vw_indicadores)
          AND total_vidas >= 10
        ORDER BY sinistralidade_pct DESC
        LIMIT 5
    """).df().to_string(index=False))

    print("\n[VALIDAÇÃO] Sinistralidade por tipo de contrato:")
    print(con.execute("""
        SELECT tipo, ano_mes,
               ROUND(sinistralidade_pct, 1) AS sinistralidade_pct,
               ROUND(receita_media_por_vida, 2) AS receita_media_por_vida
        FROM vw_tipo_contrato
        ORDER BY ano_mes, tipo
        LIMIT 10
    """).df().to_string(index=False))


if __name__ == "__main__":
    df_raw    = extrair(RAW_FILE)
    df_clean  = transformar(df_raw)
    con       = carregar(df_clean, DB_FILE)
    validar(con)
    con.close()
    print(f"\n[ETL] Concluído. Banco salvo em: {DB_FILE}")