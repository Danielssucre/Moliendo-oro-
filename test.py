import pandas as pd
row = pd.Series({'adx': 22.3})
adx_val = row['adx']
adx_levels = [15, 20, 25, 28, 32]
rr_targets = [1.5, 2.0, 2.5, 3.0]
directions = [1, -1]

exec_count = 0
for cfg_adx in adx_levels:
    if adx_val < cfg_adx: 
        print(f"Skipping {cfg_adx} because {adx_val} < {cfg_adx}")
        continue
    for cfg_rr in rr_targets:
        for cfg_dir in directions:
            exec_count += 1
            
print(f"exec_count: {exec_count}")
