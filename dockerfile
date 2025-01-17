FROM python:3.10

WORKDIR /app
COPY requirements.txt requirements.txt
RUN ls
RUN apt-get update 
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN pip uninstall -y bson
RUN pip uninstall -y pymongo
RUN pip install  pymongo
COPY . .
EXPOSE 3000
CMD ["python3", "main.py"]