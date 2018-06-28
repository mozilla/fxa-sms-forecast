import boto3
import calendar
import pandas as pd
import numpy as np
import os
import warnings
import itertools
import statsmodels.api as sm
from datetime import datetime
from tqdm import tqdm
from tabulate import tabulate
from sys import argv, exit, stderr

SECONDS_PER_HOUR = 60 * 60
FORECAST_LENGTH = 7

AWS_REGION = os.environ["AWS_REGION"]
AWS_ACCESS_KEY = os.environ["AWS_ACCESS_KEY"]
AWS_SECRET_KEY = os.environ["AWS_SECRET_KEY"]

NOW = datetime.utcnow()

def is_near_month_end():
    # Don't forecast unless there's sufficient time remaining in the month
    last_day = calendar.monthrange(NOW.year, NOW.month)[1]
    return NOW.day >= last_day - FORECAST_LENGTH

def init_client(name):
    return boto3.client(name,
                        region_name=AWS_REGION,
                        aws_access_key_id=AWS_ACCESS_KEY,
                        aws_secret_access_key=AWS_SECRET_KEY)

def get_data():
    start_of_hour = NOW.replace(minute=0, second=0, microsecond=0)
    start_of_month = start_of_hour.replace(day=1, hour=0).isoformat()
    start_of_hour = start_of_hour.isoformat()
    print "Fetching SMSMonthToDateSpentUSD:", start_of_month, "-", start_of_hour
    cloudwatch = init_client("cloudwatch")
    return cloudwatch.get_metric_statistics(
        Namespace="AWS/SNS",
        MetricName="SMSMonthToDateSpentUSD",
        StartTime=start_of_month,
        EndTime=start_of_hour,
        Period=SECONDS_PER_HOUR,
        Statistics=["Maximum"]
    )

def prepare_data(data):
    print data
    # TODO: This may be (probably is) wrong, I need to test it against real datapoints
    d = pd.Series(data['Datapoints'])
    #d = pd.read_json(fn)
    #d = d.Datapoints.apply(pd.Series)
    d['Timestamp'] = pd.to_datetime(d.Timestamp)
    d = d.sort_values('Timestamp')
    d = d.drop(['Unit'],axis = 1)
    d = d.reset_index()
    d = d.set_index(d.Timestamp)
    d['y_diff'] = d.Maximum.diff()
    return(d)

def set_grid(pu=(1,2),du=(1,2),qu=(0,2)):
    p = range(*pu)
    d = range(*du)
    q = range(*qu)
    pdq = list(itertools.product(p, d, q))
    seasonal_pdq = [(x[0], x[1], x[2], 24) for x in list(itertools.product(p, d, q))]
    return pdq, seasonal_pdq

def grid_search(d, pdq, seasonal_pdq):
    warnings.filterwarnings("ignore")
    vals = []
    for param in tqdm(pdq):
        for param_seasonal in seasonal_pdq:
            try:
                mod = sm.tsa.statespace.SARIMAX(d.y_diff,
                                                order=param,
                                                seasonal_order=param_seasonal,
                                                enforce_stationarity=False,
                                                enforce_invertibility=False)

                results = mod.fit(disp=0)
                vals.append([param,param_seasonal,results.aic])
            except:
                continue
    ret = pd.DataFrame(vals,columns=['params','seasonal_params','AIC'])
    return(ret)

def get_forecast(results):
    steps = FORECAST_LENGTH * 24
    pred_uc = results.get_forecast(steps=steps)
    pred_ci = pred_uc.conf_int()
    pred_mean = pred_uc.predicted_mean
    pred_ci['mean_pred'] = pred_mean
    return pred_ci

def get_budget():
    sns = init_client("sns")
    result = sns.get_sms_attributes(attributes=["MonthlySpendLimit"])
    return float(result["attributes"]["MonthlySpendLimit"])

def raise_ticket(new_budget):
    support = init_client("support")
    support.create_case(
        language="en",
        issueType="technical",
        serviceCode="TODO: DescribeServices",
        categoryCode="TODO: DescribeServices",
        severityCode="TODO: DescribeSeverityLevels",
        ccEmailAddresses="fxa-core@mozilla.com",
        subject="TEST CASE, please ignore",
        communicationBody="""Limit increase request 1 Service: SNS Text Messaging
Resource Type: General Limits
Limit name: Account Spend Threshold Increase for SMS
New limit value: {new_budget}
------------
Use case description: Based on current usage, it's forecast that we'll exceed our threshold for this month. Please see case #4859506511 for implementation details of how we're using SMS. Nothing has changed since then except more users are signing in to Firefox Accounts and asking to install Firefox on a mobile device.
Link to site or app which will be sending SMS: https://accounts.firefox.com
Type of messages: Promotional
Targeted Countries: AT, AU, BE, CA, DE, DK, ES, FR, GB, IT, LU, NL, PT, RO, US
""".format(new_budget=new_budget))

if NOW.day < 3 or is_near_month_end():
    # Exit gracefully if it's near the start or end of the month
    exit(0)

try:
    use_grid = int(argv[1])
except:
    use_grid = 0

d = prepare_data(get_data())

if use_grid != 0:
    pdq, seasonal_pdq = set_grid(qu=(0,use_grid))
    grid = grid_search(d,pdq,seasonal_pdq)
    grid = pd.DataFrame(grid,columns=['params','seasonal_params','AIC'])
    best_params = grid[grid['AIC'] == grid.AIC.min()]
else:
    best_params = pd.DataFrame({'params':[(1,1,2)],'seasonal_params':[(1,1,2,24)]})

last_value = d['Maximum'][-1:].values[0]
mod = sm.tsa.statespace.SARIMAX(d.y_diff,
                                order=best_params.params.values[0],
                                seasonal_order=best_params.seasonal_params.values[0],
                                enforce_stationarity=False,
                                enforce_invertibility=False)

results = mod.fit(disp=0)
try:
    _ = best_params.aic
except:
    best_params['AIC'] = results.aic

print("Using these model parameters:\n {}".format(tabulate(best_params,headers='keys',tablefmt='psql')))

preds = get_forecast(results)
preds['lower_total'] = preds['lower y_diff'].cumsum() + last_value
preds['upper_total'] = preds['upper y_diff'].cumsum() + last_value
preds['mean_total'] = preds['mean_pred'].cumsum() + last_value
preds.columns = ['spent_in_hour_lower_est','spent_in_hour_upper_est','spent_in_hour_mean_est','lower_cum_total','upper_cum_total','mean_cum_total']
print(preds)

budget = get_budget()

if preds['upper_total'] > budget:
    new_budget = preds['upper_total'] + 1000 - preds['upper_total'] % 1000
    raise_ticket(new_budget)
