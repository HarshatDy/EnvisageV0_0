import pymongo

url = "mongodb+srv://dhanayatharshat:envisagedb01@envisagedb01.7zmo7.mongodb.net/"

client = pymongo.MongoClient(url)

db = client['claude_api']