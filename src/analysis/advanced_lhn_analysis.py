import pandas as pd
import os
import json

RESEARCH_DIR = "/Users/danielsuarezsucre/TRADING/trading_agent/data/research"

def analyze_advanced_variants():
    csv_files = [
        os.path.join(RESEARCH_DIR, "recent_ftmo_history.csv"),
        os.path.join(RESEARCH_DIR, "analyzed_ftmo_history.csv"),
        os.path.join(RESEARCH_DIR, "recovered_lhn_burned_account.csv")
    ]
    
    dfs = []
    for f in csv_files:
        if os.path.exists(f):
            try:
                df = pd.read_csv(f)
                # Column normalization
                if 'comment' not in df.columns:
                    if 'comment_entry' in df.columns: df['comment'] = df['comment_entry']
                    elif 'config' in df.columns: df['comment'] = df['config']
                
                # Check for volume column
                if 'volume' not in df.columns and 'volume' not in df.columns: # Sometimes it's missing in some files
                    pass 
                
                cols = [c for c in ['symbol', 'profit', 'comment', 'volume'] if c in df.columns]
                dfs.append(df[cols])
            except Exception as e:
                print(f"Error loading {f}: {e}")

    full_df = pd.concat(dfs, ignore_index=True)
    full_df['comment'] = full_df['comment'].fillna('').astype(str).str.upper()

    print("\n--- [ANÁLISIS DE VARIANTES ESPECÍFICAS] ---")
    
    # 1. Búsqueda de Keywords
    keywords = ['POLIMATA', 'CAMALEON', 'ALFA_NEME', 'BETA']
    for kw in keywords:
        mask = full_df['comment'].str.contains(kw)
        subset = full_df[mask]
        if not subset.empty:
            print(f"\n🔹 {kw}:")
            print(f"   Trades: {len(subset)}")
            print(f"   PnL: ${subset['profit'].sum():.2g}")
            if 'volume' in subset.columns:
                print(f"   Volumen Promedio: {subset['volume'].mean():.2f}")
                print(f"   Volumen Máximo: {subset['volume'].max():.2f}")
        else:
            print(f"\n🔹 {kw}: No se encontraron registros con este nombre exacto en los comentarios.")

    # 2. Análisis de Lotaje (Alto Impacto)
    if 'volume' in full_df.columns:
        print("\n--- [ANÁLISIS DE ALTO LOTAJE (Vínculo Lote-Performance)] ---")
        q90 = full_df['volume'].quantile(0.90)
        high_lotage = full_df[full_df['volume'] >= q90]
        print(f"Umbral 90% lotaje: {q90:.2f} lotes")
        print(f"Trades alto lotaje: {len(high_lotage)}")
        print(f"PnL alto lotaje: ${high_lotage['profit'].sum():.2g}")
        
        # Estrategias en alto lotaje
        print("\nTop Estrategias en Alto Lotaje:")
        print(high_lotage.groupby('comment')['profit'].sum().sort_values(ascending=False).head(5))

    # 3. Especial: ALFA NEMESIS (Híbrido)
    # Buscamos combinaciones de ALFA y NEME en el mismo comentario o lógica
    alfa_neme_mask = (full_df['comment'].str.contains('ALFA')) & (full_df['comment'].str.contains('NEME'))
    alfa_neme = full_df[alfa_neme_mask]
    if not alfa_neme.empty:
        print(f"\n🔸 ALFA_NEMESIS (Combo):")
        print(f"   Trades: {len(alfa_neme)}")
        print(f"   PnL: ${alfa_neme['profit'].sum():.2g}")

if __name__ == "__main__":
    analyze_advanced_variants()
