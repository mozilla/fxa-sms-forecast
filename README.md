# forecast_sms

Used to (potentially) forecast sms spend for FxA.

## Dependencies (as of right now)
* python2.7 or 3 (tried both seems to work)
* These python libs (`pip install`):
  * boto3
  * pandas
  * numpy
  * statsmodels
  * for console print-formatting only: tqdm, tabulate

## Usage Example
Definitely liable to change, but as of now:
`python forecast_sms.py [days_out_to_predict] [q_upper_limit]`

e.g.

`python forecast_sms.py 7 0`

where `7` is how  many **days** after the last hour in your data to predict out. Predictions that are generated are hour by hour. Obviously predictions will be worse the further out you try to predict. If you don't include the hours it will spit out 24 by default.

The last optional parameter controls whether a search is done for better model parameters. The larger the number the more it will search, with numbers > 10 taking a long time. If the this parameter is 0 or omitted, a pre-defined set of parameters that I've found to to work decently will be used instead.

I suggest trying the default parameters first, then if need be setting the last parameter to 5 and see if the AIC improves (lower the better).

## Data Output Format (Predictions)

Currently, the script prints to the console 6 columns of data in the following order (each row is labeled with the timestamp for the hour that's being predicted):

1. `spent_in_hour_lower_est` the lower bound on the estimate for how much money is predicted to be spent in that hour
2. `spent_in_hour_upper_est` the upper bound on the estimate for how much money is predicted to be spent in that hour
3. `spent_in_hour_mean_est` the mean (i.e., best guess) estimate for how much money is predicted to be spent in that hour
4. `lower_cum_total` the lower bound on the estimate for the total (cumulative) amount spent up to and including that hour
5. `upper_cum_total` the upper bound on the estimate for the total (cumulative) amount spent up to and including that hour
6. `mean_cum_total` the mean (i.e. best guess) estimate for the total (cumulative) amount spent up to and including that hour

The upper and lower bounds should be considered to be 95% confidence intervals, i.e. "we are 95% confident that the actual value will be somewhere between the lower and upper bound".
