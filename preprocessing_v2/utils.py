import pandas as pd
import numpy as np
from joblib import Parallel, delayed
from multiprocessing import Pool, cpu_count

def applyParallel(dfGrouped, func):
    retLst = Parallel(n_jobs=cpu_count())(delayed(func)(group) for name, group in dfGrouped)
    return pd.DataFrame(retLst)

def applyParalleldf(df, func):
    n_jobs=cpu_count() - 1
    df_split = np.array_split(df, n_jobs)
    retLst = Parallel(n_jobs)(delayed(func)(chunk) for chunk in df_split)
    return pd.concat(retLst)


