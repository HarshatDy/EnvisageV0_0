import requests
from bs4 import BeautifulSoup
# from openai_api import news_sources
from urllib.parse import urljoin
from typing import List, Set, Dict, Any, Optional
import random
import time
try:
    from .logging_scripts import *
    from .web_scrapper_time_based import scrape_with_time_constraint
except ImportError:
    from logging_scripts import *
    from web_scrapper_time_based import scrape_with_time_constraint
from datetime import datetime, timedelta


log_file = f"web_scrapper_{datetime.today().strftime('%Y_%m_%d_%H_%M_%S')}_log.txt"
create_log_file(log_file)

# List of realistic user agents to rotate through
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
]

# Example proxy list - replace with your actual proxy service
PROXY_LIST = [
    # Format: "http://username:password@ip:port"
    # Add your proxy servers here
    # Examples:
    # "http://user1:pass1@192.168.1.1:8080",
    # "http://user2:pass2@192.168.1.2:8080",
]

def get_random_user_agent() -> str:
    """Return a random user agent from the list."""
    return random.choice(USER_AGENTS)

def get_random_proxy() -> Optional[Dict[str, str]]:
    """Return a random proxy configuration if available."""
    if not PROXY_LIST:
        return None
    proxy = random.choice(PROXY_LIST)
    return {"http": proxy, "https": proxy}

def make_request(url: str, retry_count: int = 3, delay_range: tuple = (1, 3)) -> requests.Response:
    """
    Makes an HTTP request with random user agent, delay and optional proxy rotation.
    Implements retries with exponential backoff.
    """
    headers = {"User-Agent": get_random_user_agent()}
    proxies = get_random_proxy()
    
    # Add random delay to avoid rate limits
    delay = random.uniform(*delay_range)
    time.sleep(delay)
    
    attempt = 0
    while attempt < retry_count:
        try:
            if proxies:
                append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Requesting {url} with proxy')
                response = requests.get(url, headers=headers, proxies=proxies, timeout=10)
            else:
                append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Requesting {url} without proxy')
                response = requests.get(url, headers=headers, timeout=10)
            
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            attempt += 1
            if attempt == retry_count:
                raise
            # Exponential backoff
            wait_time = delay * (2 ** attempt)
            append_to_log(log_file, f'[WEB_SCRAPPER][WAR][{datetime.today().strftime("%H:%M:%S")}] Request failed, retrying in {wait_time:.2f}s: {str(e)}')
            time.sleep(wait_time)
            # Rotate proxy on failure if available
            if PROXY_LIST:
                proxies = get_random_proxy()

