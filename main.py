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
import requests
from utils.T5_generate_summary import T5_model_generate_summary
from utils.BART_generate_summary import Bart_model_generate_summary
from utils.Fake_news_detection import detect_fake_news
from utils.news_type_detection_n_recommendation.news_recommendation_ import  get_recommendations, custom_tokenizer
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
    user_type = user["user_type"]
    data = {"_id": _id, "user_type": user_type}
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
    top10_relevant_news = get_recommendations(summary)
    

    summary = json.dumps(summary, default=str)
    top10_relevant_news = json.dumps(top10_relevant_news, default=str)

    return jsonify(summary=summary, probability=int(probability*100),
                 
                    top10_relevant_news = top10_relevant_news,
            
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
    

@app.route("/api/find_user_email", methods=["GET","POST"])
def find_user_email():
    data = request.get_json()
    user_account_type = data['selected_user_type']
    collection = db.connectCollection("user")

    if  data['selected_user_type'] == "deletion":
        results = list(collection.find({}))
        results = json.dumps(results,default=str)
        print(" results",results)
        return jsonify({'users_data':results}), 200

 
    
    results = list(collection.find({"user_type": user_account_type}))
 

    emails = [result["email"] for result in results]
    emails = json.dumps(emails,default=str)
    results = json.dumps(results,default=str)
  

    if results:
        return jsonify({"emails": emails, 'users_data':results}), 200
    else:
        return jsonify({"message": "User not found"}), 400




@app.route("/api/accout_creation", methods=["POST"])
def accout_creation():
    data = request.get_json()
    if data is None:
        return jsonify({"message": "No data provided"}), 400
    data = data['account_info']
    collection = db.connectCollection("user")

    result = collection.find_one({"email": data['email']})
    if result:
        return jsonify({"message": "Email already exists"}), 400

    result = collection.insert_one({
        "email": data['email'],
        "pwd": data['pwd'],
        "user_type": data['selected_user_type'],
        "gender":data['gender'],
        "job":data['job'],
        "birth_date":data['birth_date'],
        "phone_number":data['phone_number'],
        'name':data['name'],
        'agree':data['agree']==True,
        'country':data['country'],
    })
    if result.acknowledged:
        return jsonify({"message": "Account created successfully"}), 200

@app.route("/api/account_modification", methods=["POST"])
def account_modification():
    data = request.get_json()
    if data is None:
        return jsonify({"message": "No data provided"}), 400
    data = data['account_info']
    collection = db.connectCollection("user")
    # Update a single record
    filter_query = {'email': data['email']}
    update_data = {'$set': {
        "email": data['email'],
        "pwd": data['pwd'],
        "user_type": data['user_type'],
        "gender":data['gender'],
        "job":data['job'],
        "birth_date":data['birth_date'],
        "phone_number":data['phone_number'],
        'name':data['name'],
        'country':data['country'],
    }}
    result = collection.update_one(filter_query, update_data)
    if result.acknowledged:
        return jsonify({"message": "Account updated successfully"}), 200

@app.route("/api/account_deletion", methods=["POST"])
def account_deletion():
    data = request.get_json()
    data = data['selectedItems_for_deleting']
    data = [record['Email'] for record in data]
    
    collection = db.connectCollection("user")
    result = collection.delete_many({'email': {'$in': data}})


    return jsonify({"message": "Account updated successfully"}), 200

    



if __name__ == '__main__':

    
    app.run(debug=True,host="0.0.0.0",port=3000)
