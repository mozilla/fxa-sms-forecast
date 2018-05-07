import pandas as pd
import numpy as np
import warnings
import itertools
import statsmodels.api as sm
from sys import stderr, argv

def read_data(fn):
    d = pd.read_json(fn)
    d = d.Datapoints.apply(pd.Series)
    d['Timestamp'] = pd.to_datetime(d.Timestamp)
    d = d.sort_values('Timestamp')
    d = d.drop(['Unit'],axis = 1)
    d = d.reset_index()
    d = d.set_index(d.Timestamp)
    d['y_diff'] = d.Average.diff()
    return(d)

def set_grid(upper_bound=2):
    p = d = q = range(0, upper_bound)
    pdq = list(itertools.product(p, d, q))
    seasonal_pdq = [(x[0], x[1], x[2], 24) for x in list(itertools.product(p, d, q))]
    return pdq, seasonal_pdq

def grid_search(d, pdq, seasonal_pdq):
    warnings.filterwarnings("ignore")
    vals = []
    counter = 0
    for param in pdq:
        for param_seasonal in seasonal_pdq:
            if counter % 10 == 1:
                print(counter)
            try:
                mod = sm.tsa.statespace.SARIMAX(d.y_diff,
                                                order=param,
                                                seasonal_order=param_seasonal,
                                                enforce_stationarity=False,
                                                enforce_invertibility=False)

                results = mod.fit()
                vals.append([param,param_seasonal,results.aic])
            except:
                continue
            counter += 1
    ret = pd.DataFrame(vals,columns=['params','seasonal_params','AIC'])
    return(ret)

def get_forecast(results, forecast_length):
    steps = forecast_length * 24
    pred_uc = results.get_forecast(steps=steps)
    pred_ci = pred_uc.conf_int()
    pred_mean = pred_uc.predicted_mean
    pred_ci['mean_pred'] = pred_mean
    return pred_ci

data_fn = argv[1]

try:
    forecast_length = int(argv[2])
except:
    forecast_length = 1

try:
    use_grid = int(argv[3])
except:
    use_grid = 0

if use_grid != 0:
    pdq, seasonal_pdq = set_grid(upper_bound=use_grid)
    grid = grid_search(d,pdq,seasonal_pdq)
    grid = pd.DataFrame(grid,columns=['params','seasonal_params','AIC'])
    best_params = grid[grid['AIC'] == grid.AIC.min()]
else:
    best_params = pd.DataFrame({'params':[(1,1,2)],'seasonal_params':[(1,1,2,24)]})

d = read_data(data_fn)
last_value = d['Average'][-1:].values[0]
mod = sm.tsa.statespace.SARIMAX(d.y_diff,
                                order=best_params.params.values[0],
                                seasonal_order=best_params.seasonal_params.values[0],
                                enforce_stationarity=False,
                                enforce_invertibility=False)

results = mod.fit()
preds = get_forecast(results, forecast_length)
preds['lower_total'] = preds['lower y_diff'].cumsum() + last_value
preds['upper_total'] = preds['upper y_diff'].cumsum() + last_value
preds['mean_total'] = preds['mean_pred'].cumsum() + last_value
print(preds)
