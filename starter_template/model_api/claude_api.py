import anthropic
from dotenv import load_dotenv
import os
from web_scrapper_api import get_links_and_content_from_page
from mongo import db
from datetime import datetime
from logging_scripts import create_log_file, append_to_log





# message = client.messages.create(
#     model="claude-3-5-sonnet-20241022",
#     max_tokens=1000,
#     temperature=0,
#     system="You are a World class Journalist, who's aim is to provide the best news to the world in a personal way",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "text",
#                     "text": "Get todays news from https://timesofindia.indiatimes.com/india/kailash-mansarovar-yatra-will-resume-this-year-says-mea-after-foreign-secretary-vikram-misri-holds-high-level-meet-in-beijing/articleshow/117607706.cms"
#                 }
#             ]
#         }
#     ]
# )
# print(message.content[0].text)


# Replace placeholders like {{NEWS_ARTICLE}} with real values,
# because the SDK does not support variables.


class ClaudeAIAPI:
    def __init__(self):
        load_dotenv()
        self.client = anthropic.Anthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )

        self.log_file = f"claude_{datetime.today().strftime('%Y_%m_%d')}_log.txt"
        create_log_file(log_file) 
        

    def claude_api_request(self, txt)->str:
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            temperature=1,
            system="You are tasked with creating a crispy, eye-catching, and informative summary of a news article in about 300 words. Your goal is to capture the essence of the news story while making it engaging and easy to digest for readers.\n\nHere is the news article you need to summarize:\n\n<news_article>\n{{NEWS_ARTICLE}}\n</news_article>\n\nFollow these steps to create your summary:\n\n1. Read the article carefully and identify the key points, including:\n   - The main topic or event\n   - Who is involved\n   - Where and when it happened\n   - Why it's significant\n   - Any notable quotes or statistics\n\n2. Structure your summary as follows:\n   a. Headline (1 line): Create a catchy, attention-grabbing headline that encapsulates the main story.\n   b. Lead paragraph (2-3 sentences): Provide a hook that draws the reader in and summarizes the most important information.\n   c. Key points (3-4 bullet points): List the most crucial details of the story.\n   d. Context (1-2 sentences): Briefly explain any necessary background information or wider implications.\n   e. Conclusion (1 sentence): End with a thought-provoking statement or question about the story's impact or future developments.\n\n3. Keep your summary concise and aim for approximately 300 words.\n\n4. Use clear, vivid language to make the summary engaging:\n   - Employ active voice and strong verbs\n   - Include relevant metaphors or analogies where appropriate\n   - Use descriptive adjectives sparingly but effectively\n\n5. Ensure your summary is informative by:\n   - Focusing on facts rather than opinions\n   - Including specific details, numbers, or quotes that add value\n   - Explaining complex concepts in simple terms\n\n6. Make your summary visually appealing:\n   - Use short paragraphs and bullet points for easy readability\n   - Incorporate subheadings if necessary to break up longer sections\n\nPresent your summary within <summary> tags, following the structure outlined above. Remember to make it crispy, eye-catching, and informative while staying true to the original news story.",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": txt,
                        }
                    ]
                }
            ]
        )
        append_to_log(self.log_file, f"[CLAUDE_API][INF][{datetime.today().strftime('%H:%M:%S')}] {message.content[0].text}")
        print(message.content)
        return message.content[0].text

    news_sources = {
        "CLIMATE_TECHNOLOGY": {
            "primary_sources": [
                "https://www.bloomberg.com/green",
                "https://www.carbonbrief.org",
                "https://www.climatechangenews.com",
                "https://cleantechnica.com"
            ],
            "industry_analysis": [
                "https://www.greentechmedia.com",
                "https://www.environmental-finance.com"
            ]
        },
        "GOVERNMENT_POLICY": {
            "international_coverage": [
                "https://www.reuters.com/policy",
                "https://www.ft.com",
                "https://www.economist.com"
            ],
            "regional_national": [
                "https://www.politico.com/energy-and-environment",
                "https://www.euractiv.com"
            ]
        },
        "TRAVEL_INDUSTRY": {
            "industry_news": [
                "https://www.skift.com",
                "https://www.phocuswire.com",
                "https://www.travelweekly.com"
            ],
            "sustainability_focus": [
                "https://www.sustainabletravel.org",
                "https://www.responsibletravel.org"
            ]
        },
        "STOCK_MARKET": {
            "sector_specific": [
                "https://www.environmental-finance.com",
                "https://www.renewableenergyworld.com"
            ],
            "general_financial": [
                "https://www.bloomberg.com/markets",
                "https://www.ft.com/markets",
                "https://www.reuters.com/business"
            ]
        },
        "CROSS_SECTOR": {
            "general_coverage": [
                "https://www.theguardian.com/environment",
                "https://www.technologyreview.com",
                "https://www.nature.com/news",
                "https://www.science.org"
            ]
        }
    }

    # # Example of how to access the lists:

    def start_claude_assistant(self):
        claude_links_db = db['claude_api']
        for key in self.news_sources:   # Check if this works
            append_to_log(self.log_file, f"[CLAUDE_API][INF][{datetime.today().strftime('%H:%M:%S')}] News for {key}")
            # print(f"News for {key}")
            for sub_source in self.news_sources[key]:
                links={}
                append_to_log(self.log_file, f"[CLAUDE_API][INF][{datetime.today().strftime('%H:%M:%S')}] Getting news from sub_source : {sub_source}")
                # print(f"Getting news from {sub_source}")
                for source in self.news_sources[key][sub_source]:
                    try:
                        links[source] = get_links_and_content_from_page(source)
                    except Exception as e:
                        append_to_log(self.log_file, f"[CLAUDE_API][ERR][{datetime.today().strftime('%H:%M:%S')}] ************************ERROR************************")
                        append_to_log(self.log_file, f"[CLAUDE_API][ERR][{datetime.today().strftime('%H:%M:%S')}] Failed to extract news from {source} with error: {e}")
                        append_to_log(self.log_file, f"[CLAUDE_API][ERR][{datetime.today().strftime('%H:%M:%S')}] *****************************************************")
                        print("************************ERROR************************")
                        print(f"Failed to extract news from {source} with error: {e}")
                        print("*****************************************************")
                print("\n\n")
                today = datetime.today().strftime('%Y-%m-%d')
                try:
                    claude_links_db.insert_one({today:{key:{sub_source:links}}})
                    append_to_log(self.log_file, f"[CLAUDE_API][INF][{datetime.today().strftime('%H:%M:%S')}] Successfully inserted data for {key} - {sub_source}")
                except Exception as e:
                    append_to_log(self.log_file, f"[CLAUDE_API][ERR][{datetime.today().strftime('%H:%M:%S')}] Failed to insert data into MongoDB: {e}")
                    print(f"Failed to insert data into MongoDB: {e}")
                claude_links_db.insert_one({today:{key:{sub_source:links}}})
                # print("--------------------------------------------")
                # print(links)
                # print("--------------------------------------------")
            print("News retrieval complete")


            