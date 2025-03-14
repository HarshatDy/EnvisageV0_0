import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from typing import Dict, Any, Tuple, Optional, Union
import dateutil.parser

def scrape_with_time_constraint(
    url: str, 
    start_date: str = None, 
    start_time: str = None,
    end_date: str = None,
    end_time: str = None,
    days_threshold: int = None, 
    headers: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Checks if a news article was published within the specified time constraint.
    
    Args:
        url (str): The URL of the news article to check
        start_date (str, optional): Start date in YYYY-MM-DD format
        start_time (str, optional): Start time in HH:MM format (24-hour)
        end_date (str, optional): End date in YYYY-MM-DD format
        end_time (str, optional): End time in HH:MM format (24-hour)
        days_threshold (int, optional): Legacy parameter - maximum number of days old the article can be
        headers (Dict[str, str], optional): Custom headers for the request
        
    Returns:
        Dict[str, Any]: Dictionary with validity status and timestamp
    """
    
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    try:
        # Fetch the page
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract publication date
        pub_date = extract_publication_date(soup, url)
        
        if not pub_date:
            print(f"Could not extract publication date from {url}")
            return {"valid": False, "timestamp": None, "url": url}
        
        # Calculate time constraints
        current_date = datetime.now().replace(tzinfo=None)  # Ensure current_date is naive
        
        # If specific start date/time is provided
        start_constraint = None
        if start_date:
            start_components = start_date.split('-')
            if len(start_components) == 3:
                year, month, day = map(int, start_components)
                if start_time:
                    try:
                        hour, minute = map(int, start_time.split(':'))
                        start_constraint = datetime(year, month, day, hour, minute).replace(tzinfo=None)
                    except (ValueError, IndexError):
                        start_constraint = datetime(year, month, day).replace(tzinfo=None)
                else:
                    start_constraint = datetime(year, month, day).replace(tzinfo=None)
        
        # If specific end date/time is provided
        end_constraint = None
        if end_date:
            end_components = end_date.split('-')
            if len(end_components) == 3:
                year, month, day = map(int, end_components)
                if end_time:
                    try:
                        hour, minute = map(int, end_time.split(':'))
                        end_constraint = datetime(year, month, day, hour, minute).replace(tzinfo=None)
                    except (ValueError, IndexError):
                        end_constraint = datetime(year, month, day, 23, 59, 59).replace(tzinfo=None)
                else:
                    end_constraint = datetime(year, month, day, 23, 59, 59).replace(tzinfo=None)
        
        # Determine validity based on time constraints
        valid = True
        reason = None
        
        # If days_threshold is provided but no specific dates
        if days_threshold is not None and not start_constraint and not end_constraint:
            time_limit = current_date - timedelta(days=days_threshold)
            pub_date, time_limit = ensure_consistent_timezone(pub_date, time_limit)
            if pub_date < time_limit:
                valid = False
                reason = f"Article too old. Published on {pub_date.strftime('%Y-%m-%d %H:%M')}, threshold is {time_limit.strftime('%Y-%m-%d %H:%M')}"
        else:
            # Check if publication date is within constraints
            if start_constraint:
                pub_date, start_constraint = ensure_consistent_timezone(pub_date, start_constraint)
                if pub_date < start_constraint:
                    valid = False
                    reason = f"Article too old. Published on {pub_date.strftime('%Y-%m-%d %H:%M')}, start constraint is {start_constraint.strftime('%Y-%m-%d %H:%M')}"
            
            if end_constraint:
                pub_date, end_constraint = ensure_consistent_timezone(pub_date, end_constraint)
                if pub_date > end_constraint:
                    valid = False
                    reason = f"Article too recent. Published on {pub_date.strftime('%Y-%m-%d %H:%M')}, end constraint is {end_constraint.strftime('%Y-%m-%d %H:%M')}"
        
        if not valid:
            print(reason)
            
        return {
            "valid": valid,
            "timestamp": pub_date.isoformat(),
            "url": url,
            "reason": reason if not valid else None
        }
        
    except Exception as e:
        print(f"Error checking {url}: {str(e)}")
        return {"valid": False, "timestamp": None, "url": url, "reason": f"Error: {str(e)}"}

def extract_publication_date(soup: BeautifulSoup, url: str) -> Optional[datetime]:
    """
    Extract the publication date from a news article
    
    Args:
        soup (BeautifulSoup): The parsed HTML content
        url (str): The URL of the article
        
    Returns:
        Optional[datetime]: The publication date if found, None otherwise
    """
    # Check for structured data
    structured_data = soup.find('script', {'type': 'application/ld+json'})
    if structured_data:
        try:
            import json
            data = json.loads(structured_data.string)
            if isinstance(data, list):
                data = data[0]
            
            date_str = None
            # Check various fields where date might be stored
            for field in ['datePublished', 'dateModified', 'dateCreated', 'uploadDate']:
                if field in data:
                    date_str = data[field]
                    break
                    
            if date_str:
                parsed_date = dateutil.parser.parse(date_str)
                # Convert to naive datetime if it has timezone info
                if parsed_date.tzinfo is not None:
                    parsed_date = parsed_date.replace(tzinfo=None)
                return parsed_date
        except:
            pass
    
    # Common meta tags for publication date
    meta_tags = [
        ('meta[property="article:published_time"]', 'content'),
        ('meta[name="pubdate"]', 'content'),
        ('meta[name="publishdate"]', 'content'),
        ('meta[name="timestamp"]', 'content'),
        ('meta[name="date"]', 'content'),
        ('time', 'datetime')
    ]
    
    for selector, attr in meta_tags:
        date_tag = soup.select_one(selector)
        if date_tag and date_tag.get(attr):
            try:
                parsed_date = dateutil.parser.parse(date_tag[attr])
                # Convert to naive datetime if it has timezone info
                if parsed_date.tzinfo is not None:
                    parsed_date = parsed_date.replace(tzinfo=None)
                return parsed_date
            except:
                continue
    
    # Common patterns for dates in HTML text
    date_patterns = [
        # Look for date strings in HTML
        r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})',
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
        r'(\d{2}/\d{2}/\d{4})',
        r'(\d{4}/\d{2}/\d{2})',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, soup.text)
        if match:
            try:
                parsed_date = dateutil.parser.parse(match.group(1))
                # Convert to naive datetime if it has timezone info
                if parsed_date.tzinfo is not None:
                    parsed_date = parsed_date.replace(tzinfo=None)
                return parsed_date
            except:
                continue
    
    # No date found
    return None

def ensure_consistent_timezone(dt1, dt2):
    """
    Ensure both datetime objects have consistent timezone information before comparison.
    
    Args:
        dt1 (datetime): First datetime object
        dt2 (datetime): Second datetime object
        
    Returns:
        tuple: (dt1, dt2) with consistent timezone information
    """
    if dt1 is None or dt2 is None:
        return dt1, dt2
    
    # Make both naive if either one is naive
    if dt1.tzinfo is None and dt2.tzinfo is not None:
        dt2 = dt2.replace(tzinfo=None)
    elif dt1.tzinfo is not None and dt2.tzinfo is None:
        dt1 = dt1.replace(tzinfo=None)
    
    return dt1, dt2
