import requests
from bs4 import BeautifulSoup
# from openai_api import news_sources
from urllib.parse import urljoin
from typing import List, Set


def get_links_and_content_from_page(url: str) -> dict:
    response = requests.get(url, timeout=10) # added timeout for better performance
    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
    # print(response.text)
    links= extract_links_from_html(response.text, url)
    # print(links)
    content = {}
    for link in links:
        print(f"Extracting content from {link}")
        content[link] = extract_news_content(link)
    # print(content)
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
                return "Error: Could not find an article body"

        return [title, body_text]
    except requests.exceptions.RequestException as e:
       return f"Error: Could not fetch page: {e}"
    except Exception as e:
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
