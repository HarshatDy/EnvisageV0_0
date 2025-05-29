import os
import requests
import json
import time
from datetime import datetime, timedelta
import argparse
from dotenv import load_dotenv
import urllib.parse
from bs4 import BeautifulSoup
import random
import re
import google.generativeai as google_genai
from google import genai
import socket
import ssl
import http.client
from fake_useragent import UserAgent
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import threading

# Handle imports for both Django and standalone execution
try:
    # Try relative imports (for Django)
    from .mongo import db
    from .logging_scripts import *
except ImportError:
    try:
        # Try absolute imports (for standalone script)
        from mongo import db
        from logging_scripts import *
    except ImportError:
        print("Warning: Could not import some modules. Some functionality may be limited.")
        # Define fallback or dummy functions/variables if needed
        db = {}

class ThumbnailScraper:
    def __init__(self):
        """Initialize the thumbnail scraper with log file and database connection."""
        # Setup logging
        self.today_now = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        
        # Remove log file handling and just print logs to console
        
        # Load environment variables
        load_dotenv()
        print(os.getenv('GEMINI_API_KEY'), " GEMINI_API_KEY")
        # exit(0)
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.client = genai.Client(api_key=self.api_key)
            
        # Connect to database
        self.web_db = db['envisage_web']
        
        # Get the current date with time constraint
        # self.today_date = "2025-04-06_18:00"
        self.today_date = self._get_date_with_time_constraint()
        
        # Set up image sources and headers
        self.image_sources = [
            'unsplash.com',
            'pexels.com',
            'pixabay.com',
            'flickr.com',
            'shutterstock.com'
        ]
        
        # Threading configuration
        self.max_workers = min(10, os.cpu_count() * 2)  # Limit to avoid being blocked
        self.thread_lock = threading.Lock()  # Lock for thread-safe operations
        self.active_threads = 0
        self.completed_searches = 0
        self.completed_downloads = 0
        
        # Initialize approach statistics tracking
        self.approach_stats = {
            "approach_1": {"success": 0, "failure": 0},
            "approach_2": {"success": 0, "failure": 0},
            "approach_3": {"success": 0, "failure": 0},
            "approach_4": {"success": 0, "failure": 0},
            "total_requests": 0,
            "total_success": 0,
            "total_failure": 0
        }
        
        # Enhanced and expanded user agents list to better mimic real browsers
        try:
            # Use fake_useragent to generate realistic user agents
            ua = UserAgent()
            self.user_agents = [
                ua.chrome,
                ua.firefox,
                ua.edge,
                ua.safari,
                ua.random,
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            ]
        except Exception as e:
            self.log_msg(f"Failed to initialize fake_useragent: {str(e)}", "WARN")
            # Default to basic list if fake_useragent fails
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
            ]
        
        # Public proxy services - update these with actual working proxies for production
        self.proxy_list = [
            # Free proxy example format: "http://ip:port"
            "http://185.199.229.156:7492",
            "http://185.199.228.220:7300",
            "http://185.199.231.45:8382",
            "http://188.74.210.207:6286",
            "http://188.74.183.10:8279",
            "http://91.188.246.88:8899",
        ]
        
        # Headers variations for different browsers
        self.headers_variations = [
            # Chrome on Windows
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
                "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
            # Firefox on Mac
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:95.0) Gecko/20100101 Firefox/95.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
            },
            # Safari on iPhone
            {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            # Edge on Windows
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="96", "Microsoft Edge";v="96"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        ]
        
        # Initialize a random IP rotation counter
        self.ip_rotation_counter = 0
        
        self.log_msg(f"Initialized with date constraint: {self.today_date}")

    def log_msg(self, message, level="INF"):
        """Print a log message to the console."""
        timestamp = datetime.today().strftime('%H:%M:%S')
        log_message = f"[WEB_SCRAPER][{level}][{timestamp}] {message}"
        print(log_message)
    
    def get_random_user_agent(self):
        """Return a random user agent from the list."""
        return random.choice(self.user_agents)

    def get_random_proxy(self):
        """
        Returns a random proxy from the proxy list with rotation.
        
        Returns:
            dict: Proxy configuration dict or None if no proxies available
        """
        if not self.proxy_list:
            return None
            
        # Rotate through proxies sequentially to avoid using the same one repeatedly
        self.ip_rotation_counter = (self.ip_rotation_counter + 1) % len(self.proxy_list)
        proxy = self.proxy_list[self.ip_rotation_counter]
        
        self.log_msg(f"Using proxy #{self.ip_rotation_counter}: {proxy}", "DBG")
        return {"http": proxy, "https": proxy}

    def get_browser_like_headers(self):
        """
        Generate browser-like headers with random but consistent values.
        
        Returns:
            dict: Dictionary of HTTP headers
        """
        # Select a random header variation
        headers = random.choice(self.headers_variations).copy()
        
        # Update the User-Agent separately to ensure variety
        headers["User-Agent"] = self.get_random_user_agent()
        
        # Add random viewport sizes like real browsers
        viewports = [
            "1920x1080", "1366x768", "1536x864", "1440x900", 
            "1280x720", "1600x900", "1024x768", "2560x1440"
        ]
        viewport = random.choice(viewports)
        width, height = map(int, viewport.split('x'))
        
        # Set random referrers that make sense for image search
        referrers = [
            "https://www.google.com/search?q=free+images",
            "https://duckduckgo.com/?q=royalty+free+images",
            "https://www.bing.com/images/search?q=stock+photos",
            "https://www.pinterest.com/search/pins/?q=images",
            f"https://www.google.com/search?q={urllib.parse.quote_plus(random.choice(['stock photos', 'free images', 'unsplash images', 'pexels photos']))}",
        ]
        headers["Referer"] = random.choice(referrers)
        
        # Add viewport and other browser-like details
        headers["Viewport-Width"] = str(width)
        headers["Viewport-Height"] = str(height)
        headers["Device-Memory"] = str(random.choice([4, 8, 16]))
        headers["DPR"] = str(random.choice([1, 2, 2.5]))
        
        return headers

    def make_request(self, url, retry_count=4, delay_range=(2, 5)):
        """
        Makes an HTTP request with advanced techniques to avoid bot detection.
        
        Args:
            url (str): URL to request
            retry_count (int): Number of retry attempts
            delay_range (tuple): Min and max delay between requests
            
        Returns:
            requests.Response: Response object or None if all attempts fail
        """
        # Add random delay before request
        delay = random.uniform(*delay_range)
        time.sleep(delay)
        
        # Increment total requests counter
        self.approach_stats["total_requests"] += 1
        
        # Try different approaches across retry attempts
        for attempt in range(retry_count):
            # Create a fresh session for each attempt
            session = requests.Session()
            
            # Configure retry strategy with backoff
            retry_strategy = Retry(
                total=2,  # number of retries
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "HEAD"],
                backoff_factor=1
            )
            
            # Mount the adapter to both http and https
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Get fresh headers and proxy for this attempt
            headers = self.get_browser_like_headers()
            proxies = self.get_random_proxy() if attempt > 0 else None  # Try without proxy first
            
            approach_key = f"approach_{attempt+1}"
            self.log_msg(f"Attempt #{attempt+1}/{retry_count} for {url}", "INF")
            
            try:
                # Different approaches based on the attempt number
                if attempt == 0:
                    # First attempt: Direct request with standard browser-like behavior
                    self.log_msg(f"Using standard browser approach for {url}", "DBG")
                    
                    # Visit a related site first to establish cookies and browsing history
                    if "unsplash" in url:
                        session.get("https://unsplash.com/", headers=headers, timeout=10)
                    elif "pexels" in url:
                        session.get("https://www.pexels.com/", headers=headers, timeout=10)
                    
                    time.sleep(random.uniform(1, 2))
                    
                    # Make the actual request with the same session
                    response = session.get(
                        url,
                        headers=headers,
                        proxies=proxies,
                        timeout=20,
                        allow_redirects=True
                    )
                    
                elif attempt == 1:
                    # Second attempt: Try with a proxy and simplified URL
                    self.log_msg(f"Using proxy approach for {url}", "DBG")
                    
                    # Simplify URL by removing query parameters
                    simple_url = url.split('?')[0]
                    
                    # Different header set with a proxy
                    response = session.get(
                        simple_url,
                        headers=headers,
                        proxies=proxies,
                        timeout=20,
                        allow_redirects=True
                    )
                    
                elif attempt == 2:
                    # Third attempt: Try with a low-level urllib approach
                    self.log_msg(f"Using low-level urllib approach for {url}", "DBG")
                    
                    # Parse the URL
                    parsed_url = urllib.parse.urlparse(url)
                    path = parsed_url.path
                    if parsed_url.query:
                        path += '?' + parsed_url.query
                    
                    # Custom low-level HTTP request to bypass some bot detection
                    connection = http.client.HTTPSConnection(parsed_url.netloc, timeout=15)
                    
                    # Add headers one by one
                    connection.putrequest("GET", path)
                    for header, value in headers.items():
                        connection.putheader(header, value)
                    connection.endheaders()
                    
                    # Get response
                    raw_response = connection.getresponse()
                    
                    # Convert to requests.Response
                    response = requests.Response()
                    response.status_code = raw_response.status
                    response._content = raw_response.read()
                    response.headers = dict(raw_response.getheaders())
                    response.url = url
                    connection.close()
                    
                else:
                    # Final attempt: Try a completely different approach
                    self.log_msg(f"Using minimal Googlebot approach for {url}", "DBG")
                    
                    # Pretend to be Googlebot
                    googlebot_headers = {
                        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Connection": "keep-alive"
                    }
                    
                    response = session.get(
                        url,
                        headers=googlebot_headers,
                        proxies=proxies,
                        timeout=20,
                        allow_redirects=True
                    )
                
                # Check response status
                if response.status_code == 200:
                    self.log_msg(f"Request successful with approach #{attempt+1}", "INF")
                    # Update success stats
                    self.approach_stats[approach_key]["success"] += 1
                    self.approach_stats["total_success"] += 1
                    # Print stats periodically
                    if self.approach_stats["total_requests"] % 10 == 0:
                        self.print_approach_stats()
                    # Add a small delay after success to mimic browser behavior
                    time.sleep(random.uniform(0.5, 1.0))
                    return response
                else:
                    self.log_msg(f"Request returned status code {response.status_code} with approach #{attempt+1}", "WARN")
                    # Update failure stats
                    self.approach_stats[approach_key]["failure"] += 1
                    
                    # Check if we're hitting CAPTCHA or bot detection
                    if response.status_code == 403:
                        # Look for signs of bot detection in response
                        response_text = response.text.lower()
                        if any(term in response_text for term in ["captcha", "bot detection", "security check", "automated access", "too many requests"]):
                            self.log_msg("Bot detection in place, modifying approach", "WARN")
                            # Increase delay more aggressively for next attempt
                            delay_range = (delay_range[1], delay_range[1] * 2)
                    
                    # Return the last response even if not 200 for debugging
                    if attempt == retry_count - 1:
                        self.approach_stats["total_failure"] += 1
                        # Print stats on failure
                        if self.approach_stats["total_requests"] % 5 == 0:
                            self.print_approach_stats()
                        return response
                        
            except (requests.RequestException, http.client.HTTPException, socket.error, ssl.SSLError) as e:
                self.log_msg(f"Request error with approach #{attempt+1}: {str(e)}", "WARN")
                # Update failure stats
                self.approach_stats[approach_key]["failure"] += 1
            
            # Wait before next attempt with exponential backoff
            backoff_factor = (2 ** attempt)
            wait_time = delay * backoff_factor * (0.75 + random.random() * 0.5)  # Add jitter
            self.log_msg(f"Waiting {wait_time:.2f}s before attempt #{attempt+2}", "WARN")
            time.sleep(wait_time)
            
        self.log_msg(f"All {retry_count} approaches failed for URL: {url}", "ERR")
        self.approach_stats["total_failure"] += 1
        # Print stats on complete failure
        self.print_approach_stats()
        return None

    def print_approach_stats(self):
        """
        Print a table showing approach success/failure statistics.
        """
        self.log_msg("--- APPROACH STATISTICS TABLE ---", "INF")
        
        # Calculate success rates
        success_rates = {}
        for approach in ["approach_1", "approach_2", "approach_3", "approach_4"]:
            total = self.approach_stats[approach]["success"] + self.approach_stats[approach]["failure"]
            if total > 0:
                rate = (self.approach_stats[approach]["success"] / total) * 100
                success_rates[approach] = f"{rate:.1f}%"
            else:
                success_rates[approach] = "N/A"
        
        # Calculate overall success rate
        total_attempts = self.approach_stats["total_success"] + self.approach_stats["total_failure"]
        overall_rate = (self.approach_stats["total_success"] / total_attempts) * 100 if total_attempts > 0 else 0
        
        # Print header
        print("+---------------+----------+---------+---------------+")
        print("|   Approach    | Success  | Failure | Success Rate  |")
        print("+---------------+----------+---------+---------------+")
        
        # Print each approach
        for i, approach in enumerate(["approach_1", "approach_2", "approach_3", "approach_4"]):
            print(f"| Approach #{i+1}    | {self.approach_stats[approach]['success']:<8} | {self.approach_stats[approach]['failure']:<7} | {success_rates[approach]:<13} |")
        
        # Print totals
        print("+---------------+----------+---------+---------------+")
        print(f"| TOTAL         | {self.approach_stats['total_success']:<8} | {self.approach_stats['total_failure']:<7} | {overall_rate:.1f}%         |")
        print("+---------------+----------+---------+---------------+")
        print(f"| Total Requests: {self.approach_stats['total_requests']} |")
        print("+-------------------------------+")
        
        # Recommend best approach based on success rate
        best_approach = max(
            ["approach_1", "approach_2", "approach_3", "approach_4"],
            key=lambda x: self.approach_stats[x]["success"] if 
                (self.approach_stats[x]["success"] + self.approach_stats[x]["failure"]) > 0 
                else -1
        )
        best_idx = int(best_approach.split("_")[1])
        print(f"Best performing approach: #{best_idx} ({success_rates[best_approach]} success rate)")
        print()

    def _get_date_with_time_constraint(self):
        """
        Determine the current time constraint and create a date string with it.
        
        Returns:
            str: Date string with time constraint in format 'YYYY-MM-DD_HH:00'
                Example: '2023-06-15_06:00' or '2023-06-15_18:00'
        """
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Set time constraints based on current time
        if 6 <= current_hour < 18:  # Between 6am and 6pm
            # Morning to evening constraint - use 18:00 (6pm) of current day
            constraint_date = current_time.strftime('%Y-%m-%d')
            constraint_time = "18:00"
        else:  # Between 6pm and 6am
            if current_hour >= 18:  # Evening (6pm to midnight)
                # Evening to next morning constraint - use 06:00 (6am) of next day
                next_day = current_time + timedelta(days=1)
                constraint_date = next_day.strftime('%Y-%m-%d')
                constraint_time = "06:00"
            else:  # Early morning (midnight to 6am)
                # Previous evening to morning constraint - use 06:00 (6am) of current day
                constraint_date = current_time.strftime('%Y-%m-%d')
                constraint_time = "06:00"
        
        date_with_constraint = f"{constraint_date}_{constraint_time}"
        self.log_msg(f"Date with time constraint: {date_with_constraint}")
        
        return date_with_constraint
    
    def fetch_categories(self, date=None):
        """
        Fetch news categories from the database for a given date.
        
        Args:
            date (str, optional): The date with time constraint to fetch.
                                 If None, uses the current date with time constraint.
        
        Returns:
            list: List of categories with their summaries
        """
        if date is None:
            date = self.today_date
            
        self.log_msg(f"Fetching categories for date: {date}", "DBG")
        print(f"DEBUG: Fetching categories for date: {date}")
        
        # Query the database for the web data
        query = {f"envisage_web.{date}": {"$exists": True}}
        result = self.web_db.find_one(query)
        
        if not result:
            self.log_msg(f"No web data found for date: {date}", "WARN")
            print(f"DEBUG: No web data found for date: {date}")
            return []
            
        try:
            # Extract the web data for the specified date
            web_data = result["envisage_web"][date]
            print(f"DEBUG: Found web data structure with keys: {list(web_data.keys())}")
            
            # Extract categories from news items with summaries
            categories = []
            for news_item in web_data.get("newsItems", []):
                category = news_item.get("category")
                title = news_item.get("title")
                summary = news_item.get("summary", "")
                
                if category:
                    categories.append({
                        "category": category,
                        "title": title,
                        "id": news_item.get("id"),
                        "summary": summary
                    })
                    print(f"DEBUG: Found category {category} with title: {title}")
            
            self.log_msg(f"Found {len(categories)} categories", "INF")
            print(f"DEBUG: Retrieved {len(categories)} categories from database")
            return categories
            
        except Exception as e:
            self.log_msg(f"Error fetching categories: {str(e)}", "ERR")
            print(f"DEBUG ERROR: Error fetching categories: {str(e)}")
            import traceback
            print(f"DEBUG ERROR: {traceback.format_exc()}")
            return []
    
    def generate_image_search_terms(self, category, title, summary):
        """
        Generate relevant image search terms using Gemini API based on the news summary.
        
        Args:
            category (str): The news category
            title (str): The news title
            summary (str): The news summary text
            
        Returns:
            list: List of relevant image search terms
        """
        if not self.client:
            self.log_msg(f"Gemini API not available, using default search terms for {category}", "WARN")
            print(f"DEBUG: No Gemini API client available, using default search terms")
            return [title, category]
            
        try:
            self.log_msg(f"Generating image search terms for {category}", "INF")
            print(f"DEBUG: Generating search terms for category '{category}' with Gemini API")
            
            # Trim summary if it's too long
            summary_excerpt = summary[:1000] if len(summary) > 1000 else summary
            
            prompt = f"""
            Based on this news summary, provide 5 descriptive terms or phrases whose images would look good for the thumbnail of this article.
            Focus on concrete, visually distinctive concepts that would make for compelling thumbnail images.

            Category: {category}
            Title: {title}
            Summary excerpt: {summary_excerpt}

            Format your response as a JSON array of strings, containing only the search terms.
            For example: ["term1", "term2", "term3", "term4", "term5"]
            
            Do NOT include any explanation, commentary, or other text outside the JSON array.
            """
            
            # Log the request being sent
            print(f"DEBUG: Sending request to Gemini API with prompt length: {len(prompt)} characters")
            
            # Make the request to Gemini
            response = self.openai_api_request(prompt)
            
            response_text = response.text
            print(f"DEBUG: Received response from Gemini: {response_text}")
            
            # Clean up the response text to ensure it's valid JSON
            if "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                
            if response_text.startswith('json') or response_text.startswith('JSON'):
                response_text = response_text[4:].strip()
                
            try:
                # Parse JSON response
                search_terms = json.loads(response_text)
                if not isinstance(search_terms, list):
                    raise ValueError("Response is not a list")
                    
                print(f"DEBUG: Successfully parsed search terms: {search_terms}")
                self.log_msg(f"Generated terms for {category}: {search_terms}", "INF")
                
                # Add the category and title to ensure we have fallback search terms
                if title not in search_terms:
                    search_terms.append(title)
                if category not in search_terms:
                    search_terms.append(category)
                    
                return search_terms
                
            except json.JSONDecodeError as e:
                self.log_msg(f"Error parsing Gemini API response: {str(e)}", "ERR")
                print(f"DEBUG ERROR: JSON parsing error for response: {response_text}")
                print(f"DEBUG ERROR: {str(e)}")
                # Fall back to basic search terms
                return [title, category]
                
        except Exception as e:
            self.log_msg(f"Error generating search terms with Gemini: {str(e)}", "ERR")
            print(f"DEBUG ERROR: Gemini API error: {str(e)}")
            import traceback
            print(f"DEBUG ERROR: {traceback.format_exc()}")
            # Fall back to basic search terms
            return [title, category]

    def openai_api_request(self, prompt_text):
        """
        Makes an API request to Gemini model and returns response in an OpenAI-compatible format.
        
        Args:
            prompt_text (str): The prompt text to send to the Gemini API
                
        Returns:
            ResponseWrapper: Custom object containing response data with attributes:
                - text (str): The generated text response
                - data (list): List containing nested object structure similar to OpenAI response
        """
        self.log_msg(f"Making Gemini API request", "DBG")
        print(f"DEBUG: Making Gemini API request for image search terms")
        
        if not self.client:
            raise ValueError("Gemini client not initialized")
            
        try:
            # model_info = google_genai.get_model("models/gemini-2.0-flash-lite")
            # model = google_genai.GenerativeModel("models/gemini-2.0-flash-lite")
            # required_input_tokens = model.count_tokens(prompt_text)
            # print(f"DEBUG: Required tokens for prompt: {required_input_tokens}")
            
            # Fix: Use client.models.generate_content method instead of non-existent method
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[prompt_text])
            
            print(f"DEBUG: Gemini response received")
            print(f"DEBUG: Finish reason: {response.candidates[0].finish_reason}")
            
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
            
        except Exception as e:
            self.log_msg(f"Gemini API request failed: {str(e)}", "ERR")
            print(f"DEBUG ERROR: Gemini API request failed: {str(e)}")
            # Create a basic error response
            class ErrorResponse:
                def __init__(self, error_message):
                    self.text = f'["Error generating search terms"]'
                    self.data = [type('obj', (object,), {
                        'content': [type('obj', (object,), {
                            'text': type('obj', (object,), {'value': self.text})
                        })]
                    })]
                    
            return ErrorResponse(str(e))
    
    def _is_restricted_url(self, url):
        """
        Check if the URL contains restricted keywords indicating paid content or profile images.
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if URL contains restricted keywords, False otherwise
        """
        if not url:
            return True
            
        url_lower = url.lower()
        # Check for premium (paid) content or profile images
        return 'premium' in url_lower or 'profile' in url_lower

    def search_unsplash(self, query, n_images=3):
        """
        Search Unsplash for images matching the query.
        
        Args:
            query (str): The search term to look for on Unsplash
            n_images (int): Number of images to try to retrieve
            
        Returns:
            list: List of image URLs from Unsplash
        """
        self.log_msg(f"Searching Unsplash for: {query}", "INF")
        
        # Replace spaces with hyphens for Unsplash URL format
        query_formatted = query.replace(' ', '-')
        encoded_query = urllib.parse.quote(query_formatted)
        search_url = f"https://unsplash.com/s/photos/{encoded_query}"
        
        self.log_msg(f"Using Unsplash URL: {search_url}", "DBG")
        
        try:
            # Get the search results page
            response = self.make_request(search_url)
            if not response or response.status_code != 200:
                self.log_msg(f"Failed to get Unsplash search page for {query}", "ERR")
                return []
                
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find image elements - Unsplash usually has images in figure elements
            image_urls = []
            restricted_skipped = 0
            
            # Look for image elements with data-test attribute
            image_elements = soup.select("figure img[srcset]")
            
            for img in image_elements:
                if len(image_urls) >= n_images:
                    break
                    
                # Get the src or srcset attribute
                if img.get('src'):
                    img_url = img['src']
                elif img.get('srcset'):
                    # Extract the highest quality image from srcset
                    srcset = img['srcset']
                    urls = srcset.split(',')
                    if urls:
                        img_url = urls[0].strip().split(' ')[0]
                    else:
                        continue
                else:
                    continue
                    
                # Skip restricted images (premium/profile)
                if self._is_restricted_url(img_url):
                    self.log_msg(f"Skipping restricted image: {img_url}", "DBG")
                    restricted_skipped += 1
                    continue
                    
                # Ensure it's a valid Unsplash image
                if 'unsplash' in img_url and img_url not in image_urls:
                    # Fix URL if needed
                    img_url = self._fix_url(img_url)
                    if img_url:  # Make sure _fix_url didn't return None
                        image_urls.append(img_url)
                        self.log_msg(f"Found image: {img_url}", "DBG")
            
            # If we didn't find enough images with the above method, try alternate selectors
            if len(image_urls) < n_images:
                # Try another common pattern for Unsplash images
                alt_images = soup.select("div[data-test='search-photos-route'] img[src*='unsplash']")
                for img in alt_images:
                    if len(image_urls) >= n_images:
                        break
                        
                    if img.get('src'):
                        img_url = img['src']
                        
                        # Skip restricted images
                        if self._is_restricted_url(img_url):
                            self.log_msg(f"Skipping restricted image: {img_url}", "DBG")
                            restricted_skipped += 1
                            continue
                            
                        img_url = self._fix_url(img_url)
                        if img_url and img_url not in image_urls:
                            image_urls.append(img_url)
                            self.log_msg(f"Found additional image: {img_url}", "DBG")
            
            if restricted_skipped > 0:
                self.log_msg(f"Skipped {restricted_skipped} restricted images for query: {query}", "INF")
            self.log_msg(f"Found {len(image_urls)} usable images for query: {query}", "INF")
            return image_urls
            
        except Exception as e:
            self.log_msg(f"Error searching Unsplash: {str(e)}", "ERR")
            print(f"DEBUG ERROR: {str(e)}")
            import traceback
            print(f"DEBUG ERROR: {traceback.format_exc()}")
            return []

    def search_pexels(self, query, n_images=3):
        """
        Search Pexels for images matching the query.
        
        Args:
            query (str): The search term to look for on Pexels
            n_images (int): Number of images to try to retrieve
            
        Returns:
            list: List of image URLs from Pexels
        """
        self.log_msg(f"Searching Pexels for: {query}", "INF")
        
        # Replace spaces with plus signs for Pexels URL format
        query_formatted = query.replace(' ', '+')
        search_url = f"https://www.pexels.com/search/{query_formatted}/"
        
        self.log_msg(f"Using Pexels URL: {search_url}", "DBG")
        
        try:
            # Get the search results page
            response = self.make_request(search_url)
            if not response or response.status_code != 200:
                self.log_msg(f"Failed to get Pexels search page for {query}", "ERR")
                return []
                
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find image elements from Pexels
            image_urls = []
            
            # Pexels commonly uses article elements for photos with img inside
            articles = soup.find_all('article')
            for article in articles:
                if len(image_urls) >= n_images:
                    break
                
                # Find image elements within the article
                img = article.find('img')
                if img and img.get('src'):
                    img_url = img['src']
                    # Some Pexels images have data-large or srcset with higher quality
                    if img.get('data-large'):
                        img_url = img['data-large']
                    elif img.get('srcset'):
                        # Try to get the largest image from srcset
                        srcset = img['srcset']
                        urls = srcset.split(',')
                        if urls:
                            # Last entry is usually largest
                            largest = urls[-1].strip().split(' ')[0]
                            if largest:
                                img_url = largest
                    
                    # Fix URL if needed and add to results
                    img_url = self._fix_url(img_url)
                    if img_url and img_url not in image_urls:
                        image_urls.append(img_url)
                        self.log_msg(f"Found Pexels image: {img_url}", "DBG")
            
            # If we're still short on images, try alternate selectors
            if len(image_urls) < n_images:
                # Try alternative selector patterns for Pexels
                alt_images = soup.select("img.photo-item__img")
                for img in alt_images:
                    if len(image_urls) >= n_images:
                        break
                    
                    if img.get('src'):
                        img_url = self._fix_url(img['src'])
                        if img_url and img_url not in image_urls:
                            image_urls.append(img_url)
                            self.log_msg(f"Found additional Pexels image: {img_url}", "DBG")
            
            self.log_msg(f"Found {len(image_urls)} images from Pexels for query: {query}", "INF")
            return image_urls
            
        except Exception as e:
            self.log_msg(f"Error searching Pexels: {str(e)}", "ERR")
            print(f"DEBUG ERROR: {str(e)}")
            import traceback
            print(f"DEBUG ERROR: {traceback.format_exc()}")
            return []

    def _fix_url(self, url):
        """
        Fix URLs with missing scheme by adding https:
        
        Args:
            url (str): The URL to fix
            
        Returns:
            str: The fixed URL with proper scheme, or None if URL is restricted
        """
        # Skip restricted URLs
        if self._is_restricted_url(url):
            return None
            
        if url.startswith('//'):
            return f"https:{url}"
        elif not url.startswith(('http://', 'https://')):
            return f"https://{url}"
        return url
    
    def search_images(self, query, n_images=10):
        """
        Search for images on Unsplash and Pexels using the search terms.
        
        Args:
            query (str or list): The search query or list of search queries
            n_images (int): Number of images to search for
            
        Returns:
            list: List of image URLs
        """
        # Handle list of search terms
        if isinstance(query, list):
            # Try each search term until we find enough images
            image_urls = []
            for term in query:
                print(f"DEBUG: Searching for term: '{term}'")
                # Get images for each term, up to the required number
                needed_images = n_images - len(image_urls)
                if needed_images <= 0:
                    break
                    
                # Try Unsplash first
                term_images = self.search_unsplash(term, min(3, needed_images))
                
                # If Unsplash didn't yield enough results, try Pexels
                if len(term_images) < min(3, needed_images):
                    self.log_msg(f"Unsplash search yielded {len(term_images)} results, trying Pexels", "INF")
                    pexels_images = self.search_pexels(term, min(3, needed_images) - len(term_images))
                    term_images.extend(pexels_images)
                
                # Add each image with its associated term
                for img_url in term_images:
                    if len(image_urls) < n_images and img_url and not self._is_restricted_url(img_url):
                        image_urls.append({"term": term, "image_url": img_url})
                    
            self.log_msg(f"Found {len(image_urls)} usable images total for all terms", "INF")
            return image_urls
        else:
            # Handle single search term
            unsplash_urls = self.search_unsplash(query, n_images)
            
            # If Unsplash didn't yield enough results, try Pexels
            if len(unsplash_urls) < n_images:
                self.log_msg(f"Unsplash search yielded {len(unsplash_urls)} results, trying Pexels", "INF")
                pexels_urls = self.search_pexels(query, n_images - len(unsplash_urls))
                unsplash_urls.extend(pexels_urls)
                
            # Filter out any restricted URLs that might have slipped through
            filtered_urls = [url for url in unsplash_urls if url and not self._is_restricted_url(url)]
            
            return [{"term": query, "image_url": url} for url in filtered_urls]
    
    def download_image(self, image_data, folder_path, filename):
        """
        Download an image from Unsplash to a file.
        
        Args:
            image_data (dict): Dictionary containing image term and URL
            folder_path (str): Path to the folder to save the image
            filename (str): Name to give the downloaded image
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create the folder if it doesn't exist
            os.makedirs(folder_path, exist_ok=True)
            
            # Full path for the image
            image_path = os.path.join(folder_path, f"{filename}.jpg")
            
            term = image_data.get("term", "unknown")
            url = image_data.get("image_url")
            
            if not url:
                self.log_msg(f"No image URL found for term: {term}", "ERR")
                return False
                
            # Skip restricted images
            if self._is_restricted_url(url):
                self.log_msg(f"Skipping download of restricted image: {url}", "WARN")
                return False
            
            # Download the image from URL
            response = self.make_request(url)
            if response and response.status_code == 200:
                with open(image_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                self.log_msg(f"Downloaded image from Unsplash to {image_path}")
                return True
                
            return False
                
        except Exception as e:
            self.log_msg(f"Error downloading image: {str(e)}", "ERR")
            return False
    
    def process_categories(self, date=None, n_images=10):
        """
        Process all categories for a date - search and download images using threads.
        
        Args:
            date (str, optional): Date to process in 'YYYY-MM-DD_HH:00' format.
                                 If None, uses current date with time constraint.
            n_images (int): Number of images to download per category
            
        Returns:
            dict: Dictionary with results for each category
        """
        if date is None:
            date = self.today_date
            
        self.log_msg(f"Processing categories for date: {date} using up to {self.max_workers} threads", "INF")
        print(f"DEBUG: Processing categories for date: {date}")
        
        # Create base folder for this date
        date_folder = os.path.join('thumbnail_images', date.replace(':', ''))
        print(f"DEBUG: Images will be stored in folder: {date_folder}")
        
        # Fetch categories with summaries
        categories = self.fetch_categories(date)
        if not categories:
            self.log_msg(f"No categories found for date: {date}", "WARN")
            print(f"DEBUG: No categories found for date: {date}")
            return {}
            
        results = {}
        # Thread-safe results dictionary
        results_lock = threading.Lock()
        
        # Reset counters for this run
        self.active_threads = 0
        self.completed_searches = 0
        self.completed_downloads = 0
        total_categories = len(categories)
        
        def process_category(cat_info):
            """Worker function to process a single category in a thread"""
            try:
                category = cat_info['category']
                title = cat_info['title']
                item_id = cat_info['id']
                summary = cat_info.get('summary', '')
                
                thread_name = threading.current_thread().name
                self.log_msg(f"Thread {thread_name} processing category: {category}, ID: {item_id}", "INF")
                
                # Generate relevant search terms with Gemini API
                search_terms = self.generate_image_search_terms(category, title, summary)
                
                with self.thread_lock:
                    self.completed_searches += 1
                    self.log_msg(f"Progress: {self.completed_searches}/{total_categories} categories searched, {self.completed_downloads} images downloaded", "INF")
                
                # Search for images on Unsplash using the generated terms
                image_urls = self.search_images(search_terms, n_images)
                
                # Download images
                category_folder = os.path.join(date_folder, f"{item_id}_{category.replace(' ', '_')}")
                downloaded = 0
                
                for i, img_data in enumerate(image_urls):
                    filename = f"{category.lower().replace(' ', '_')}_{i+1}"
                    if self.download_image(img_data, category_folder, filename):
                        downloaded += 1
                        with self.thread_lock:
                            self.completed_downloads += 1
                
                # Store results in thread-safe manner
                with results_lock:
                    results[category] = {
                        "search_terms": search_terms,
                        "found": len(image_urls),
                        "downloaded": downloaded,
                        "folder": category_folder
                    }
                
                self.log_msg(f"Thread {thread_name} completed category {category} - found: {len(image_urls)}, downloaded: {downloaded}", "INF")
                
                # Print approach stats after each category completes
                if random.random() < 0.3:  # Only print stats occasionally to avoid log spam
                    self.print_approach_stats()
                
            except Exception as e:
                self.log_msg(f"Error processing category in thread: {str(e)}", "ERR")
                import traceback
                print(f"DEBUG ERROR: {traceback.format_exc()}")
        
        # Use ThreadPoolExecutor to manage threads
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all categories to the thread pool
            futures = [executor.submit(process_category, cat_info) for cat_info in categories]
            
            # Show progress while waiting for completion
            for i, future in enumerate(as_completed(futures)):
                # Just wait for completion and catch any exceptions
                try:
                    future.result()
                except Exception as exc:
                    self.log_msg(f"Thread generated an exception: {exc}", "ERR")
        
        # Final approach stats
        self.print_approach_stats()
        
        self.log_msg(f"All threads completed. Processed {len(categories)} categories, downloaded images to {date_folder}", "INF")
        print(f"DEBUG: All categories processed. Results: {json.dumps(results, indent=2)}")
        return results

    def print_thread_status(self):
        """Print the current thread status for debugging."""
        with self.thread_lock:
            self.log_msg(f"Thread status: Active={self.active_threads}, Completed searches={self.completed_searches}, Downloads={self.completed_downloads}", "INF")

def main():
    """Main function to run the script from command line."""
    parser = argparse.ArgumentParser(description='Scrape images for news categories')
    parser.add_argument('--date', help='Date to process in YYYY-MM-DD_HH:00 format')
    parser.add_argument('--images', type=int, default=10, help='Number of images to download per category')
    parser.add_argument('--debug', action='store_true', help='Enable detailed debug mode')
    parser.add_argument('--threads', type=int, help='Number of worker threads to use (default: CPU count * 2, max 10)')
    args = parser.parse_args()
    
    try:
        # Test internet connectivity first
        print("Testing internet connectivity...")
        try:
            test_response = requests.get("https://www.google.com", timeout=5)
            print(f"Internet connection test: {test_response.status_code}")
        except Exception as e:
            print(f"WARNING: Internet connectivity issue: {str(e)}")
        
        # Test Unsplash connectivity specifically
        print("Testing Unsplash connectivity...")
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            unsplash_response = requests.get("https://unsplash.com", headers=headers, timeout=10)
            print(f"Unsplash connection test: {unsplash_response.status_code}")
            if unsplash_response.status_code != 200:
                print("WARNING: Unsplash returned non-200 status code. May have rate limiting issues.")
        except Exception as e:
            print(f"WARNING: Unsplash connectivity issue: {str(e)}")
            
        scraper = ThumbnailScraper()
        
        # Set thread count if specified
        if args.threads:
            scraper.max_workers = min(args.threads, 20)  # Cap at 20 threads max
            print(f"Using {scraper.max_workers} worker threads")
        
        # Enable more verbose debugging if requested
        if args.debug:
            print("Verbose debugging enabled")
            # Create a sample search to test the scraper
            print("\n--- TESTING SEARCH FUNCTIONALITY ---")
            test_term = "nature landscape"
            print(f"Testing search for: '{test_term}'")
            test_images = scraper.search_unsplash(test_term, 2)
            print(f"Test search results: {len(test_images)} images found")
            if len(test_images) > 0:
                print(f"First image URL: {test_images[0]}")
            else:
                print("ERROR: Test search returned no images!")
                
            # Print Unsplash HTML response for debugging
            print("\n--- TESTING UNSPLASH RESPONSE STRUCTURE ---")
            try:
                test_url = "https://unsplash.com/s/photos/test"
                test_response = scraper.make_request(test_url)
                if test_response and test_response.status_code == 200:
                    soup = BeautifulSoup(test_response.text, 'html.parser')
                    # Look for key Unsplash elements
                    figures = soup.find_all('figure')
                    print(f"Found {len(figures)} figure elements")
                    
                    # Check for image elements
                    images = soup.find_all('img')
                    print(f"Found {len(images)} img elements")
                    
                    # Sample a few image URLs
                    unsplash_images = [img['src'] for img in images if img.get('src') and 'unsplash' in img.get('src', '')]
                    print(f"Found {len(unsplash_images)} Unsplash image sources")
                    if unsplash_images:
                        print(f"Sample image URL: {unsplash_images[0]}")
                    else:
                        print("ERROR: No Unsplash images found in test page!")
                        print("Unsplash may have changed their page structure or blocked scraping.")
                else:
                    print(f"Failed to get test page. Status code: {test_response.status_code if test_response else 'None'}")
            except Exception as e:
                print(f"Error during Unsplash structure test: {str(e)}")
        
        # Proceed with normal execution
        if args.date:
            print(f"Processing date: {args.date}")
            results = scraper.process_categories(args.date, args.images)
        else:
            print(f"Processing current date with time constraint: {scraper.today_date}")
            results = scraper.process_categories(None, args.images)
        
        # Print results
        for category, result in results.items():
            print(f"{category}: Found {result['found']} images, Downloaded {result['downloaded']} to {result['folder']}")
        
        print("Processing complete")
        
    except Exception as e:
        print(f"ERROR: Script execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nTROUBLESHOOTING TIPS:")
        print("1. Check internet connection")
        print("2. Verify Unsplash is accessible from your location")
        print("3. Try using a VPN if you're getting connection errors")
        print("4. Try running with --debug flag for more information")
        print("5. Check if Unsplash has changed their website structure")

if __name__ == "__main__":
    main()