def get_links_and_content_from_page(url: str) -> dict:
    try:
        response = make_request(url)
        links = extract_links_from_html(response.text, url)
        content = {}
        
        # Get current time to determine time constraints
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Set time constraints based on current time
        if 6 <= current_hour < 18:  # Between 6am and 6pm
            # Today from 6am to current time
            start_date = current_time.strftime("%Y-%m-%d")
            start_time = "06:00"
            end_date = current_time.strftime("%Y-%m-%d")
            end_time = current_time.strftime("%H:%M")
            time_period = "morning to now"
        else:  # Between 6pm and 6am
            if current_hour >= 18:  # Evening (6pm to midnight)
                start_date = current_time.strftime("%Y-%m-%d")  # Today
                start_time = "18:00"
                end_date = (current_time + timedelta(days=1)).strftime("%Y-%m-%d")  # Tomorrow
                end_time = "06:00"
                time_period = "evening to early morning"
            else:  # Early morning (midnight to 6am)
                start_date = (current_time - timedelta(days=1)).strftime("%Y-%m-%d")  # Yesterday
                start_time = "18:00"
                end_date = current_time.strftime("%Y-%m-%d")  # Today
                end_time = "06:00"
                time_period = "evening to now"
        
        append_to_log(log_file, f'[WEB_SCRAPPER][INF][{current_time.strftime("%H:%M:%S")}] Using time constraint: {time_period} ({start_date} {start_time} to {end_date} {end_time})')
        print(f"Using time constraint: {time_period} ({start_date} {start_time} to {end_date} {end_time})")
        
        for link in links:
            append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Checking time constraints for {link}')
            print(f"Checking time constraints for {link}")
            
            # Check if article meets time constraints
            time_result = scrape_with_time_constraint(
                link,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=end_time
            )
            
            print(f"Time constraint check result: {time_result}")
            append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Time constraint check result: {time_result}')
            
            # Only process articles that meet the time constraint
            if time_result["valid"]:
                append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Getting content from {link}')
                print(f"Extracting content from {link}")
                article_content = extract_news_content(link)
                
                # Check if content is valid and has enough words
                if isinstance(article_content, list) and len(article_content) == 2:
                    # Check if body text has at least 20 words
                    if article_content[1] and len(article_content[1].split()) >= 20:
                        content[link] = article_content
                    else:
                        message = "Missing Content: Less than 20 words"
                        append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Skipping {link}: {message}')
                        print(f"Skipping {link}: {message}")
                else:
                    message = "Missing Content"
                    append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Skipping {link}: {message}')
                    print(f"Skipping {link}: {message}")
            else:
                reason = time_result.get("reason", "Did not meet time constraints")
                append_to_log(log_file, f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Skipping {link}: {reason}')
                print(f"Skipping {link}: {reason}")
        
        if content:
            append_to_log(log_file, f'[WEB_SCRAPPER][SUC][{datetime.today().strftime("%H:%M:%S")}] Extracted successfully from {url}')
            print(f"Extracted successfully from {url}")
        else:
            append_to_log(log_file, f'[WEB_SCRAPPER][ERR][{datetime.today().strftime("%H:%M:%S")}] Failed to extract from {url}')
            print(f"Failed to extract from {url}")
        return content
    except Exception as e:
        append_to_log(log_file, f'[WEB_SCRAPPER][ERR][{datetime.today().strftime("%H:%M:%S")}] Error processing {url}: {str(e)}')
        print(f"Error processing {url}: {str(e)}")
        return {}


def extract_news_content(page: str) -> List[str]:
    """
    Extracts article title and body from a news URL using BeautifulSoup.
    Works best on article pages. Returns title, body or an error message.
    """
    try:       
        response = make_request(page)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Attempt to find the title
        title = soup.find('h1') or soup.find('h2')
        if title:
          title = title.text.strip()
        else:
           append_to_log(log_file,f'[WEB_SCRAPPER][ERR][{datetime.today().strftime("%H:%M:%S")}] Could not find article title')
           return "Error: Could not find an article title"

        # Attempt to find the main article body
        article_body = soup.find('div', class_=['article-content', 'article-body', 'body-content', 'article-text', 'content']) # Common article body classes, can expand as needed
        if article_body:
           paragraphs = article_body.find_all('p')
           body_text = "\n".join([p.text.strip() for p in paragraphs])
        else:
            # If a specific article-body div isn't found, fallback to all paragraphs in the main content (risky!)
            main_content = (soup.find('main') or 
                            soup.find('div', id='main') or 
                            soup.find('div', class_="container")) # Common main content areas, you can expand this too
            if main_content:
                paragraphs = main_content.find_all('p')
                body_text = "\n".join([p.text.strip() for p in paragraphs])
            else:
                append_to_log(log_file,f'[WEB_SCRAPPER][ERR][{datetime.today().strftime("%H:%M:%S")}] Could not find article body ')
                return "Error: Could not find an article body"

        return [title, body_text]
    except requests.exceptions.RequestException as e:
       append_to_log(log_file,f'[WEB_SCRAPPER][ERR][{datetime.today().strftime("%H:%M:%S")}] Could not fetch page: {e}')
       return f"Error: Could not fetch page: {e}"
    except Exception as e:
        append_to_log(log_file,f'[WEB_SCRAPPER][ERR][{datetime.today().strftime("%H:%M:%S")}] An unexpected error occurred: {e}')
        return f"Error: An unexpected error occurred: {e}"


def extract_links_from_html(html_content: str, base_url: str) -> List[str]:
    """Extract and normalize links from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    links: Set[str] = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Normalize URL
        full_url = urljoin(base_url, href)
        if full_url.startswith('http'):
            links.add(full_url)
    return links
