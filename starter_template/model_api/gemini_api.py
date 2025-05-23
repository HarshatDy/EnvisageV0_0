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
    from .hugging_face_api_enhanced import check_url_content_relevance, categorize_content
except ImportError:
    try:
        # Try absolute imports (for standalone script)
        from web_scrapper_api import get_links_and_content_from_page
        from mongo import db
        from logging_scripts import *
        from hugging_face_api_enhanced import check_url_content_relevance, categorize_content
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

    def get_news_src(self):
        """Renamed from get_news to match OpenAI API function name"""
        news_sources = {
        "0": [
        "https://www.ndtv.com",  # NDTV
        "https://www.timesofindia.indiatimes.com",  # Times of India
        "https://www.thehindu.com",  # The Hindu
        "https://www.indianexpress.com",  # The Indian Express
        "https://www.indiatoday.in",  # India Today
        ],
        "1": [
        "https://www.mintpressnews.com",  # Mint
        "https://www.dnaindia.com",  # DNA India
        "https://www.hindustantimes.com",  # Hindustan Times
        "https://www.cnbctv18.com",  # CNBC TV18
        "https://www.scoopwhoop.com",  # ScoopWhoop
        ],
        "2": [
        "https://www.firstpost.com",  # Firstpost
        "https://www.moneycontrol.com",  # Moneycontrol
        "https://www.thequint.com",  # The Quint
        "https://www.deccanherald.com",  # Deccan Herald
        "https://www.news18.com",  # News18
        ],
        "3": [
        "https://www.thenewsminute.com",  # The News Minute
        "https://www.wionews.com",  # WION News
        "https://www.sify.com",  # Sify News
        "https://www.opindia.com",  # OpIndia
        "https://www.economictimes.indiatimes.com",  # Economic Times
        ],
        "4": [
        "https://www.tribuneindia.com",  # Tribune India
        "https://www.mid-day.com",  # Mid-Day
        "https://www.aryanews.com",  # Arya News
        "https://www.kashmirreader.com",  # Kashmir Reader
        "https://www.bhaskar.com",  # Dainik Bhaskar
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

    def openai_api_request(self, txt):
        """Renamed from generate to match OpenAI API function name"""
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][openai_api_request] Received Gemini request for content {txt}")
        
        model_info = google_genai.get_model("models/gemini-2.0-flash-lite")
        model = google_genai.GenerativeModel("models/gemini-2.0-flash-lite")
        required_input_tokens = model.count_tokens(txt)
        print(f"Required Token for txt ={required_input_tokens=}")
        
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[txt])
        
        print(response)
        print(f"Finish reason: {response.candidates[0].finish_reason}")
        
        # Create a structure similar to OpenAI's response for compatibility
        class ResponseWrapper:
            def __init__(self, gemini_response):
                self.data = [type('obj', (object,), {
                    'content': [type('obj', (object,), {
                        'text': type('obj', (object,), {'value': gemini_response.text})
                    })]
                })]
                self.text = gemini_response.text
                self.candidates = gemini_response.candidates
                
        return ResponseWrapper(response)
    
    def start_gemini_assistant(self):
        """
        Similar to start_openai_assistant but using Gemini API.
        Gets news from sources, processes them in threads and stores results in MongoDB.
        """
        gemini_links_db = self.db
        
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Starting Gemini Assistant")
        news_sources = self.get_news_src()
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
            
            if category not in result_grded_news:
                result_grded_news[category] = []
                
            with lock:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Thread {thread.ident} acquired lock for {category}")
                
                # Step 1: Check URL relevance using HuggingFace API
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Checking URL content relevance for {category}")
                relevance_results = check_url_content_relevance(links[category], threshold=0.4)
                
                # Filter out irrelevant content
                filtered_links = {}
                for base_url, articles in links[category].items():
                    filtered_links[base_url] = {}
                    for article_url, content in articles.items():
                        if base_url in relevance_results and article_url in relevance_results[base_url] and relevance_results[base_url][article_url] == 1:
                            filtered_links[base_url][article_url] = content
                            
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Filtered {sum(len(articles) for articles in links[category].values()) - sum(len(articles) for articles in filtered_links.values())} irrelevant articles")
                
                # Step 2: Categorize content using HuggingFace API
                news_categories = self.get_categories()
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Categorizing content for {category}")
                categorized_content = categorize_content(filtered_links, news_categories)
                
                # Convert categorized content to the expected format for result_grded_news
                result_grded_news[category] = categorized_content
                
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] After processing category: {result_grded_news[category]} and length {len(str(result_grded_news[category])) if result_grded_news[category] else 0} and for category {category}")
            
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
                
            # Create lists of categories and article items for index reference
            categories_list = list(categories.keys())
            
            prompt = f"""
            Analyze these articles: {link_item}
            
            I'll provide you with:
            1. A list of article items where each item is a tuple of (article_url, [title, content])
            2. A list of category names: {categories_list}
            
            Return a dictionary mapping category indices to lists of article indices that belong to that category.
            For example: {{2: [0, 3], 5: [1, 2]}} means:
            - Articles at indices 0 and 3 belong to the category at index 2
            - Articles at indices 1 and 2 belong to the category at index 5
            
            An article can belong to multiple categories if relevant.
            Only include articles that are relevant to at least one category.
            Format the response as a valid Python dictionary of indices.

            Only return a python dict data structure, avoid ``` and word python in the string
            """
            
            response = self.openai_api_request(prompt)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Received grading response")
            
            # Log the raw response text for debugging
            try:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Raw response text: {response.text}")
            except Exception as log_error:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to log response text: {str(log_error)}")
                
            # Parsing response
            response_text = response.text
            # Remove markdown formatting if present
            if "```python" in response_text:
                response_text = response_text.split("```python")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            try:
                index_mapping = eval(response_text)
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Successfully parsed index mapping")
                
                # Convert the index mapping to actual data
                categorized_data = {}
                for cat_idx, article_indices in index_mapping.items():
                    if cat_idx < len(categories_list):
                        cat_name = categories_list[cat_idx]
                        if cat_name not in categorized_data:
                            categorized_data[cat_name] = []
                        
                        for article_idx in article_indices:
                            if article_idx < len(link_item):
                                categorized_data[cat_name].append(link_item[article_idx])
                
                # Merge the categorized data into result_links
                for cat, articles in categorized_data.items():
                    if cat not in result_links:
                        result_links[cat] = {}
                    if articles:  # Only process if there are articles
                        if top_url not in result_links[cat]:
                            result_links[cat][top_url] = {}
                        for article_url, content in articles:
                            result_links[cat][top_url][article_url] = content
            except Exception as parsing_error:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to parse response: {str(parsing_error)}")
                raise parsing_error  # Re-raise to trigger the split and retry
                        
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

    def process_category(self, category, sources):
        """
        Process news sources for a specific category, generating summaries for each article.
        """
        result = {}
        for source, content in sources.items():
            for link_url, details_url in content.items():
                for link, details in details_url.items():
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][process_category] LINK from the news: {link} with details: {details}")
                    
                    if len(details) != 2:
                        append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][process_category] Skipping link {link} as it has insufficient details")
                        print(f"Skipping link {link} as it has insufficient details")
                        continue
                        
                    title, news_content = details
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Processing summary for {link} with title: {title}")
                    
                    prompt = f"Summarize the news from {link} with the title {title} and content {news_content} with at least 100 words"
                    summary = self.openai_api_request(prompt)
                    
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Summary result: {summary.data[0].content[0].text.value}")
                    
                    if category not in result:
                        result[category] = {}
                    if source not in result[category]:
                        result[category][source] = []
                        
                    result[category][source].append({
                        "link": link,
                        "title": title,
                        "content": news_content,
                        "summary": summary.data[0].content[0].text.value
                    })
                    
                    with self.thread_lock:
                        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Thread acquired lock for {category}")
                        self.thread_result[category] = result

    def check_news_in_db(self, preferred_category=None):
        """
        Check if news for today's date exists in the database.
        Optionally filter by category if preferred_category is specified.
        """
        gemini_links_db = self.db
        today_date = self.today_date
        
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] Checking news for date: {today_date}")
        
        if not preferred_category:
            query = {self.today_date: {"$exists": True}}
        else:
            query = {f"{today_date}.{preferred_category}": {"$exists": True}}
            
        news_data_cursor = gemini_links_db.find(query)
        
        collected_news = {}
        
        for news_data in news_data_cursor:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] Found news data in database {news_data}")
            
            for date, categories in news_data.items():
                if date == "_id":
                    continue
                for category, sources in categories.items():
                    if category not in collected_news:
                        collected_news[category] = {}
                    for source, content in sources.items():
                        collected_news[category][source] = content
                        
        if not collected_news:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] No news data found for today in the database")
            return None
            
        return collected_news

    def run_sumarizing_threads(self):
        """
        Run threads to summarize news content for each category.
        """
        threads = []
        self.thread_result.clear()
        content = self.check_news_in_db()
        
        if not content:
            append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] No content found in database")
            return None
            
        for category, sources in content.items():
            thread = Thread(target=self.process_category, args=(category, sources))
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] Starting thread")
            threads.append(thread)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] Starting thread for {category} with {thread.ident}")
            thread.start()
            
        for thread in threads:
            thread.join()

    def push_results_to_db(self, result, result_type):
        """
        Push summarized results to the database.
        """
        print("Result from Gemini") 
        print("CONTENT FROM DB")
        gemini_links_db = self.db
        gemini_links_db.insert_one({result_type:{self.today_date: result}})
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][push_results_to_db] Pushed {result_type} to database")

    def fetch_todays_results(self):
        """
        Fetch today's results from the database.
        """
        gemini_links_db = self.db
        query = {f"Result.{self.today_date}": {"$exists": True}}
        
        results_cursor = gemini_links_db.find(query)
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Fetching today's results from MongoDB")
        
        result_json = None
        for result in results_cursor:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Query result: {result['_id']}")
            # Convert ObjectId to string representation
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Processing result: {result['_id']}")
            result['_id'] = str(result['_id'])
            result_json = json.dumps(result, indent=4)
            
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Result JSON: {result_json}")
        return result_json

    def fetch_content_and_run_summary(self):
        """
        Fetch content and run summary generation if not already done.
        Uses HuggingFace summarize_articles for initial summarization before Gemini processing.
        """
        result_json = self.fetch_todays_results()
        if not result_json:
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No results found for today, starting summarization process")
            
            # Get content from database first
            content = self.check_news_in_db()
            if not content:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No content found in database")
                return None
                
            # Step 1: Use HuggingFace summarization for each article
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Starting local summarization with HuggingFace")
            try:
                from hugging_face_api_enhanced import summarize_articles, generate_overall_summary
                
                # Process each category with the summarize_articles function
                summarized_content = {}
                for category, sources in content.items():
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Summarizing content for category: {category}")
                    category_summaries = summarize_articles(sources, min_words=75)
                    
                    if category not in summarized_content:
                        summarized_content[category] = {}
                    
                    # Convert summaries to the expected format (keeping consistent with the thread_result format)
                    for source, article_summaries in category_summaries.items():
                        if source not in summarized_content[category]:
                            summarized_content[category][source] = []
                            
                        for article_url, summary in article_summaries.items():
                            # Get original content
                            original_content = sources.get(source, {}).get(article_url, ["", ""])
                            title = original_content[0] if isinstance(original_content, list) and len(original_content) > 0 else ""
                            content = original_content[1] if isinstance(original_content, list) and len(original_content) > 1 else ""
                            
                            summarized_content[category][source].append({
                                "link": article_url,
                                "title": title,
                                "content": content,
                                "summary": summary
                            })
                
                # Save summarized content to thread_result for database storage
                self.thread_result = summarized_content
                
                # Push results to database if we have summarized content
                if self.thread_result:
                    self.push_results_to_db(self.thread_result, "Result")
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Successfully pushed summarized results to MongoDB")
                else:
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No thread_result found, nothing to push to MongoDB")
                
                # Generate an overall summary using HuggingFace
                try:
                    overall_summary = generate_overall_summary(content)
                    self.summary = {"huggingface_summary": overall_summary}
                    formatted_result = {self.today_date: overall_summary}
                    self.push_results_to_db(formatted_result, "Summary")
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Successfully generated and stored overall summary")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Error generating overall summary: {str(e)}")
                
            except ImportError as e:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Error importing HuggingFace modules: {str(e)}")
                # Fall back to original threading approach
                self.run_sumarizing_threads()
                if self.thread_result:
                    self.push_results_to_db(self.thread_result, "Result")
            except Exception as e:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Error during HuggingFace summarization: {str(e)}")
                # Fall back to original threading approach
                self.run_sumarizing_threads()
                if self.thread_result:
                    self.push_results_to_db(self.thread_result, "Result")
        else:
            # If results already exist, use Gemini for enhanced summary
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Result JSON length: {len(result_json)}")
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Result : {result_json}")
            result_length = len(result_json)
            json_parts = []

            if result_length > 32000:  # Gemini has lower context window than GPT-4
                json_parts = [result_json[i:i+31500] for i in range(0, len(result_json), 31500)]
            else:
                json_parts.append(result_json)
                
            for json_part in json_parts:
                content = f"""Please analyze this news data and create a summary of 400 words:
                1. Key bullet points for each category
                2. Important trends or patterns
                3. A brief executive summary
                4. Highlight any critical developments
                Data: {json_part}"""
                
                self.summary[json_part] = self.openai_api_request(content)
                
            if bool(self.summary):
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] SUMMARY IS PRESENT")
                print("Summary is present")
                self.check_summary_present()

    def check_summary_present(self):
        """
        Check if summary is present and push to database.
        """
        print(" THERE is SUMMARY")
        formatted_result = {}
        for _, summary_response in self.summary.items():
            # Modified to use the new response wrapper structure
            summary_text = summary_response.data[0].content[0].text.value
            formatted_result[self.today_date] = summary_text
            
        self.push_results_to_db(formatted_result, "Summary")
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_summary_present] Successfully pushed summary to MongoDB")

    def chk_news(self):
        """
        Check if news exists in the database for all categories.
        """
        flag = []
        for category in self.get_news_src():
            if self.db.count_documents({f"{self.today_date}.{category}": {"$exists": True}}) > 0:
                flag.append(1)
            else:
                flag.append(0)
        return flag

    def chk_results(self):
        """
        Check if results exist in the database for today's date.
        """
        if self.db.count_documents({f"Result.{self.today_date}": {"$exists": True}}) > 0:
            print(f"Results are present {self.db.find({f'Result.{self.today_date}': {'$exists': True}})}")
            return True
        return False
    
    def chk_summary(self):
        """
        Check if summary exists in the database for today's date.
        """
        if self.db.count_documents({f"Summary.{self.today_date}": {"$exists": True}}) > 0:
            print(f"Summary is present {self.db.find({f'Summary.{self.today_date}': {'$exists': True}})}")
            return True
        return False

    def get_all_available_dates(self):
        """
        Returns a list of all unique dates available in the database
        Dates are expected to be in the format 'YYYY-MM-DD'
        """
        gemini_links_db = self.db
        date_pattern = r"\d{4}-\d{2}-\d{2}"  # Regex pattern for YYYY-MM-DD format

        # Aggregate pipeline to extract all field names that match the date pattern
        pipeline = [
            {"$project": {"documentFields": {"$objectToArray": "$$ROOT"}}},
            {"$unwind": "$documentFields"},
            {"$match": {"documentFields.k": {"$regex": date_pattern}}},
            {"$group": {"_id": None, "dates": {"$addToSet": "$documentFields.k"}}},
            {"$project": {"_id": 0, "dates": 1}}
        ]

        result = list(gemini_links_db.aggregate(pipeline))

        if result and 'dates' in result[0]:
            dates = result[0]['dates']
            # Sort dates chronologically
            dates.sort(reverse=True)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][get_all_available_dates] Found {len(dates)} dates in database")
            return dates
        else:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][get_all_available_dates] No dates found in database")
            return []

# if __name__ == "__main__":
#     client_api = GeminiAPI()
#     client_api.start_gemini_assistant()
#     # client_api.openai_api_request("This is a test prompt for Gemini API.")


