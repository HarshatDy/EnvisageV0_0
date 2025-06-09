import os
import json
import pymysql
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import the EnvisageWebController class
try:
    # Try relative imports (for Django)
    from .envisage_web_ct_ctr import EnvisageWebController
    from .logging_scripts import *
except ImportError:
    try:
        # Try absolute imports (for standalone script)
        from envisage_web_ct_ctr import EnvisageWebController
        from logging_scripts import *
    except ImportError:
        print("Warning: Could not import some modules. Some functionality may be limited.")

class HostingerDBUpdater:
    def __init__(self):
        """Initialize the updater with connections to MongoDB and MySQL."""
        # Load environment variables
        load_dotenv()
        
        # Setup logging
        self.today_now = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"hostinger_db_update_{self.today_now}_log.txt"
        try:
            create_log_file(self.log_file)
        except NameError:
            print(f"Warning: create_log_file function not available. Log file {self.log_file} not created.")
        
        # Initialize the EnvisageWebController to access MongoDB data
        self.web_controller = EnvisageWebController()
        
        # MySQL connection details
        self.mysql_config = {
            'host': os.getenv('MYSQL_HOST', 'srv876.hstgr.io'),  # or '82.180.142.51'
            'user': os.getenv('MYSQL_USER', ''),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DATABASE', ''),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        # Test database connection
        try:
            self._get_mysql_connection()
            append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][__init__] Successfully connected to MySQL database")
            print(f"Successfully connected to MySQL database")
        except Exception as e:
            append_to_log(self.log_file, f"[HOSTINGER_DB][ERR][{datetime.today().strftime('%H:%M:%S')}][__init__] Failed to connect to MySQL: {str(e)}")
            print(f"Failed to connect to MySQL: {str(e)}")
    
    def _get_mysql_connection(self):
        """Create and return a MySQL connection."""
        return pymysql.connect(**self.mysql_config)
    
    def _create_tables_if_not_exist(self):
        """Create the necessary tables in MySQL if they don't exist."""
        try:
            connection = self._get_mysql_connection()
            cursor = connection.cursor()
            
            # Create table for summary data
            summary_table_sql = """
            CREATE TABLE IF NOT EXISTS summary_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date VARCHAR(20) UNIQUE,
                overall_introduction TEXT,
                overall_conclusion TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
            
            # Create table for news items
            news_items_table_sql = """
            CREATE TABLE IF NOT EXISTS news_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                summary_date VARCHAR(20),
                title VARCHAR(255),
                summary TEXT,
                image VARCHAR(255),
                category VARCHAR(100),
                date DATE,
                slug VARCHAR(255),
                views INT DEFAULT 0,
                is_read BOOLEAN DEFAULT FALSE,
                article_count INT DEFAULT 0,
                source_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (summary_date) REFERENCES summary_data(date) ON DELETE CASCADE,
                UNIQUE KEY (summary_date, category)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
            
            cursor.execute(summary_table_sql)
            cursor.execute(news_items_table_sql)
            connection.commit()
            
            append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][_create_tables_if_not_exist] Tables created successfully")
            print("Tables created successfully")
            
        except Exception as e:
            append_to_log(self.log_file, f"[HOSTINGER_DB][ERR][{datetime.today().strftime('%H:%M:%S')}][_create_tables_if_not_exist] Error creating tables: {str(e)}")
            print(f"Error creating tables: {str(e)}")
        finally:
            if connection:
                connection.close()
    
    def _insert_or_update_summary(self, web_data):
        """Insert or update the summary data in MySQL."""
        try:
            connection = self._get_mysql_connection()
            cursor = connection.cursor()
            
            date = web_data["date"]
            overall_introduction = web_data.get("overall_introduction", "")
            overall_conclusion = web_data.get("overall_conclusion", "")
            
            # Check if record exists
            cursor.execute("SELECT date FROM summary_data WHERE date = %s", (date,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing record
                cursor.execute(
                    "UPDATE summary_data SET overall_introduction = %s, overall_conclusion = %s WHERE date = %s",
                    (overall_introduction, overall_conclusion, date)
                )
                append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][_insert_or_update_summary] Updated summary for date: {date}")
                print(f"Updated summary for date: {date}")
            else:
                # Insert new record
                cursor.execute(
                    "INSERT INTO summary_data (date, overall_introduction, overall_conclusion) VALUES (%s, %s, %s)",
                    (date, overall_introduction, overall_conclusion)
                )
                append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][_insert_or_update_summary] Inserted new summary for date: {date}")
                print(f"Inserted new summary for date: {date}")
            
            connection.commit()
            return True
            
        except Exception as e:
            if connection:
                connection.rollback()
            append_to_log(self.log_file, f"[HOSTINGER_DB][ERR][{datetime.today().strftime('%H:%M:%S')}][_insert_or_update_summary] Error inserting/updating summary: {str(e)}")
            print(f"Error inserting/updating summary: {str(e)}")
            return False
        finally:
            if connection:
                connection.close()
    
    def _insert_or_update_news_items(self, web_data):
        """Insert or update the news items in MySQL."""
        try:
            connection = self._get_mysql_connection()
            cursor = connection.cursor()
            
            date = web_data["date"]
            news_items = web_data.get("newsItems", [])
            
            for item in news_items:
                title = item.get("title", "")
                item_summary = item.get("summary", "")
                image = item.get("image", "")
                category = item.get("category", "")
                item_date = item.get("date", "")  # This is date without time
                slug = item.get("slug", "")
                views = item.get("views", 0)
                is_read = 1 if item.get("isRead", False) else 0
                article_count = item.get("articleCount", 0)
                source_count = item.get("sourceCount", 0)
                
                # Check if record exists
                cursor.execute(
                    "SELECT id FROM news_items WHERE summary_date = %s AND category = %s",
                    (date, category)
                )
                exists = cursor.fetchone()
                
                if exists:
                    # Update existing record
                    cursor.execute(
                        """UPDATE news_items SET 
                        title = %s, summary = %s, image = %s, date = %s, slug = %s, 
                        views = %s, is_read = %s, article_count = %s, source_count = %s
                        WHERE summary_date = %s AND category = %s""",
                        (title, item_summary, image, item_date, slug, views, is_read, 
                         article_count, source_count, date, category)
                    )
                    append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][_insert_or_update_news_items] Updated news item: {category} for date: {date}")
                    print(f"Updated news item: {category} for date: {date}")
                else:
                    # Insert new record
                    cursor.execute(
                        """INSERT INTO news_items 
                        (summary_date, title, summary, image, category, date, slug, views, is_read, article_count, source_count)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (date, title, item_summary, image, category, item_date, slug, views, is_read, article_count, source_count)
                    )
                    append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][_insert_or_update_news_items] Inserted new news item: {category} for date: {date}")
                    print(f"Inserted new news item: {category} for date: {date}")
            
            connection.commit()
            return True
            
        except Exception as e:
            if connection:
                connection.rollback()
            append_to_log(self.log_file, f"[HOSTINGER_DB][ERR][{datetime.today().strftime('%H:%M:%S')}][_insert_or_update_news_items] Error inserting/updating news items: {str(e)}")
            print(f"Error inserting/updating news items: {str(e)}")
            return False
        finally:
            if connection:
                connection.close()
    
    def update_for_date(self, date=None):
        """
        Update MySQL database with data for a specific date.
        
        Args:
            date (str, optional): Date to process in 'YYYY-MM-DD_HH:00' format.
                                 If None, uses current time logic to determine the appropriate date and time.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Ensure tables exist
        self._create_tables_if_not_exist()
        
        if date is None:
            # Apply dynamic time logic to determine appropriate date and time format
            now = datetime.now()
            current_hour = now.hour
            
            if 6 <= current_hour < 18:
                # Between 6am and 6pm, use current day with 06:00
                date_format = now.strftime('%Y-%m-%d_06:00')
            else:
                # Between 6pm and 6am next day, use previous day with 18:00 if after 6pm
                # or between 6pm previous day and 6am current day, use previous day with 18:00
                if current_hour >= 18:
                    # After 6pm but still same day
                    date_format = now.strftime('%Y-%m-%d_18:00')
                else:
                    # Before 6am, so use previous day
                    yesterday = now - timedelta(days=1)
                    date_format = yesterday.strftime('%Y-%m-%d_18:00')
            
            date = date_format
            
        append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][update_for_date] Processing date: {date}")
        print(f"Processing date: {date}")
        
        # Fetch the web data from MongoDB
        web_data = self.web_controller.fetch_web_data(date)
        if not web_data:
            append_to_log(self.log_file, f"[HOSTINGER_DB][WARN][{datetime.today().strftime('%H:%M:%S')}][update_for_date] No data found for date: {date}")
            print(f"No data found for date: {date}")
            return False
            
        # Insert or update summary data
        summary_result = self._insert_or_update_summary(web_data)
        if not summary_result:
            return False
            
        # Insert or update news items
        news_items_result = self._insert_or_update_news_items(web_data)
        if not news_items_result:
            return False
            
        append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][update_for_date] Successfully updated MySQL for date: {date}")
        print(f"Successfully updated MySQL for date: {date}")
        return True
    
    def update_all_dates(self):
        """
        Update MySQL database with data for all available dates in MongoDB.
        
        Returns:
            dict: Dictionary mapping dates to success/failure status
        """
        # Ensure tables exist
        self._create_tables_if_not_exist()
        
        # Get all available dates from MongoDB
        dates = self.web_controller.get_all_available_dates()
        results = {}
        
        for date in dates:
            append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][update_all_dates] Processing date: {date}")
            success = self.update_for_date(date)
            results[date] = success
            
        return results
        
    def fetch_and_print_all_data(self, date=None):
        """
        Fetch all data from MySQL database and print it in a structured format.
        
        Args:
            date (str, optional): Date to fetch in 'YYYY-MM-DD_HH:00' format.
                                 If None, uses current time logic to determine the appropriate date and time.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            connection = self._get_mysql_connection()
            cursor = connection.cursor()
            
            # If no specific date is provided, determine based on time logic
            if date is None:
                # Apply dynamic time logic to determine appropriate date and time format
                now = datetime.now()
                current_hour = now.hour
                
                if 6 <= current_hour < 18:
                    # Between 6am and 6pm, use current day with 06:00
                    date_format = now.strftime('%Y-%m-%d_06:00')
                else:
                    # Between 6pm and 6am next day, use previous day with 18:00 if after 6pm
                    # or between 6pm previous day and 6am current day, use previous day with 18:00
                    if current_hour >= 18:
                        # After 6pm but still same day
                        date_format = now.strftime('%Y-%m-%d_18:00')
                    else:
                        # Before 6am, so use previous day
                        yesterday = now - timedelta(days=1)
                        date_format = yesterday.strftime('%Y-%m-%d_18:00')
                
                date = date_format
                append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_and_print_all_data] Using date: {date}")
                print(f"Using date: {date}")
            
            # Fetch summary data for specific date if provided
            if date:
                cursor.execute("SELECT * FROM summary_data WHERE date = %s", (date,))
            else:
                cursor.execute("SELECT * FROM summary_data ORDER BY date DESC")
            
            summaries = cursor.fetchall()
            
            if not summaries:
                append_to_log(self.log_file, f"[HOSTINGER_DB][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_and_print_all_data] No data found in summary_data table for date: {date}")
                print(f"No data found in the database for date: {date}")
                return False
                
            print("\n" + "="*80)
            print(f"{'DATE':^20} | {'SUMMARY COUNT':^15}")
            print("-"*80)
            
            for summary in summaries:
                date = summary['date']
                
                # Fetch news items for this summary
                cursor.execute("SELECT * FROM news_items WHERE summary_date = %s ORDER BY category", (date,))
                items = cursor.fetchall()
                
                print(f"{date:^20} | {len(items):^15}")
                
                # Print summary details
                print("\nSummary Details:")
                print(f"  Introduction: {summary['overall_introduction'][:100]}...")
                print(f"  Conclusion: {summary['overall_conclusion'][:100]}...")
                
                # Print news items
                if items:
                    print("\nNews Items:")
                    for item in items:
                        print(f"  Category: {item['category']}")
                        print(f"  Title: {item['title']}")
                        print(f"  Summary: {item['summary'][:100]}...")
                        print(f"  Stats: {item['article_count']} articles, {item['source_count']} sources, {item['views']} views")
                        print("  " + "-"*60)
                
                print("="*80)
                
            append_to_log(self.log_file, f"[HOSTINGER_DB][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_and_print_all_data] Successfully fetched and printed all data")
            return True
            
        except Exception as e:
            append_to_log(self.log_file, f"[HOSTINGER_DB][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_and_print_all_data] Error fetching data: {str(e)}")
            print(f"Error fetching data: {str(e)}")
            return False
        finally:
            if connection:
                connection.close()

def main():
    """Main function to run the script from command line."""
    parser = argparse.ArgumentParser(description='Update MySQL database with data from MongoDB')
    parser.add_argument('--date', help='Date to process in YYYY-MM-DD_HH:00 format')
    parser.add_argument('--all', action='store_true', help='Process all available dates')
    parser.add_argument('--fetch', action='store_true', help='Fetch and print all data from MySQL')
    parser.add_argument('--fetch-all', action='store_true', help='Fetch and print all dates from MySQL')
    args = parser.parse_args()
    
    updater = HostingerDBUpdater()
    
    if args.fetch_all:
        print("Fetching all data from MySQL database...")
        updater.fetch_and_print_all_data(None)
    elif args.fetch:
        if args.date:
            print(f"Fetching data from MySQL database for date: {args.date}")
            updater.fetch_and_print_all_data(args.date)
        else:
            print("Fetching data from MySQL database for current date with time constraint...")
            updater.fetch_and_print_all_data()
    elif args.all:
        print("Updating MySQL for all available dates...")
        results = updater.update_all_dates()
        for date, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            print(f"{date}: {status}")
    elif args.date:
        print(f"Updating MySQL for date: {args.date}")
        success = updater.update_for_date(args.date)
        status = "SUCCESS" if success else "FAILED"
        print(f"Result: {status}")
    else:
        print(f"Updating MySQL for current date with time constraint")
        success = updater.update_for_date()
        status = "SUCCESS" if success else "FAILED"
        print(f"Result: {status}")
    
    print("MySQL update complete")

if __name__ == "__main__":
    main()
