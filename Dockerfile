FROM python:3
RUN mkdir /app
COPY forecast_sms.py /app/
WORKDIR /app
RUN pip install scipy numpy
RUN pip install pandas statsmodels tqdm tabulate boto3
CMD [ "python", "forecast_sms.py" ]
