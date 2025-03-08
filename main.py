from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import utils.db as db
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_sse import sse
from datetime import timedelta, datetime
from bson.objectid import ObjectId
import json
import os
from PyPDF2 import PdfFileReader
import requests
import nltk
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
nltk.download('stopwords')
nltk.download('punkt')
nltk.download('punkt_tab')


from utils.T5_generate_summary import T5_model_generate_summary
from utils.BART_generate_summary import Bart_model_generate_summary
from utils.Fake_news_detection import detect_fake_news
from utils.Llama3_generate_summar import Llama3_model_generate_summary
from moviepy import VideoFileClip
import whisper


from utils.news_type_detection_n_recommendation.news_recommendation_ import  get_recommendations, custom_tokenizer
app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost:6379/0"
app.register_blueprint(sse, url_prefix='/stream')




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


@app.route("/api/udate_rating",methods=['GET', 'POST'])
def udate_rating():
    collection= db.connectCollection("news_summary")

    data = request.get_json()
    grade = data.get('rating', '')
    currebt_id = data.get('currebt_id', '')
    print(currebt_id)
    result = collection.update_one(
    {"_id": ObjectId(currebt_id)},  # filter to find the document to update
    {
        "$set": {  # update operator
            "grade": grade,
        }
    })
    if result.matched_count == 1 and result.modified_count == 1:
        print("Update successful")
    return jsonify(msg="rating is updated"), 200


@app.route("/api/T5_generate_summary",methods=['GET', 'POST'])  
@jwt_required()
def T5_generate_summary():
    grade =2.5
    collection= db.connectCollection("news_summary")

    data = request.get_json()
    selected_text = data.get('selectedText', '')
    temperature = data.get('temperature')
    currebt_id =  data.get('currebt_id')
  

    user_id = get_jwt_identity()
    user_id = json.loads(user_id)["_id"]
    
    # user_id = user_id.get()
    
    summary = T5_model_generate_summary(selected_text, temperature= temperature)
    probability, detection = detect_fake_news(unseen_news_text=summary)
    top10_relevant_news, prediction_news_type = get_recommendations(summary)
    
    summary = json.dumps(summary, default=str)
    top10_relevant_news = json.dumps(top10_relevant_news, default=str)
    if currebt_id is None:
        result = collection.insert_one({
            "grade":grade,
            "summary":summary,
            "model": "T5",
            "user_id":ObjectId(user_id),
            "news_type": prediction_news_type,
            "title":"",
            "fake_news_probability":probability,
            "date_time":datetime.now()
        })
        currebt_id = result.inserted_id
        currebt_id = json.dumps(currebt_id, default=str)
    
    else:
        print(currebt_id)
        result = collection.update_one(
        {"_id": ObjectId(currebt_id)},  # filter to find the document to update
        {
        "$set": { 
            "grade":grade,
            "summary":summary,
            "model": "T5",
            "user_id":ObjectId(user_id),
            "news_type": prediction_news_type,
            "title":"",
            "fake_news_probability":probability,
            "date_time":datetime.now()}
        })
      
        currebt_id = json.dumps(currebt_id, default=str)
    

   

    return jsonify(summary=summary, probability=int(probability*100),
                 inserted_id=currebt_id,
                    top10_relevant_news = top10_relevant_news,
                    detection=detection), 200

@app.route("/api/Llama3_generate_summary",methods=['GET', 'POST'])
def Llama3_generate_summary():
    data = request.get_json()
    selected_text = data.get('selectedText', '')
    temperature = data.get('temperature')

    summary = Llama3_model_generate_summary(selected_text, temperature= temperature)
    probability, detection = detect_fake_news(unseen_news_text=summary)
    top10_relevant_news = get_recommendations(summary)
    

    summary = json.dumps(summary, default=str)
    top10_relevant_news = json.dumps(top10_relevant_news, default=str)

    return jsonify(summary=summary, probability=int(probability*100),
                 
                    top10_relevant_news = top10_relevant_news,
            
                    detection=detection), 200


