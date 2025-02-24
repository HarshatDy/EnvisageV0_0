from openai_api import OpenAiAPI
import json
from datetime import datetime
from logging_scripts import create_log_file, append_to_log

def main():
    # Initialize OpenAI API
    openai_client = OpenAiAPI()
    
    # Setup logging
    current_time = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    log_file = f"test_grading_{current_time}_log.txt"
    create_log_file(log_file)
    
    append_to_log(log_file, f"[TEST][INF][{datetime.now().strftime('%H:%M:%S')}][main] Starting test grading process")
    
    try:
        # Get news from database
        append_to_log(log_file, f"[TEST][INF][{datetime.now().strftime('%H:%M:%S')}][main] Fetching news from database")
        news_data = openai_client.check_news_in_db("Climate Technology")
        
        if not news_data:
            append_to_log(log_file, f"[TEST][ERR][{datetime.now().strftime('%H:%M:%S')}][main] No news found in database")
            return
        
        # Log the retrieved data
        append_to_log(log_file, f"[TEST][DBG][{datetime.now().strftime('%H:%M:%S')}][main] Retrieved news data:")
        append_to_log(log_file, json.dumps(news_data, indent=2))
        
        # Process through grading
        append_to_log(log_file, f"[TEST][INF][{datetime.now().strftime('%H:%M:%S')}][main] Starting grading process")
        graded_news = openai_client.grd_nws(news_data)
        
        # Log the results
        append_to_log(log_file, f"[TEST][DBG][{datetime.now().strftime('%H:%M:%S')}][main] Grading completed. Results:")
        append_to_log(log_file, json.dumps(graded_news, indent=2))
        
        append_to_log(log_file, f"[TEST][INF][{datetime.now().strftime('%H:%M:%S')}][main] Test completed successfully")
        print(f"Test completed. Check logs/{log_file} for results.")
        
    except Exception as e:
        append_to_log(log_file, f"[TEST][ERR][{datetime.now().strftime('%H:%M:%S')}][main] Error occurred: {str(e)}")
        print(f"Error occurred. Check logs/{log_file} for details.")

if __name__ == "__main__":
    main()
