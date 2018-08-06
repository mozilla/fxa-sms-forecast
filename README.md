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

## Docker

Container is built [in CircleCI](https://circleci.com/gh/mozilla/fxa-sms-forecast)
and uploaded to DockerHub [here](https://hub.docker.com/r/philbooth/fxa-sms-forecast/).

**TODO:
@jbuck to update the DockerHub link
when he's changed the build
to upload to the mozilla DockerHub org.**
