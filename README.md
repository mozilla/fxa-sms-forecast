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
`python forecast_sms.py [q_upper_limit]`

e.g.

`python forecast_sms.py 0`

An optional parameter controls whether a search is done for better model parameters. The larger the number the more it will search, with numbers > 10 taking a long time. If the this parameter is 0 or omitted, a pre-defined set of parameters that I've found to to work decently will be used instead.

I suggest trying without any parameter first, then if need be setting the last parameter to 5 and see if the AIC improves (lower the better).

## Data Output Format (Predictions)

Currently, the script prints to the console 6 columns of data in the following order (each row is labeled with the timestamp for the hour that's being predicted):

1. `spent_in_hour_lower_est` the lower bound on the estimate for how much money is predicted to be spent in that hour
2. `spent_in_hour_upper_est` the upper bound on the estimate for how much money is predicted to be spent in that hour
3. `spent_in_hour_mean_est` the mean (i.e., best guess) estimate for how much money is predicted to be spent in that hour
4. `lower_cum_total` the lower bound on the estimate for the total (cumulative) amount spent up to and including that hour
5. `upper_cum_total` the upper bound on the estimate for the total (cumulative) amount spent up to and including that hour
6. `mean_cum_total` the mean (i.e. best guess) estimate for the total (cumulative) amount spent up to and including that hour

The upper and lower bounds should be considered to be 95% confidence intervals, i.e. "we are 95% confident that the actual value will be somewhere between the lower and upper bound".

## Deploying to AWS Lambda

It turns out this is hard and annoying.
Firstly,
the zip file including all the dependencies
is sufficiently large
that it can only be uploaded via S3.
Secondly,
the `pandas` dependency
must be compiled on AWS Linux
in order for it to be used in Lambda.
Yay for serverless architecture!

Because I'm not competent with Python,
I'm recording the steps I took
to build the deployment package.
They're cobbled together from the following sources:

* https://docs.aws.amazon.com/lambda/latest/dg/with-s3-example-deployment-pkg.html#with-s3-example-deployment-pkg-python
* https://stackoverflow.com/questions/43877692/pandas-in-aws-lambda-gives-numpy-error
* https://stackoverflow.com/questions/36054976/pandas-aws-lambda

```
sudo yum install -y gcc zlib zlib-devel openssl openssl-devel
wget https://www.python.org/ftp/python/3.6.6/Python-3.6.6.tgz
tar -xvf Python-3.6.6.tgz
cd Python-3.6.6
./configure
make
sudo make install
/usr/local/bin/virtualenv ~/forecast_sms
source ~/forecast_sms/bin/activate
pip install boto3 numpy pandas scipy statsmodels tabulate tqdm
cd ~/forecast_sms/lib/python3.6/site-packages
zip -r9 ~/fxa-sms-forecast.zip .
cd ../../..
zip -g ~/fxa-sms-forecast.zip forecast_sms.py
aws s3 cp ~/fxa-sms-forecast.zip s3://fxa-forecast-sms/
```
