import os
import json
import time
from threading import Thread, Lock
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Handle imports for both Django and standalone execution
try:
    # Try relative imports (for Django)
    from .web_scrapper_api import get_links_and_content_from_page
    from .mongo import db
    from .logging_scripts import *
except ImportError:
    try:
        # Try absolute imports (for standalone script)
        from web_scrapper_api import get_links_and_content_from_page
        from mongo import db
        from logging_scripts import *
    except ImportError:
        print("Warning: Could not import some modules. Some functionality may be limited.")
        # Define fallback or dummy functions/variables if needed
        db = {}

from google import genai
import google.generativeai as google_genai
# from genai import types


class GeminiAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.client = genai.Client(api_key=self.api_key)
        
        self.today = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"gemini_{self.today}_log.txt"
        try:
            create_log_file(self.log_file)
        except NameError:
            print(f"Warning: create_log_file function not available. Log file {self.log_file} not created.")
        
        self.thread_lock = Lock()
        self.thread_result = {}
        self.summary = {}
        self.db = db['gemini_api']
        self.today_date = datetime.today().strftime('%Y-%m-%d')
        self.MAX_RETRY = 5
        self.MAX_BATCHES = 5
        
        # Initialize model
        # self.model = genai.GenerativeModel('gemini-pro')

    def get_news(self):
        news_sources = {
            "climate_tech_general": [
                "https://www.reuters.com/",
                "https://www.bloomberg.com/",
                "https://www.theguardian.com/",
                "https://www.ft.com/"
            ],
            "climate_tech_specialized": [
                "https://climateinsider.com/",
                "https://www.canarymedia.com/",
                "https://www.greentechmedia.com/",
                "https://sifted.eu/sector/climatetech"
            ],
            "climate_tech_research": [
                "https://www.nature.com/",
                "https://www.science.org/"
            ],
            "government_politics_general": [
                "https://apnews.com/",
                "https://www.reuters.com/",
                "https://www.bbc.com/news",
                "https://www.nytimes.com/",
                "https://www.politico.com/"
            ],
            "government_politics_websites": [
                "https://www.whitehouse.gov/",
                "https://www.gov.uk/",
                "https://ec.europa.eu/"
                # Add other government websites as needed
            ],
            "travel_specialized": [
                "https://skift.com/",
                "https://www.travelweekly.com/",
                "https://thepointsguy.com/",
                "https://www.phocuswire.com/"
            ],
            "travel_general": [
                "https://www.nytimes.com/section/travel",
                "https://www.latimes.com/travel",
                "https://www.cntraveler.com/"
            ],
            "stock_market": [
                "https://www.bloomberg.com/",
                "https://www.reuters.com/",
                "https://www.wsj.com/",
                "https://www.cnbc.com/",
                "https://www.marketwatch.com/"
            ]
        }
        return news_sources
    
    def get_categories(self):
        news_categories = {
            "Politics": [], "Business": [], "Economy": [], "Finance": [], "Health": [], "Science": [], "Technology": [], 
            "Environment": [], "Education": [], "Sports": [], "Entertainment": [], "Culture": [], "Lifestyle": [], "Travel": [], 
            "Food": [], "Fashion": [], "Art": [], "Music": [], "Film": [], "Television": [], "Theater": [], "Books": [], 
            "Automotive": [], "Real Estate": [], "Law": [], "Crime": [], "Public Safety": [], "Weather": [], "Natural Disasters": [], 
            "Space": [], "Agriculture": [], "Energy": [], "Transportation": [], "Military": [], "International Affairs": [], 
            "Human Rights": [], "Social Issues": [], "Religion": [], "Philanthropy": [], "Technology Innovations": [], 
            "Cybersecurity": [], "Artificial Intelligence": [], "Blockchain": [], "Startups": [], "Investments": [], 
            "Cryptocurrency": [], "Economics": [], "Trade": [], "Labor": [], "Consumer Affairs": [], "Public Health": [], 
            "Mental Health": [], "Nutrition": [], "Fitness": []
        }
        return news_categories

    def generate(self, txt):
        model_info = google_genai.get_model("models/gemini-2.0-flash-lite")
        model = google_genai.GenerativeModel("models/gemini-2.0-flash-lite")
        # append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][generate] Model input token limit: {model_info.input_token_limit=}")
        # append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][generate] Model output token limit: {model_info.output_token_limit=}")
        # print(f"input Token{model_info.input_token_limit=}")
        # print(f"Output Token{model_info.output_token_limit=}")
        required_input_tokens = model.count_tokens(txt)
        print(f"Required Token for txt ={required_input_tokens=}")
        # append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][generate] Required input tokens: {required_input_tokens}")
        # while response.candidates[0].finish_reason == "MAX_TOKEN" and required_input_tokens > 0:
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[txt])
        # Get the response text
        response_text = response.text
        print(response)
        print(f"Finish reason: {response.candidates[0].finish_reason}")
        # Extract usage metadata
        # try:
        #     usage_metadata = {
        #         "candidates": len(response.candidates),
        #         "prompt_token_count": response.usage_metadata.prompt_token_count,
        #         "candidates_token_count": response.usage_metadata.candidates_token_count,
        #         "total_token_count": response.usage_metadata.total_token_count
        #     }
        #     append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][generate] Usage metadata: {json.dumps(usage_metadata)}")
        # except (AttributeError, TypeError) as e:
        #     append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][generate] Failed to log usage metadata: {str(e)}")
        
        # Log model token limits to the log file
        # print(response.text)
        return response
    
    def start_gemini_assistant(self):
        """
        Similar to start_openai_assistant but using Gemini API.
        Gets news from sources, processes them in threads and stores results in MongoDB.
        """
        gemini_links_db = self.db
        
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Starting Gemini Assistant")
        news_sources = self.get_news()
        links = {}
        lock = self.thread_lock
        result_grded_news = {}
        
        def process_lnks(category, sources):
            nonlocal links    
            if category not in links:
                links[category] = {}
                
            for source in sources:
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Getting news from {source}")
                try:
                    links[category][source] = get_links_and_content_from_page(source)
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Successfully extracted news from {source}")
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] *****************************************************")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] ************************ERROR************************")
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Failed to extract news from {source}: {e}")
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] *****************************************************")
                    
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Before processing category: {links[category]} and length {len(str(links[category]))} and for category {category}")
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Thread ID for {category}: {thread.ident}")
            
            if not category in result_grded_news:
                result_grded_news[category] = []
                
            with lock:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Thread {thread.ident} acquired lock for {category}")
                result_grded_news[category] = self.grd_nws(links[category], category)
                
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] After processing category: {result_grded_news[category]} and length {len(result_grded_news[category]) if result_grded_news[category] else 0} and for category {category}")
            
            with lock:
                try:
                    gemini_links_db.insert_one({self.today_date: {category: result_grded_news[category]}})
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Successfully inserted data for {category} into MongoDB")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Failed to insert data into MongoDB: {e}")
                    print(f"Failed to insert data into MongoDB: {e}")
                    
        threads = []
        for category, sources in news_sources.items():
            thread = Thread(target=process_lnks, args=(category, sources))
            threads.append(thread)
            thread.start()
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Starting thread for {category} with thread ID: {thread.ident}")
            
        for thread in threads:
            thread.join()
            
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] News retrieval complete")
        return None

    def grd_nws(self, links, category):
        news = links
        summary = self.summary
        result_links = {}
        categories = self.get_categories()
        
        if news and summary:
            return None
        elif news:
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] News is present for category {category}")
            
            for top_url in list(links.keys()):
                step = max(1, int(len(list(news[top_url].items()))/self.MAX_BATCHES))
                link_items = [list(news[top_url].items())[j:j+step] for j in range(0, len(list(news[top_url].items())), step)]
                
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing {len(link_items)} batches for {category}")
                
                for link_item in link_items:
                    # Log the size of link_item in bytes and KB
                    try:
                        link_item_str = str(link_item)
                        link_item_size_bytes = len(link_item_str)
                        link_item_size_kb = link_item_size_bytes / 1024
                        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing batch with size: {link_item_size_bytes} bytes ({link_item_size_kb:.2f} KB)")
                    except Exception as e:
                        append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to calculate batch size: {str(e)}")
                    
                    # Process the batch with retry logic and batch splitting
                    self._process_batch_with_retry(link_item, result_links, categories, top_url, self.MAX_RETRY)
                
            # Remove empty categories
            result_links = {k: v for k, v in result_links.items() if v}
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Final categorized news: {result_links}")
            
        return result_links

    def _process_batch_with_retry(self, link_item, result_links, categories, top_url, retries_remaining):
        """Helper method to process a batch with retry logic and batch splitting."""
        if retries_remaining <= 0:
            append_to_log(self.log_file, f"[GEMINI][CRITICAL][{datetime.today().strftime('%H:%M:%S')}][grd_nws] CRITICAL ERROR: Could not process the data after all retry attempts")
            return
        
        try:
            # Log the size of link_item after converting to string
            try:
                link_item_str = str(link_item)
                link_item_size = len(link_item_str)
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing batch of size {link_item_size} bytes ({link_item_size/1024:.2f} KB)")
            except Exception as e:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to log link_item size: {str(e)}")
            prompt = f"""
            Analyze these articles: {link_item}
            Categorize each article into the most appropriate categories from this list: {list(categories.keys())}
            An article can belong to multiple categories if relevant.
            
            Return the result as a dictionary where:
            - Keys are category names from the provided categories list
            - Values are lists of tuples containing (article_url, [title, content])
            
            Only include articles that are relevant to at least one category.
            Format the response as a valid Python dictionary.

            Only return the python dict and nothing else in less than 100 words, avoid ``` and word python in the string
            """
            
            response = self.generate(prompt)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Received grading response: {response}")
            
            # Parsing response - assuming Gemini returns clean Python dict text
            response_text = response.text
            # Remove markdown formatting if present
            if "```python" in response_text:
                response_text = response_text.split("```python")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            categorized_data = eval(response_text)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Received categorization: {categorized_data}")
            
            # Merge the categorized data into result_links
            for cat, articles in categorized_data.items():
                if cat not in result_links:
                    result_links[cat] = {}
                if articles:  # Only process if there are articles
                    if top_url not in result_links[cat]:
                        result_links[cat][top_url] = {}
                    for article_url, content in articles:
                        result_links[cat][top_url][article_url] = content
                        
        except Exception as e:
            append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Error processing batch: {str(e)}. Retries remaining: {retries_remaining-1}")
            
            # If batch processing failed, split the batch into smaller pieces
            if len(link_item) > 1:
                mid = len(link_item) // 2
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Splitting batch of size {len(link_item)} into two smaller batches")
                
                # Process first half
                self._process_batch_with_retry(link_item[:mid], result_links, categories, top_url, retries_remaining-1)
                # Process second half
                self._process_batch_with_retry(link_item[mid:], result_links, categories, top_url, retries_remaining-1)
            else:
                # If we're already down to a single item and still failing, try one more time with reduced retries
                time.sleep(2)  # Longer pause before retrying a single item
                self._process_batch_with_retry(link_item, result_links, categories, top_url, retries_remaining-1)

if __name__ == "__main__":
    client_api = GeminiAPI()
    client_api.start_gemini_assistant()
    # client_api.generate("This is a test prompt for Gemini API.")

