import requests
from bs4 import BeautifulSoup
# from openai_api import news_sources
from urllib.parse import urljoin
from typing import List, Set
try :
    from .logging_scripts import *
except ImportError:
    from logging_scripts import *
from datetime import datetime


log_file = f"web_scrapper_{datetime.today().strftime('%Y_%m_%d')}_log.txt"
create_log_file(log_file)


def get_links_and_content_from_page(url: str) -> dict:
    response = requests.get(url, timeout=10) # added timeout for better performance
    append_to_log(log_file,f'[WEB_SCRAPPER][ERR][{datetime.today().strftime('%H:%M:%S')}]{response.raise_for_status()}')
    response.raise_for_status()  # Raise HTTP  Error for bad responses (4xx or 5xx)
    # print(response.text)
    links= extract_links_from_html(response.text, url)
    # print(links)
    content = {}
    for link in links:
        append_to_log(log_file,f'[WEB_SCRAPPER][INF][{datetime.today().strftime("%H:%M:%S")}] Getting content from {link}')
        print(f"Extracting content from {link}")
        content[link] = extract_news_content(link)
    if content:
        append_to_log(log_file,f'[WEB_SCRAPPER][SUC][{datetime.today().strftime("%H:%M:%S")}] Extracted successfully from {url}')
        print(f"Extracted successfully from {url}")
    else:
        append_to_log(log_file,f'[WEB_SCRAPPER][ERR][{datetime.today().strftime("%H:%M:%S")}] Failed to extract from {url}')
        print(f"Failed to extract from {url}")
    return content


def extract_news_content(page: requests.get) -> List[str]:
    """
    Extracts article title and body from a news URL using BeautifulSoup.
    Works best on article pages. Returns title, body or an error message.
    """
    try:       
        response = requests.get(page, timeout=10) # added timeout for better performance
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
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


# if __name__ == '__main__':
#    for url in news_sources["Climate Technology"]:
#        print(f"Extracting content from {url}")
#        list = get_links_from_page(url)
#        print(list)
    #    print(f"Title: {title}\nBody: {body}\n")
#    news_url = input("Enter news article URL: ")
#    title, body = extract_news_content(news_url)
#    if isinstance(title, str) and title.startswith("Error"):
#       print(title)
#    else:
#      print("Article Title:", title)
#      print("\nArticle Body:\n", body)
