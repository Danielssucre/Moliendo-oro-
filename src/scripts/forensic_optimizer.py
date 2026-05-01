import json, datetime, re, os

def get_day(ts):
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

def run_simulation(report_path):
    with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
        full_content = f.read()
        
        # Extracción robusta del JSON
        start_marker = "window.__report ="
        pos = full_content.find(start_marker)
        if pos == -1:
            print("Error: No se encontró window.__report")
            return
        
        json_start = full_content.find("{", pos)
        # El JSON termina justo antes del punto y coma que cierra el script
        json_end = full_content.find(";</script>", json_start)
        if json_end == -1:
            json_end = full_content.find("</script>", json_start)
            
        data_str = full_content[json_start:json_end].strip()
        if data_str.endswith(";"): data_str = data_str[:-1]
    
    try:
        data = json.loads(data_str)
    except Exception as e:
        # Fallback regex radical
        match = re.search(r'(\{.*\})', data_str)
        if match:
            data = json.loads(match.group(1))
        else:
            print(f"Error parseando JSON: {e}")
            return
            
    target_day = '2026-04-17'
    
    # --- CONFIGURACIÓN OPTIMIZADA o2 ---
    MFE_LOCK_THRESHOLD = 50.0 
    MFE_LOCK_TARGET = 15.0    # Asegurar al menos $15 si tocamos $50
    MFE_TRAILING_RATIO = 0.6  # Si MFE > $200, asegurar el 60% (Configuración Agresiva o2)
    MAX_MAE_ALLOWED = 40.0    # Hard Stop ceñido a $40 (0.4% risk)
    
    # Data containers
    original_results = { 'net': 0, 'wins': 0, 'losses': 0, 'gp': 0, 'gl': 0 }
    optimized_results = { 'net': 0, 'wins': 0, 'losses': 0, 'gp': 0, 'gl': 0 }
    
    risks = data.get('risksMfeMaeMoney', {}).get('chart', [[]])[0]
    pd = data.get('profitDeals', {})
    
    for r in risks:
        day = get_day(r['x'])
        if day != target_day: continue
        
        # Contar trades en el bloque
        num_wins = 0
        for item in pd.get('profit', []):
            if item['x'] == r['x']: num_wins = sum(item['y'])
            
        num_losses = 0
        for item in pd.get('loss', []):
            if item['x'] == r['x']: num_losses = sum(item['y'])
        
        total_in_block = num_wins + num_losses
        if total_in_block == 0: continue
        
        avg_profit_orig = r['y'][0]
        avg_mfe_orig = r['y'][1]
        avg_loss_orig = r['y'][2]
        avg_mae_orig = abs(r['y'][3])
        
        # 1. Ganadoras
        for _ in range(num_wins):
            original_results['net'] += avg_profit_orig
            original_results['wins'] += 1
            original_results['gp'] += avg_profit_orig
            
            opt_pnl = avg_profit_orig
            if avg_mfe_orig > 200:
                opt_pnl = max(opt_pnl, avg_mfe_orig * MFE_TRAILING_RATIO)
            elif avg_mfe_orig > MFE_LOCK_THRESHOLD:
                opt_pnl = max(opt_pnl, MFE_LOCK_TARGET)
            
            optimized_results['net'] += opt_pnl
            optimized_results['wins'] += 1
            optimized_results['gp'] += opt_pnl

        # 2. Perdedoras
        for _ in range(num_losses):
            original_results['net'] += avg_loss_orig
            original_results['losses'] += 1
            original_results['gl'] += avg_loss_orig
            
            # Impacto de Hard Stop o2
            opt_loss = max(avg_loss_orig, -MAX_MAE_ALLOWED)
            
            optimized_results['net'] += opt_loss
            optimized_results['losses'] += 1
            optimized_results['gl'] += opt_loss

    # --- EXCLUSIÓN DE XAGUSD (Simulado) ---
    # Según auditoría, XAGUSD perdió -$129.06 el 17 de abril.
    # Eliminamos esa pérdida del cálculo optimizado.
    optimized_results['net'] += 129.06 # Reintegramos la pérdida por no operarlo
    optimized_results['losses'] -= 1
    optimized_results['gl'] += 129.06

    print("\n" + "="*50)
    print("📈 SIMULACIÓN HIVE o2: RESULTADO OPTIMIZADO (17 ABRIL)")
    print("="*50)
    print(f"{'Métrica':<20} | {'Actual (Audit)':<12} | {'Optimizado (o2)'}")
    print("-" * 50)
    print(f"{'Net Daily':<20} | ${original_results['net']:>11.2f} | ${optimized_results['net']:>11.2f}")
    print(f"{'Win Rate':<20} | {(original_results['wins']/(original_results['wins']+original_results['losses'])*100):.1f}%{'':<6} | {(optimized_results['wins']/(optimized_results['wins']+optimized_results['losses'])*100):.1f}%")
    print(f"{'Avg Win':<20} | ${original_results['gp']/original_results['wins']:.2f}{'':<6} | ${optimized_results['gp']/optimized_results['wins']:.2f}")
    print(f"{'Avg Loss':<20} | ${abs(original_results['gl']/original_results['losses']):.2f}{'':<6} | ${abs(optimized_results['gl']/optimized_results['losses']):.2f}")
    print("-" * 50)
    print(f"💰 MEJORA TOTAL: +${optimized_results['net'] - original_results['net']:.2f}")
    print(f"📉 REDUCCIÓN DE RIESGO: Stop Loss limitado a $40 (vs $129 real)")
    print("="*50)

if __name__ == '__main__':
    run_simulation('/Users/danielsuarezsucre/Desktop/Trade report-1513000248 2026-04-18 21-09.html')
