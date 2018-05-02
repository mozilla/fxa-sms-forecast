import pandas as pd
import numpy as np
import seasonal
from sys import stderr, argv
from copy import deepcopy
from collections import namedtuple
from scipy.optimize import fmin_l_bfgs_b
from datetime import timedelta

# many functions below taken from the seasonal example script
# https://github.com/welch/seasonal/blob/master/examples/hw.py

HWState = namedtuple('HWState', 't level trend seasons')
HWParams = namedtuple('HWParams', 'alpha beta gamma')

def estimate_state(data):
    """estimate initial state for Holt Winters
    HWState estimates are for t=-1, the step before y[0].
    Parameters
    ----------
    data : ndarray
        observations
    """
    seasons, trended = seasonal.fit_seasons(data)
    if seasons is None:
        seasons = np.zeros(1)
    trend = trended[1] - trended[0]
    level = trended[0] - trend
    return HWState(-1, level, trend, seasons)

def forecast(state, steps=1):
    """return a single or multi-step forecast from the current state
    Parameters
    ----------
    state : HWState
        current model state
    steps : int
        number of steps out to forecast
    """
    season = state.seasons[(state.t + steps) % len(state.seasons)]
    return state.level + state.trend * steps + season

def advance(y, params, state):
    """incorporate the next observation into the state estimate.
    This returns updated state, using Hyndman's error correction form of H-W [1]
    It mutates state's seasonal array.
    Parameters
    ----------
    y : float
        observed value at time state.t + 1
    params : HWParams
        alpha, beta, gamma params for HW
    state : HWState
        current HW state
    Returns
    -------
    state, err : HWState, float
        state: updated state
        one-step forecast error for y
    References
    ----------
    .. [1] https://www.otexts.org/fpp/7/5, Holt-Winters additive method
    """
    seasons = state.seasons
    e = y - forecast(state)
    level = state.level + state.trend + params.alpha * e
    trend = state.trend + params.alpha * params.beta * e
    seasons[(state.t + 1) % len(state.seasons)] += params.gamma * e
    # in a proper implementation, we would enforce seasons being 0-mean.
    return HWState(state.t+1, level, trend, seasons), e

def estimate_params(data, state, alpha0=0.3, beta0=0.1, gamma0=0.1):
    """Estimate Holt Winters parameters from data
    Parameters
    ----------
    data : ndarray
        observations
    state : HWState
        initial state for HW (one step prior to first data value)
    alpha0, beta0, gamma0 : float, float, float
        initial guess for HW parameters
    Returns
    -------
    params : HWParams
    Notes
    -----
    This is a not a demo about estimating Holt Winters parameters, and
    this is not a great way to go about it, because it does not
    produce good out-of-sample error. In this demo, we unrealistically
    train the HW parameters over all the data, not just the training
    prefix used for the initial seasonal state estimate.
    """
    def _forecast_error(x0, state, data):
        """bfgs HW parameter error callback."""
        E = 0
        state = deepcopy(state)
        params = HWParams(*x0)
        for y in data:
            state, e = advance(y, params, state)
            E += e * e
        return E / len(data)

    alpha, beta, gamma = fmin_l_bfgs_b(
        _forecast_error, x0=[alpha0, beta0, gamma0], bounds=[[0, 1]] * 3,
        args=(state, data), approx_grad=True)[0]
    return HWParams(alpha, beta, gamma)


def hw(data, split=None, params=None):
    """fit a HW model and return the 1-step forecast and smoothed series.
    Parameters
    ----------
    data : array of float
        observations
    split : number
        initialize using the leading split*100% of the data (if split <=1.0)
        or N=split points (if split > 1)
    Returns
    -------
    forecast, smoothed : ndarray, ndarray
    """
    if split is None:
        splitidx = len(data)
    elif split > 1.0:
        splitidx = int(split)
    else:
        splitidx = int(split * len(data))
    state = estimate_state(data[:splitidx])
    print("||seasons|| = {:.3f}".format(np.sqrt(np.sum(state.seasons ** 2))))
    if params is None:
        params = estimate_params(data, state)
        print("estimated alpha={:.3f}, beta={:.3f}, gamma={:.3f}".format(*params))
    level = np.empty(len(data))
    fcast = np.empty(len(data))
    for y in data:
        yhat = forecast(state)
        state, _ = advance(y, params, state)
        level[state.t], fcast[state.t] = state.level, yhat
    return fcast, level

def last_state(data, params=None):
    state = estimate_state(data)
    if params is None:
        params = estimate_params(data, state)
    level = np.empty(len(data))
    fcast = np.empty(len(data))
    for y in data:
        state, _ = advance(y, params, state)
    return state

def get_forecast(data, nsteps=24):
    ls = last_state(data)
    preds = np.empty(nsteps)
    for i in range(nsteps):
        preds[i] = forecast(ls,i)
    return(preds)

data_fn = argv[1]
if len(argv) == 3:
    forecast_length = int(argv[2])
else:
    forecast_length = 24


d = pd.read_json(data_fn)
d = d.Datapoints.apply(pd.Series)
d['Timestamp'] = pd.to_datetime(d.Timestamp)
d = d.sort_values('Timestamp')
d = d.drop(['Unit'],axis = 1)
d = d.reset_index()

last_hour = d.Timestamp.iloc[-1]
fc = get_forecast(d.Average, forecast_length)
next_hours = [last_hour + timedelta(hours = i) for i in range(1, forecast_length+1)]
to_print = pd.DataFrame({'timestamp':next_hours, 'prediction':fc},columns=['timestamp','prediction'])
print(to_print.sort_values('timestamp'))
