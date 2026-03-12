adx_val = 22.3
adx_levels = [15, 20, 25, 28, 32]
rr_targets = [1.5, 2.0, 2.5, 3.0]
directions = [1, -1]
c = 0
for cfg_adx in adx_levels:
    if adx_val < cfg_adx: continue
    for r in rr_targets:
        for d in directions:
            c += 1
print(c)
