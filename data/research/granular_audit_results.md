Traceback (most recent call last):
  File "/Users/danielsuarezsucre/TRADING/trading_agent/src/analysis/hyper_granular_audit.py", line 131, in <module>
    hyper_granular_audit()
    ~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/danielsuarezsucre/TRADING/trading_agent/src/analysis/hyper_granular_audit.py", line 63, in hyper_granular_audit
    df = load_all()
  File "/Users/danielsuarezsucre/TRADING/trading_agent/src/analysis/hyper_granular_audit.py", line 58, in load_all
    master = pd.concat([l_axi(), l_ft_a(), l_ft_r(), l_bn(), l_sh()], ignore_index=True)
  File "/Users/danielsuarezsucre/TRADING/trading_agent/.venv/lib/python3.14/site-packages/pandas/core/reshape/concat.py", line 466, in concat
    result = _get_result(
        objs,
    ...<9 lines>...
        axis,
    )
  File "/Users/danielsuarezsucre/TRADING/trading_agent/.venv/lib/python3.14/site-packages/pandas/core/reshape/concat.py", line 653, in _get_result
    indexers[ax] = obj_labels.get_indexer(new_labels)
                   ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/danielsuarezsucre/TRADING/trading_agent/.venv/lib/python3.14/site-packages/pandas/core/indexes/base.py", line 3728, in get_indexer
    raise InvalidIndexError(self._requires_unique_msg)
pandas.errors.InvalidIndexError: Reindexing only valid with uniquely valued Index objects