@app.route("/api/pie_chart",methods=['GET', 'POST'])
@jwt_required()
def pie_chart():
    user_info = get_jwt_identity()
    user_type = json.loads(user_info)["user_type"]
    user_id = json.loads(user_info)["_id"]
    data = request.get_json()
    target_year = data.get('selected_year', '')

    collection= db.connectCollection("news_summary")

    result=""

    if user_type =="System administrator":
        result = collection.aggregate([
            {
            "$match": {"$expr": {
                "$eq": [
                    {"$year": "$date_time"},
                    target_year
                ]
            }


            },
            },
            {
                '$group': {
                    '_id':{ 'grade': '$grade', },  
                    'count': {'$sum': 1}
            }
            },
            {
            '$sort': {
                    '_id.grade': 1,
                      
             }
            }
        ])
    else:
        result = collection.aggregate([
            {
            "$match": {
                "user_id": ObjectId(user_id),
                "$expr": {
                "$eq": [
                    {"$year": "$date_time"},
                    target_year
                ]
            }
            },
            },
            {
            '$group': {
                    '_id':{ 'grade': '$grade', },  
                    'count': {'$sum': 1}
            }
            },
            {
            '$sort': {
                        '_id.grade': 1,
            }
            }
        ])

    result = list(result)  # store the result in a variable
    
    print("result",result)
    transformed_result = []

    for entry in result:
        grade = entry['_id']['grade']
        count = entry['count']
        transformed_result.append({'_id': grade, 'count': count})


    if transformed_result:  # check if the result is not empty
        ids, counts = map(list, zip(*[(float(item['_id']), item['count']) for item in transformed_result]))
    else:
        ids, counts = [], []


    ids = [f"{item}" +" Star" for item in ids ]
    print(ids)  
    print(counts) 
    ids = json.dumps(ids,default=list)
    counts = json.dumps(counts,default=list)



    result = collection.aggregate([
        {
            '$group': {
                '_id': {
                    '$year': '$date_time'
                }
            }
        },
        {
            '$sort': {'_id': 1}
        }
    ])

    # Extract the years from the aggregation result
    available_years = [entry['_id'] for entry in result]
    available_years = json.dumps(available_years,default=list)
    print(available_years,"available_years")


    return jsonify(counts=counts,ids=ids, available_years=available_years), 200



@app.route("/api/line_chart",methods=['GET', 'POST'])
@jwt_required()
def line_chart():
    user_info = get_jwt_identity()

    data = request.get_json()
    target_year = data.get('selected_year', '')
    user_type = json.loads(user_info)["user_type"]
    user_id = json.loads(user_info)["_id"]
    
    collection= db.connectCollection("news_summary")
    result=""
    if user_type =="System administrator":
        result = collection.aggregate([
            {
            "$match": {"$expr": {
                "$eq": [

                    {"$year": "$date_time"},
                    target_year
                ]
            }


            },
            },
            {
                '$group': {
                    '_id':{ 'grade': '$grade', 
                           'date_time':{
                                '$dateToString': {
                                    'format': f'%Y-%m',
                                    'date': '$date_time'
                                }
                           }
                           },  
                    'count': {'$sum': 1}
            }
            },
            {
            '$sort': {
                        '_id.grade': 1,
                      '_id.date_time': 1
                      }
            }
        ])
    else:
        result = collection.aggregate([
              {
            "$match": {
                "user_id": ObjectId(user_id),
                "$expr": {
                "$eq": [
                    {"$year": "$date_time"},
                    target_year
                ]
            }
            },
            },
            {
            '$group': {
                    '_id':{ 'grade': '$grade', 
                           'date_time':{
                                '$dateToString': {
                                    'format': f'%Y-%m',
                                    'date': '$date_time'
                                }
                           }
                           },  
                    'count': {'$sum': 1}
            }
            },
            {
            '$sort': {
                '_id.grade': 1,
                '_id.date_time': 1

            }
            }
        ])

    result_list = list(result)  # store the result in a variable

    # Transforming the result
    transformed_result = {}

    for entry in result_list:
        grade = entry['_id']['grade']
        date_time = entry['_id']['date_time']
        count = entry['count']
        
        if grade not in transformed_result:
            transformed_result[grade] = {
                "name": f"{grade}",
                "data": []
            }
        
        transformed_result[grade]['data'].append([date_time, count])

    # Convert the dictionary to a list
    final_result = list(transformed_result.values())

    print(final_result)
    final_result = json.dumps(final_result,default=list)

    return jsonify(data=final_result), 200







@app.route("/api/BART_generate_summary",methods=['GET', 'POST'])
def Bart_generate_summary():
    data = request.get_json()
    selected_text = data.get('selectedText', '')
    temperature = data.get('temperature')

    summary = Bart_model_generate_summary(selected_text, temperature= temperature)
    probability, detection = detect_fake_news(unseen_news_text=summary)
    top10_relevant_news = get_recommendations( summary)
    
    summary = json.dumps(summary, default=str)
    top10_relevant_news = json.dumps(top10_relevant_news, default=str)

    return jsonify(summary=summary, probability=int(probability*100),
                    top10_relevant_news = top10_relevant_news,
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

@app.route("/api/upload_video_file", methods=["POST"])
def upload_video_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        # Save the file to a temporary location
        temp_video_path = os.path.join('/tmp', file.filename)
        file.save(temp_video_path)

        # Extract audio from video
        video = VideoFileClip(temp_video_path)
        temp_audio_path = temp_video_path.replace('.mp4', '.wav')
        video.audio.write_audiofile(temp_audio_path)

        # Use Whisper to get the transcript
        model = whisper.load_model("base")
        result = model.transcribe(temp_audio_path)
        transcript = result['text']

        # Clean up temporary files
        os.remove(temp_video_path)
        os.remove(temp_audio_path)

        return jsonify({'transcript': transcript})

    return jsonify({'error': 'File upload failed'}), 500







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
