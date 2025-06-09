import os
import json
import random
import re
from datetime import datetime, timedelta
import argparse
from dotenv import load_dotenv

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

class EnvisageWebController:
    def __init__(self):
        """Initialize the controller with log file and database connection."""
        # Setup logging
        self.today_now = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"envisage_web_{self.today_now}_log.txt"
        try:
            create_log_file(self.log_file)
        except NameError:
            print(f"Warning: create_log_file function not available. Log file {self.log_file} not created.")
        
        # Connect to database
        self.db = db['gemini_api']
        self.web_db = db['envisage_web']
        
        # Get the current date with time constraint
        self.today_date = self._get_date_with_time_constraint()
        
        append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][__init__] Initialized with date constraint: {self.today_date}")

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
        append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][_get_date_with_time_constraint] Date with time constraint: {date_with_constraint}")
        
        return date_with_constraint

    def _clean_title(self, title):
        """Clean title text by removing special characters and extra spaces."""
        # Remove special characters but keep basic punctuation
        cleaned = re.sub(r'[^\w\s.,!?-]', '', title)
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    def fetch_and_transform_summary(self, date=None):
        """
        Fetch summary for a specific date and transform it to the required format.
        
        Args:
            date (str, optional): The date with time constraint to fetch.
                                 If None, uses the current date with time constraint.
        
        Returns:
            dict: The transformed data ready for web display
        """
        if date is None:
            date = self.today_date
            
        append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_and_transform_summary] Fetching summary for date: {date}")
        print(f"DEBUG: Fetching summary for date: {date}")
        
        # Query the database for the summary
        query = {f"Summary.{date}": {"$exists": True}}
        print(f"DEBUG: MongoDB query: {query}")
        result = self.db.find_one(query)
        
        # Debug print for the raw result from MongoDB
        # print(f"DEBUG: MongoDB raw result: {result}")
        
        if not result:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_and_transform_summary] No summary found for date: {date}")
            print(f"DEBUG: No summary found for date: {date}")
            return None
            
        try:
            # Extract the summary for the specified date
            summary_data = result["Summary"][date]
            # print(f"DEBUG: Initial summary_data structure: {type(summary_data)}")
            
            # Check for nested date structure (date key appears twice)
            if isinstance(summary_data, dict) and date in summary_data:
                print(f"DEBUG: Detected nested date structure, extracting inner content")
                summary_data = summary_data[date]
            
            # Debug print the summary data
            # print(f"DEBUG: Extracted summary data: {json.dumps(summary_data, indent=2)[:500]}...")
            
            # Create the base structure for web display
            web_data = {
                "date": date,
                "overall_introduction": summary_data.get("overall_introduction", ""),
                "overall_conclusion": summary_data.get("overall_conclusion", ""),
                "newsItems": []
            }
            
            # Process each category
            id_counter = 1
            
            if "categories" in summary_data:
                # print(f"DEBUG: Processing {len(summary_data['categories'])} categories")
                for category, value in summary_data["categories"].items():
                    # print(f"DEBUG: Processing category: {category}")
                    # Clean the title to remove special characters
                    clean_title = self._clean_title(value.get("title", category))
                    # print(f"DEBUG: Cleaned title: {clean_title}")
                    
                    # Create the news item structure directly without slug transformation
                    news_item = {
                        "id": id_counter,
                        "title": clean_title,
                        "summary": value.get("summary", ""),
                        "image": f"/placeholder.svg?height=400&width=600&category={category}",
                        "category": category,
                        "date": date.split('_')[0],  # Extract just the date part
                        # Just use lowercase title as slug without further processing
                        "views": random.randint(1000, 5000),  # Random value between 1000-5000
                        "isRead": False,
                        "articleCount": value.get("article_count", 0),
                        "sourceCount": value.get("source_count", 0),
                    }
                    
                    # print(f"DEBUG: Created news item: {json.dumps(news_item, indent=2)}")
                    web_data["newsItems"].append(news_item)
                    id_counter += 1
            
            append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_and_transform_summary] Successfully processed {len(web_data['newsItems'])} categories")
            # print(f"DEBUG: Final web data structure has {len(web_data['newsItems'])} news items")
            # print(f"DEBUG: Sample of web_data: {json.dumps({k: v if k != 'newsItems' else f'{len(v)} items' for k, v in web_data.items()}, indent=2)}")
            return web_data
            
        except Exception as e:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_and_transform_summary] Error processing summary: {str(e)}")
            print(f"DEBUG: Error processing summary: {str(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            return None

    def store_web_data(self, web_data):
        """
        Store the transformed web data in the database.
        
        Args:
            web_data (dict): The web data structure to store
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not web_data:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][WARN][{datetime.today().strftime('%H:%M:%S')}][store_web_data] No web data to store")
            print(f"DEBUG: No web data to store")
            return False
            
        try:
            # Create the document to insert
            date = web_data["date"]
            document = {"envisage_web": {date: web_data}}
            
            print(f"DEBUG: Storing web data for date: {date}")
            print(f"DEBUG: Document structure: {json.dumps({k: v if k != 'envisage_web' else f'{len(v[date].get('newsItems', []))} news items' for k, v in document.items()}, indent=2)}")
            
            # Check if a document already exists for this date
            existing = self.web_db.find_one({f"envisage_web.{date}": {"$exists": True}})
            
            if existing:
                print(f"DEBUG: Found existing document for date: {date}")
                # Update existing document
                self.web_db.update_one(
                    {f"envisage_web.{date}": {"$exists": True}},
                    {"$set": {f"envisage_web.{date}": web_data}}
                )
                append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][store_web_data] Updated existing web data for date: {date}")
                print(f"DEBUG: Updated existing web data for date: {date}")
            else:
                print(f"DEBUG: No existing document found for date: {date}, creating new")
                # Insert new document
                result = self.web_db.insert_one(document)
                append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][store_web_data] Inserted new web data for date: {date}")
                print(f"DEBUG: Inserted new web data for date: {date}, document ID: {result.inserted_id}")
                
            return True
            
        except Exception as e:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][ERR][{datetime.today().strftime('%H:%M:%S')}][store_web_data] Error storing web data: {str(e)}")
            print(f"DEBUG: Error storing web data: {str(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            return False

    def process_date(self, date=None):
        """
        Process a specific date - fetch, transform and store the summary data.
        
        Args:
            date (str, optional): Date to process in 'YYYY-MM-DD_HH:00' format.
                                 If None, uses current date with time constraint.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if date is None:
            date = self.today_date
            
        append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][process_date] Processing date: {date}")
        print(f"DEBUG: Processing date: {date}")
        
        # Fetch and transform the summary
        web_data = self.fetch_and_transform_summary(date)
        if not web_data:
            print(f"DEBUG: Failed to fetch and transform summary for date: {date}")
            return False
            
        print(f"DEBUG: Successfully fetched and transformed summary for date: {date}")
        
        # Store the transformed data
        result = self.store_web_data(web_data)
        print(f"DEBUG: Result of storing web data: {result}")
        return result

    def get_all_available_dates(self):
        """
        Returns a list of all unique dates available in the database with summaries.
        
        Returns:
            list: List of date strings in format 'YYYY-MM-DD_HH:00'
        """
        date_pattern = r"\d{4}-\d{2}-\d{2}_\d{2}:\d{2}"  # Regex pattern for YYYY-MM-DD_HH:MM format
        print(f"DEBUG: Looking for dates with pattern: {date_pattern}")

        # Aggregate pipeline to extract all field names that match the date pattern
        pipeline = [
            {"$project": {"documentFields": {"$objectToArray": "$Summary"}}},
            {"$unwind": "$documentFields"},
            {"$match": {"documentFields.k": {"$regex": date_pattern}}},
            {"$group": {"_id": None, "dates": {"$addToSet": "$documentFields.k"}}},
            {"$project": {"_id": 0, "dates": 1}}
        ]

        print(f"DEBUG: Executing MongoDB aggregation pipeline: {pipeline}")
        result = list(self.db.aggregate(pipeline))
        print(f"DEBUG: Aggregation result: {result}")

        if result and 'dates' in result[0]:
            dates = result[0]['dates']
            # Sort dates chronologically with custom sort function
            dates.sort(key=lambda x: x.replace('_', 'T'), reverse=True)
            append_to_log(self.log_file, f"[ENVISAGE_WEB][DBG][{datetime.today().strftime('%H:%M:%S')}][get_all_available_dates] Found {len(dates)} dates with summaries")
            print(f"DEBUG: Found {len(dates)} dates with summaries: {dates}")
            return dates
        else:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][DBG][{datetime.today().strftime('%H:%M:%S')}][get_all_available_dates] No dates with summaries found")
            print(f"DEBUG: No dates with summaries found")
            return []

    def process_all_dates(self):
        """
        Process all available dates with summaries.
        
        Returns:
            dict: Dictionary mapping dates to success/failure status
        """
        dates = self.get_all_available_dates()
        results = {}
        
        for date in dates:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][process_all_dates] Processing date: {date}")
            success = self.process_date(date)
            results[date] = success
            
        return results

    def fetch_web_data(self, date=None):
        """
        Fetch the stored web data for a specific date from the envisage_web collection.
        
        Args:
            date (str, optional): The date with time constraint to fetch in 'YYYY-MM-DD_HH:00' format.
                                 If None, uses the current date with time constraint.
        
        Returns:
            dict: The web data for the requested date, or None if not found
        """
        if date is None:
            date = self.today_date
            
        append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_web_data] Fetching web data for date: {date}")
        print(f"DEBUG: Fetching web data for date: {date}")
        
        # Query the database for the web data
        query = {f"envisage_web.{date}": {"$exists": True}}
        print(f"DEBUG: MongoDB query: {query}")
        result = self.web_db.find_one(query)
        
        if not result:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_web_data] No web data found for date: {date}")
            print(f"DEBUG: No web data found for date: {date}")
            return None
            
        try:
            # Extract the web data for the specified date
            web_data = result["envisage_web"][date]
            append_to_log(self.log_file, f"[ENVISAGE_WEB][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_web_data] Successfully retrieved web data for date: {date}")
            print(f"DEBUG: Successfully retrieved web data with {len(web_data.get('newsItems', []))} news items")
            return web_data
            
        except Exception as e:
            append_to_log(self.log_file, f"[ENVISAGE_WEB][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_web_data] Error retrieving web data: {str(e)}")
            print(f"DEBUG: Error retrieving web data: {str(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            return None

def main():
    """Main function to run the script from command line."""
    parser = argparse.ArgumentParser(description='Process web data from Gemini API summaries')
    parser.add_argument('--date', help='Date to process in YYYY-MM-DD_HH:00 format')
    parser.add_argument('--all', action='store_true', help='Process all available dates')
    args = parser.parse_args()
    
    controller = EnvisageWebController()
    
    if args.all:
        print("Processing all available dates...")
        results = controller.process_all_dates()
        for date, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            print(f"{date}: {status}")
    elif args.date:
        print(f"Processing date: {args.date}")
        success = controller.process_date(args.date)
        status = "SUCCESS" if success else "FAILED"
        print(f"Result: {status}")
    else:
        print(f"Processing current date with time constraint: {controller.today_date}")
        success = controller.process_date()
        status = "SUCCESS" if success else "FAILED"
        print(f"Result: {status}")
    
    print("Processing complete")

if __name__ == "__main__":
    main()
