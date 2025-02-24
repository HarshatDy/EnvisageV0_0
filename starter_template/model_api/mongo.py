import pymongo
from dotenv import load_dotenv
import os
load_dotenv()   

url = os.getenv('MONGO_URL')

client = pymongo.MongoClient(url)

db = client['claude_api']