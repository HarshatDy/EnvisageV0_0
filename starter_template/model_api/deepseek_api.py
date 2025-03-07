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


class DeepseekAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        
        self.today = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"deepseek_{self.today}_log.txt"
        try:
            create_log_file(self.log_file)
        except NameError:
            print(f"Warning: create_log_file function not available. Log file {self.log_file} not created.")
        
        self.thread_lock = Lock()
        self.thread_result = {}
        self.summary = {}
        self.db = db['deepseek_api']
        self.today_date = datetime.today().strftime('%Y-%m-%d')
        self.MAX_RETRY = 5
        self.MAX_BATCHES = 5
        
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
        """Generate content using Deepseek API"""
        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are an expert assistant that categorizes news content."},
                    {"role": "user", "content": txt}
                ],
                temperature=0.2,
                max_tokens=1024
            )
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Log processing time
            append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][generate] Processing time: {processing_time:.2f} seconds")
            
            # This is a placeholder for the response - OpenAI API returns different structure than Gemini
            response_text = response.choices[0].message.content
            
            # Create a response object similar to what's expected elsewhere
            class ResponseWrapper:
                def __init__(self, text, candidates=None):
                    self.text = text
                    self.candidates = candidates or [type('obj', (object,), {'finish_reason': 'stop'})]
            
            return ResponseWrapper(response_text)
            
        except Exception as e:
            append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][generate] Error generating content: {str(e)}")
            raise
    
    def start_deepseek_assistant(self):
        """
        Gets news from sources, processes them in threads and stores results in MongoDB.
        """
        deepseek_links_db = self.db
        
        append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Starting Deepseek Assistant")
        news_sources = self.get_news()
        links = {}
        lock = self.thread_lock
        result_grded_news = {}
        
        def process_lnks(category, sources):
            nonlocal links    
            if category not in links:
                links[category] = {}
                
            for source in sources:
                append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Getting news from {source}")
                try:
                    links[category][source] = get_links_and_content_from_page(source)
                    append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Successfully extracted news from {source}")
                    append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] *****************************************************")
                except Exception as e:
                    append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] ************************ERROR************************")
                    append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Failed to extract news from {source}: {e}")
                    append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] *****************************************************")
                    
            append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Before processing category: {links[category]} and length {len(str(links[category]))} and for category {category}")
            append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Thread ID for {category}: {thread.ident}")
            
            if category not in result_grded_news:
                result_grded_news[category] = []
                
            with lock:
                append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Thread {thread.ident} acquired lock for {category}")
                result_grded_news[category] = self.grd_nws(links[category], category)
                
            append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] After processing category: {result_grded_news[category]} and length {len(result_grded_news[category]) if result_grded_news[category] else 0} and for category {category}")
            
            with lock:
                try:
                    deepseek_links_db.insert_one({self.today_date: {category: result_grded_news[category]}})
                    append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Successfully inserted data for {category} into MongoDB")
                except Exception as e:
                    append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Failed to insert data into MongoDB: {e}")
                    print(f"Failed to insert data into MongoDB: {e}")
                    
        threads = []
        for category, sources in news_sources.items():
            thread = Thread(target=process_lnks, args=(category, sources))
            threads.append(thread)
            thread.start()
            append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] Starting thread for {category} with thread ID: {thread.ident}")
            
        for thread in threads:
            thread.join()
            
        append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][start_deepseek_assistant] News retrieval complete")
        return None

    def grd_nws(self, links, category):
        news = links
        summary = self.summary
        result_links = {}
        categories = self.get_categories()
        
        if news and summary:
            return None
        elif news:
            append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] News is present for category {category}")
            
            for top_url in list(links.keys()):
                step = max(1, int(len(list(news[top_url].items()))/self.MAX_BATCHES))
                link_items = [list(news[top_url].items())[j:j+step] for j in range(0, len(list(news[top_url].items())), step)]
                
                append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing {len(link_items)} batches for {category}")
                
                for link_item in link_items:
                    # Log the size of link_item in bytes and KB
                    try:
                        link_item_str = str(link_item)
                        link_item_size_bytes = len(link_item_str)
                        link_item_size_kb = link_item_size_bytes / 1024
                        append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing batch with size: {link_item_size_bytes} bytes ({link_item_size_kb:.2f} KB)")
                    except Exception as e:
                        append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to calculate batch size: {str(e)}")
                    
                    # Process the batch with retry logic and batch splitting
                    self._process_batch_with_retry(link_item, result_links, categories, top_url, self.MAX_RETRY)
                
            # Remove empty categories
            result_links = {k: v for k, v in result_links.items() if v}
            append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Final categorized news: {result_links}")
            
        return result_links

    def _process_batch_with_retry(self, link_item, result_links, categories, top_url, retries_remaining):
        """Helper method to process a batch with retry logic and batch splitting."""
        if retries_remaining <= 0:
            append_to_log(self.log_file, f"[DEEPSEEK][CRITICAL][{datetime.today().strftime('%H:%M:%S')}][grd_nws] CRITICAL ERROR: Could not process the data after all retry attempts")
            return
        
        try:
            # Log the size of link_item after converting to string
            try:
                link_item_str = str(link_item)
                link_item_size = len(link_item_str)
                append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing batch of size {link_item_size} bytes ({link_item_size/1024:.2f} KB)")
            except Exception as e:
                append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to log link_item size: {str(e)}")
            
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

            Only return the python dict and nothing else, avoid markdown formatting.
            """
            
            response = self.generate(prompt)
            append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Received grading response")
            # Log the raw response text for debugging
            try:
                append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Raw response text: {response.text}")
            except Exception as log_error:
                append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to log response text: {str(log_error)}")
            # Parsing response - DeepSeek might need different handling
            response_text = response.text
            # Remove markdown formatting if present
            if "```python" in response_text:
                response_text = response_text.split("```python")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            try:
                index_mapping = eval(response_text)
                append_to_log(self.log_file, f"[DEEPSEEK][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Successfully parsed index mapping")
                
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
                append_to_log(self.log_file, f"[DEEPSEEK][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to parse response: {str(parsing_error)}")
                raise parsing_error  # Re-raise to trigger the split and retry
                        
        except Exception as e:
            append_to_log(self.log_file, f"[DEEPSEEK][WARN][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Error processing batch: {str(e)}. Retries remaining: {retries_remaining-1}")
            
            # If batch processing failed, split the batch into smaller pieces
            if len(link_item) > 1:
                mid = len(link_item) // 2
                append_to_log(self.log_file, f"[DEEPSEEK][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Splitting batch of size {len(link_item)} into two smaller batches")
                
                # Process first half
                self._process_batch_with_retry(link_item[:mid], result_links, categories, top_url, retries_remaining-1)
                # Process second half
                self._process_batch_with_retry(link_item[mid:], result_links, categories, top_url, retries_remaining-1)
            else:
                # If we're already down to a single item and still failing, try one more time with reduced retries
                time.sleep(2)  # Longer pause before retrying a single item
                self._process_batch_with_retry(link_item, result_links, categories, top_url, retries_remaining-1)


if __name__ == "__main__":
    client_api = DeepseekAPI()
    client_api.start_deepseek_assistant()