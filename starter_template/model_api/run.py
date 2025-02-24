try:
    from .openai_api import OpenAiAPI
    from .mongo import db
except ImportError:
    from openai_api import OpenAiAPI
    from mongo import db

client = OpenAiAPI()

db = db['openai_api']

query = ({f"{"2025-02-18"}.{"Government Politics"}": {"$exists":True}})
result = db.find(query)
links = {}
for doc in result:
    for date, categories in doc.items():
        if date == "_id":
            continue
        for category, sources in categories.items():
            if category not in links:
                links[category] = {}
            for source, content in sources.items():
                links[category][source] = content

print(" BEFORE CALLING the LINKS is : ", links)

client.grd_nws(links)








