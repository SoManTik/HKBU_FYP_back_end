from flask import Flask, request, jsonify, Response
# from config import Config
from flask_cors import CORS
import utils.db as db
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
from bson.objectid import ObjectId
import json
import os
from PyPDF2 import PdfFileReader
# import numpy as np
import requests
# from bs4 import BeautifulSoup
import joblib
from utils.T5_generate_summary import T5_model_generate_summary
from utils.BART_generate_summary import Bart_model_generate_summary
from utils.Fake_news_detection import detect_fake_news
from utils.news_type_detection_n_recommendation.news_recommendation_ import  custom_tokenizer
from utils.news_type_detection_n_recommendation.news_recommendation_ import  get_recommendations
app = Flask(__name__)



CORS(app, resources={r'/*': {'origins': '*'}})
app.config['JWT_SECRET_KEY'] = 'secret'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['JWT_TOKEN_LOCATION'] = ['headers']

app.config.from_object(__name__)
jwt = JWTManager(app)

@app.route("/api/login",methods=['POST'])
def login():
    collection= db.connectCollection("user")
    credentials = request.get_json()
    user = collection.find_one(credentials)
    if(user==None):
        return jsonify({"message": "Authentication failed","user":False}),401
    _id = ObjectId(str(user["_id"]))
    data = {"_id": _id}
    data = json.dumps(data, default=str)
    access_token = create_access_token(identity=data)
    return jsonify(user=True,access_token=access_token),200

@app.route("/api/T5_generate_summary",methods=['GET', 'POST'])
def T5_generate_summary():
    data = request.get_json()
    selected_text = data.get('selectedText', '')
    temperature = data.get('temperature')

    summary = T5_model_generate_summary(selected_text, temperature= temperature)
    probability, detection = detect_fake_news(unseen_news_text=summary)
    news_recommendation_url, news_recommendation_img, news_recommendation_title = get_recommendations(summary)
    
    response = requests.get(news_recommendation_img)

    news_recommendation_img = response.url
    print(news_recommendation_img)
    summary = json.dumps(summary, default=str)
    return jsonify(summary=summary, probability=int(probability*100),
                  news_recommendation_url = news_recommendation_url,
                    news_recommendation_img = news_recommendation_img,
                    news_recommendation_title = news_recommendation_title,
                    detection=detection), 200

@app.route("/api/BART_generate_summary",methods=['GET', 'POST'])
def Bart_generate_summary():
    data = request.get_json()
    selected_text = data.get('selectedText', '')
    temperature = data.get('temperature')

    summary = Bart_model_generate_summary(selected_text, temperature= temperature)
    probability, detection = detect_fake_news(unseen_news_text=summary)
    news_recommendation_url, news_recommendation_img, news_recommendation_title = get_recommendations( summary)
    # 
    response = requests.get(news_recommendation_img)

    #
    news_recommendation_img = response.url

    summary = json.dumps(summary, default=str)
    return jsonify(summary=summary, probability=int(probability*100),
                  news_recommendation_url = news_recommendation_url,
                    news_recommendation_img = news_recommendation_img,
                    news_recommendation_title = news_recommendation_title,
                    detection=detection), 200

@app.route('/get-url', methods=['POST'])
def get_url():
    data = request.json
    url = data.get('url')
    return jsonify({'url': url})

@app.route('/api/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:

        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return jsonify({'content': response.text})
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/upload_file", methods=["POST"])
def upload_file():

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400


    file_name = file.filename
    file_extension = os.path.splitext(file_name)[1]


    if file_extension == ".pdf":
        # Extract text from PDF file
        pdf_file = PdfFileReader(file)
        text = ""
        for page in range(pdf_file.numPages):
            text += pdf_file.getPage(page).extractText()
        return jsonify(text= text), 200
    elif file_extension == ".txt":
        # Read text from txt file
        text = file.read().decode("utf-8")
        return jsonify(text= text), 200
    else:
        # Return error message for invalid file type
        return jsonify({"error": "Invalid file type"}), 400



if __name__ == '__main__':

    
    app.run(debug=True,host="0.0.0.0",port=3000)
