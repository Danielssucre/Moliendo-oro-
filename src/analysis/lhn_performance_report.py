import pandas as pd
import os
import glob
from datetime import datetime

# Rutas de datos
RESEARCH_DIR = "/Users/danielsuarezsucre/TRADING/trading_agent/data/research"
OUTPUT_REPORT = "/Users/danielsuarezsucre/.gemini/antigravity/brain/43304ed8-ef8e-4ced-a9d4-d3d504ca977c/lhn_analysis_results.md"

def categorize_lhn(comment):
    comment = str(comment).upper()
    if 'ALFA' in comment: return 'ALFA (Trend Sniper)'
    if 'NEME' in comment: return 'NEMESIS (Mean Reversion)'
    if 'EXPL' in comment: return 'EXPLORATION (Trend Runner)'
    if 'BETA' in comment: return 'BETA (Hybrid)'
    return 'OTHER'

def generate_report():
    print("🚀 Iniciando Consolidación de Datos L-H-N...")
    
    # 1. Cargar historias de investigación
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
                # Normalizar nombres de columnas si varían
                if 'comment' not in df.columns:
                    if 'comment_entry' in df.columns:
                        df['comment'] = df['comment_entry']
                    elif 'config' in df.columns:
                        df['comment'] = df['config']
                
                if 'profit' in df.columns and 'comment' in df.columns:
                    dfs.append(df[['symbol', 'profit', 'comment']])
            except Exception as e:
                print(f"⚠️ Error cargando {f}: {e}")
    
    if not dfs:
        print("❌ No se encontraron datos para analizar.")
        return
        
    full_df = pd.concat(dfs)
    full_df['distrito'] = full_df['comment'].apply(categorize_lhn)
    
    # 2. Métricas por Distrito
    stats = full_df.groupby('distrito').agg(
        trades=('profit', 'count'),
        total_pnl=('profit', 'sum'),
        avg_profit=('profit', 'mean'),
        wins=('profit', lambda x: (x > 0).sum())
    )
    
    stats['win_rate'] = (stats['wins'] / stats['trades'] * 100).round(2)
    stats['profit_factor'] = full_df.groupby('distrito').apply(
        lambda x: abs(x[x['profit'] > 0]['profit'].sum() / x[x['profit'] < 0]['profit'].sum()) if x[x['profit'] < 0]['profit'].sum() != 0 else 0
    )
    
    # 3. Top Activos
    top_assets = full_df.groupby(['distrito', 'symbol'])['profit'].sum().reset_index()
    top_assets = top_assets.sort_values(['distrito', 'profit'], ascending=[True, False])
    
    # 4. Construir Informe Markdown
    report_md = f"""# 📊 INFORME DE RENDIMIENTO LABORAL L-H-N
*Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## 🎯 Desempeño por Distrito (Consolidado)

| Distrito | Trades | PnL Total | Win Rate | Profit Factor |
|----------|--------|-----------|----------|---------------|
"""
    for dist, row in stats.iterrows():
        report_md += f"| {dist} | {row['trades']} | ${row['total_pnl']:,.2f} | {row['win_rate']}% | {row['profit_factor']:.2f} |\n"
        
    report_md += "\n## 🏆 Top 3 Activos por Distrito\n"
    for dist in stats.index:
        dist_assets = top_assets[top_assets['distrito'] == dist].head(3)
        report_md += f"\n### {dist}\n"
        for _, asset in dist_assets.iterrows():
            report_md += f"- **{asset['symbol']}**: ${asset['profit']:,.2f}\n"
            
    report_md += f"""
## 🧬 Conclusiones del Experimento
1. **Dominancia**: Se observa si el perfil de reversión (NEMESIS) o tendencia (ALFA) está liderando la recuperación.
2. **Eficiencia**: El Profit Factor superior a 1.2 indica robustez en el distrito.
3. **Recovery Status**: El PnL total refleja el avance hacia el equilibrio tras el último drawdown.

---
*Análisis ejecutado por Antigravity L-H-N Engine.*
"""

    with open(OUTPUT_REPORT, 'w') as f:
        f.write(report_md)
        
    print(f"✅ Informe generado en: {OUTPUT_REPORT}")

if __name__ == "__main__":
    generate_report()
