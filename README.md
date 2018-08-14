# fxa-sms-forecast

[![CI](https://circleci.com/gh/mozilla/fxa-sms-forecast.svg?style=svg)](https://circleci.com/gh/mozilla/fxa-sms-forecast)

Forecasts SMS spending for Firefox Accounts.
If spend is predicted to exceed budget
within 7 days,
email is sent to `fxa-core@mozilla.com`.

## Dependencies

* Python 3
* `numpy`
* `scipy`
* `pandas`
* `statsmodels`
* `tqdm`
* `tabulate`
* `boto3`

## Usage

```
python forecast_sms.py
```

## Environment variables

* `AWS_REGION`
* `AWS_ACCESS_KEY`
* `AWS_SECRET_KEY`
* `ENV`
  (optional):
  The environment name
  to be included in notification emails.
  Defaults to `dev`.
* `FORECAST_LENGTH`
  (optional):
  The number of days ahead
  to project the forecast.
  Defaults to `7`.
* `FROM_ADDRESS`
  (optional):
  The from address for email notifications.
  Defaults to `fxa-sms@latest.dev.lcip.org`.
* `USE_GRID`
  (optional):
  Some kind of statistical magic number.
  Defaults to `0`.

## Docker

Container is built [in CircleCI](https://circleci.com/gh/mozilla/fxa-sms-forecast)
and uploaded to DockerHub [here](https://hub.docker.com/r/mozilla/fxa-sms-forecast/).
