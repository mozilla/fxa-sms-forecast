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

SECONDS_PER_HOUR = 60 * 60

AWS_REGION = os.environ["AWS_REGION"]

def from_env_or_default(variable_name, default_value):
    if variable_name in os.environ:
        return os.environ[variable_name]

    return default_value

AWS_ACCESS_KEY = from_env_or_default("AWS_ACCESS_KEY", None)
AWS_SECRET_KEY = from_env_or_default("AWS_SECRET_KEY", None)

def is_near_month_end(now, forecast_length):
    # Don't forecast unless there's sufficient time remaining in the month
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day >= last_day - forecast_length

def init_client(name):
    return boto3.client(name,
                        region_name=AWS_REGION,
                        aws_access_key_id=AWS_ACCESS_KEY,
                        aws_secret_access_key=AWS_SECRET_KEY)

def get_data(now):
    start_of_hour = now.replace(minute=0, second=0, microsecond=0)
    start_of_month = start_of_hour.replace(day=1, hour=0).isoformat()
    start_of_hour = start_of_hour.isoformat()
    print("Fetching SMSMonthToDateSpentUSD:", start_of_month, "-", start_of_hour)
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
    #print(data)
    d = pd.DataFrame(data['Datapoints'])
    d['Timestamp'] = pd.to_datetime(d.Timestamp)
    d = d.sort_values('Timestamp')
    d = d.drop(['Unit'],axis = 1)
    d = d.reset_index()
    d = d.set_index(d.Timestamp)
    d['y_diff'] = d.Maximum.diff()
    print(d.head())
    return d

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

def get_forecast(results, forecast_length):
    steps = forecast_length * 24
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

def send_email(from_address, env, region, forecast_length, mean, current, recommended, spend):
    ses = init_client("ses")
    ses.send_email(
        Source=from_address,
        Destination={"ToAddresses": ["fxa-core@mozilla.com"]},
        Message={
            "Subject": {"Data": "SMS budget forecast"},
            "Body": {
                "Text": {
                  "Data": """The FxA SMS spend in {env}/{region} is expected to exceed budget within {forecast_length} days!

Forecasted total spend in 7 days: {mean}

Current Spend: {spend}
Current budget: {current}
Crude budget recommendation: {recommended}

Cheerio!

-- 
This email was sent by a bot. Nobody will see your reply.
https://github.com/mozilla/fxa-sms-forecast
""".format(env=env, region=region, forecast_length=forecast_length, mean=mean, current=current, recommended=recommended, spend=spend)
                }
            }
        }
    )

def main():
    now = datetime.utcnow()
    forecast_length = int(from_env_or_default("FORECAST_LENGTH", 7))

    if now.day < forecast_length or is_near_month_end(now, forecast_length):
        # Exit gracefully if it's near the start or end of the month
        return

    d = prepare_data(get_data(now))

    use_grid = int(from_env_or_default("USE_GRID", 0))

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

    try:
        results = mod.fit(disp=0)
    except:
        # We probably don't have enough datapoints for the model,
        # abort for now and then try again next time
        print("mod.fit failed, aborting")
        return

    try:
        _ = best_params.aic
    except:
        best_params['AIC'] = results.aic

    print("model parameters:\n{}".format(tabulate(best_params, headers='keys', tablefmt='psql')))

    preds = get_forecast(results, forecast_length)
    preds['lower_total'] = preds['lower y_diff'].cumsum() + last_value
    preds['upper_total'] = preds['upper y_diff'].cumsum() + last_value
    preds['mean_total'] = preds['mean_pred'].cumsum() + last_value

    lower_total = preds['lower_total'][-1]
    upper_total = preds['upper_total'][-1]
    mean_total = preds['mean_total'][-1]
    budget = get_budget()
    print(upper_total, lower_total, mean_total, budget)

    if mean_total > budget:
        new_budget = mean_total + 1000 - (mean_total % 1000)
        #raise_ticket(new_budget)
        send_email(from_env_or_default("FROM_ADDRESS", "fxa-sms@latest.dev.lcip.org"),
                   from_env_or_default("ENV", "dev"),
                   AWS_REGION,
                   forecast_length,
                   mean_total,
                   budget,
                   new_budget,
                   last_value)

if __name__ == "__main__":
    main()
