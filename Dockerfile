FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .[prod]
ENV KF_HOST=0.0.0.0 KF_PORT=5050 KF_AUTO_BOOTSTRAP=0
EXPOSE 5050
CMD ["gunicorn","-c","gunicorn.conf.py","admin.app:app"]
