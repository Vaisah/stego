FROM python:3.10.11-slim-bullseye
WORKDIR /app
COPY . .
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=development
RUN pip install -r requirements.txt
EXPOSE 5000
ENV MONGODB_USERNAME=xander
ENV MONGODB_PASSWORD=xander21
CMD ["flask", "run"]
