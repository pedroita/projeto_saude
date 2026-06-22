from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "raw" / "prova_idea.xlsx"
OUT_DIR = BASE_DIR / "outputs" / "postgres"
OUT_FILE = OUT_DIR / "fato_assistencial.csv"


def main() -> None:
    df = pd.read_excel(RAW_FILE, sheet_name="base")
    df.columns = [c.lower() for c in df.columns]
    df["periodo"] = pd.to_datetime(df["periodo"])
    df["ano"] = df["periodo"].dt.year
    df["mes"] = df["periodo"].dt.month
    df["ano_mes"] = df["periodo"].dt.to_period("M").astype(str)
    df["periodo"] = df["periodo"].dt.strftime("%Y-%m-%d")

    for col in ["tipo", "vertical", "cidade", "uf", "regiao", "produto"]:
        df[col] = df[col].astype(str).str.strip().str.upper()

    df = df[~((df["receita"] == 0) & (df["custo"] == 0))].copy()

    cols = [
        "periodo",
        "ano",
        "mes",
        "ano_mes",
        "tipo",
        "vertical",
        "cidade",
        "uf",
        "regiao",
        "produto",
        "vidas",
        "receita",
        "custo",
        "usuarios",
        "procedimentos",
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df[cols].to_csv(OUT_FILE, index=False, encoding="utf-8")
    print(f"CSV gerado: {OUT_FILE}")
    print(f"Linhas: {len(df):,}")


if __name__ == "__main__":
    main()
