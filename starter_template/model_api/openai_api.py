from openai import OpenAI
import os
import json
import time
from dotenv import load_dotenv
# from .web_scrapper_api import get_links_and_content_from_page
# from .mongo import db
from datetime import datetime
from threading import Thread, Lock
# from .logging_scripts import *

try:
    from .web_scrapper_api import get_links_and_content_from_page
    from .mongo import db
    from .logging_scripts import *
except ImportError:
    from web_scrapper_api import get_links_and_content_from_page
    from mongo import db
    from logging_scripts import *



class OpenAiAPI:
    def __init__(self):
        load_dotenv()   
        self.client=OpenAI(
            organization=os.getenv('ORG'),
            project=os.getenv('PROJ'),
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.today = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"openai_{self.today}_log.txt"
        create_log_file(self.log_file)
        # run = None
        # self.thread = None
        # self.message = None
        self.thread_lock = Lock()
        self.thread_result = {}
        self.summary={}
        self.db = db['openai_api']  # change everywhere in the code
        self.today_date = datetime.today().strftime('%Y-%m-%d') # Fix this
        # self.today_date = '2025-02-12' #Debugging
        self.news_thread=self.client.beta.threads.create()
        self.grd_thread=self.client.beta.threads.create()
        self.MAX_RETRY = 0
        self.MAX_BATCHES = 5


    # def openai_log_init(self,log_file):

    # def get_rslt(self):
    #     return self.__thread_result = {}
    
    # def get_lock(self):
    #     return self.__thread_lock = Lock()

    # def get_summary(self):
    #     self.__summary = {}
    #     return self.__summary
    

# print(os.getenv('PROJ'))

    def get_news_src(self):
      news_sources = {
            "Climate Technology": [
                "https://www.thehindu.com/sci-tech/energy-and-environment/",
                # "https://www.ndtv.com/topic/climate-change",
                # "https://www.indiatoday.in/india/climate-change",
                # "https://www.business-standard.com/climate-change",
                # "https://www.deccanherald.com/specials/insight/climate-change-618973.html"
            ],
            "Government Politics": [
                "https://www.thehindu.com/news/national/politics/",
                # "https://www.ndtv.com/india-politics",
                # "https://www.timesofindia.indiatimes.com/india",
                # "https://www.indiatoday.in/india",
                # "https://www.tribuneindia.com/news/punjab/politics",
                # "https://www.eenaduindia.com/"
            ],
            "Travel Industry": [
                "https://www.indiatoday.in/travel",
                # "https://www.businessinsider.in/business/news/india-travel",
                # "https://www.hindustantimes.com/india-news",
                # "https://www.moneycontrol.com/news/travel/",
                # "https://www.financialexpress.com/industry/tourism-travel-industry-news/"
            ],
            "Stock Market": [
                # "https://www.moneycontrol.com/",
                "https://www.bloombergquint.com/markets",
                # "https://www.business-standard.com/markets",
                # "https://economictimes.indiatimes.com/markets",
                # "https://www.moneycontrol.com/markets/"
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
        
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][openai_api_request] Recieved OPENAI request for content {txt}")
        thread = self.news_thread  
        # print(f"Thread created: {thread.id}")  # Debugging line
        message = self.client.beta.threads.messages.create(  # Create a new message in the thread
            thread_id=thread.id,
            role="user",
            content=txt
        )
        # print(f"Message created: {message.id}")  # Debugging line
        run = self.client.beta.threads.runs.create(  # Create a new run in the thread
            thread_id=thread.id,
            assistant_id='asst_WqxlAhEY2ktg9mj5fGHqvNaq',
        )
        # print(f"Run created: {run.id}")  # Debugging line
        run = self.wait_on_run( run, thread)
        if (run.status == 'failed' or run.status == 'stopped'):
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][openai_api_request] Failed run : {run}")
            raise Exception(f"Run failed or stopped with error: {run}")
        while run.status == 'requires_action':  # Handle required actions if the run status is 'requires_action'
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][openai_api_request] Tool name: {run.required_action.submit_tool_outputs.tool_calls[0].id}")
            # print(f"Tool name {run.required_action.submit_tool_outputs.tool_calls[0].id}")  # Debugging line
            run = self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=[{"tool_call_id": run.required_action.submit_tool_outputs.tool_calls[0].id, "output": "true"}]
            )
            self.wait_on_run(run, thread)  # Wait for the run to complete
            # print(f"FINAL Run requires action: {run.status}")  # Debugging line
        messages = self.client.beta.threads.messages.list(
            thread_id=thread.id, order='asc', after=message.id,
        )
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][openai_api_request] Messages retrieved from thread: {messages}")
        # print(f"Messages: {messages}")  # Debugging line
        return messages



    def wait_on_run(self, run, thread):
        while run.status=='queued' or run.status=='in_progress':
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][wait_on_run] Run status: {run.status}")
            # print(f"Run status: {run.status}")  # Debugging line
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            time.sleep(0.5)
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][wait_on_run] Run status after completion: {run.status}, Run ID: {run.id}")
        # print(f"Run status after completion: {run.status}")  # Debugging line
        return run
    

    def list_assistant(self):
        my_assistant= self.client.beta.assistants.list(
            order="desc",
            limit="4",
        )
    # print(my_assistant.data)




    def start_openai_assistant(self)-> None:
        openai_links_db = db['openai_api']  # Add to constructor
        
        append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Starting OpenAI Assistant")
        news_sources = self.get_news_src()
        links = {}
        lock = self.thread_lock
        result_grded_news = {}
        
        def process_lnks(category, sources):
            nonlocal links    
            # for category in news_sources:
            if category not in links:
                links[category] = {}
            for source in sources:
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Getting news from {source}")
                try:
                    links[category][source] = get_links_and_content_from_page(source)
                    append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Successfully extracted news from {source}")
                    append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] *****************************************************")
                except Exception as e:
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] ************************ERROR************************")
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Failed to extract news from {source}: {e}")
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] *****************************************************")
            # today_date = self.today_date  # Changed
            print(" IT'S HEREEEEEEEEEEEEEEEEEEEEEEEEEEEE")
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Before processing Processing category: {links[category]} and length {len(links[category])} and for category {category}")
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Thread ID for {category}: {thread.ident}")
            if not category in result_grded_news:
                result_grded_news[category] = []
            with lock:
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Thread {thread.ident} acquired lock for {category}")
                result_grded_news[category] = self.grd_nws(links[category], category)
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] After processing Processing category: {result_grded_news[category]} and length {len(result_grded_news[category])} and for category {category}")
            with lock:
                try:
                    openai_links_db.insert_one({self.today_date:{category: result_grded_news[category]}})  # Changed
                    append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Successfully inserted data for {category} into MongoDB")
                except Exception as e:
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Failed to insert data into MongoDB: {e}")
                    print(f"Failed to insert data into MongoDB: {e}")
                # openai_links_db.insert_one({today_date:{category: links}})
        threads = []
        for category, sources in news_sources.items():
            thread = Thread(target=process_lnks, args=(category, sources))
            threads.append(thread)
            thread.start()
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Starting thread for {category} with thread ID: {thread.ident}")
        for thread in threads:
            thread.join()
        # print("News retrieval complete")
        append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] News retrieval complete")
        # client.close()
        # print(links)
        # exit(0)
        return None


    def write_to_file(self, txt, file_name):
        try:
            file_path = os.path.join(os.path.dirname(__file__), file_name)
            print(f"Writing to file: {file_path}")
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(txt)
        except Exception as e:
            print(f"Failed to write to file with error: {e}")

    def check_news_in_db(self, preferred_category):
        openai_links_db = db['openai_api'] # Add to constructor
        today_date = self.today_date #add to constructor
        print(today_date)
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] Checking news for date: {today_date}")
        if not preferred_category:
            query = {self.today_date: {"$exists": True}}
            # for news_data in news_data_cursor:
            #     append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] News data from database: {news_data}")
                # print(news_data)
            # exit()
        else:
            query = {f"{today_date}.{preferred_category}": {"$exists": True}}
            # for news_data in news_data_cursor:
            #     append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] News data from database: {news_data}")
            #     # print(news_data)
            # exit()
        news_data_cursor = openai_links_db.find(query)
        
        collected_news = {}
        
        for news_data in news_data_cursor:
            # print("ITS HERE")
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] Found news data in database {news_data}")
            
            for date, categories in news_data.items():
                if date == "_id":
                    continue
                for category, sources in categories.items():
                    if category not in collected_news:
                        collected_news[category] = {}
                    for source, content in sources.items():
                        collected_news[category][source] = content
        if not collected_news:
            # print("No news data found for today in the database.")
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] No news data found for today in the database")
            return None
        return collected_news

# print(f" NEWS are present {check_news_in_db()}")
    def process_category(self, category, sources):
        result = {}
        for source, content in sources.items():
            # print(f"Processing news from {source} in category {category}")
            for link, details in content.items():
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][process_category] LINK from the news: {link}")
                # write_to_file(str(details), "details.txt")
                if len(details) != 2:
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][process_category] Skipping link {link} as it has insufficient details")
                    print(f"Skipping link {link} as it has insufficient details")
                    continue
                title, news_content = details
                # exit()
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Processing summary for {link} with title: {title}")
                summary = self.openai_api_request(f"Summarize the news from {link} with the title {title} and content {news_content} with at least 100 words")   # Neeeds better prompt
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Summary result: {summary.data[0].content[0].text.value}")
                # print(f"Summary for {link}: {summary.data[0].content[0].text.value}")
                if category not in result:
                    result[category] = {}
                if source not in result[category]:
                    result[category][source] = []
                result[category][source].append({
                    "link": link,
                    "title": title,
                    "content": news_content,
                    "summary": summary.data[0].content[0].text.value
                }) # Needs refactoring and change of structure
                with self.thread_lock:
                    append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Thread acquired lock for {result[category]}") # Check with result.category.title
                    self.thread_result[category] = result
                # write_to_file(result, "result.txt")

    def run_sumarizing_threads(self)-> None:
        threads = []
        self.thread_result.clear()
        content = self.check_news_in_db()
        if not content:
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] No content found in database")
            return None
        for category, sources in content.items():
            thread = Thread(target=self.process_category, args=(category, sources))
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] Starting thread")
            threads.append(thread)
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] Starting thread for {category} with {thread.ident}")
            thread.start()
            # print("Starting thread")
            # print(f"Starting thread for {category} with {thread.ident}" )
        for thread in threads:
            thread.join()


    def push_results_to_db(self ,result, result_type):
        print("Result from OpenAI") 
        print("CONTENT FROM DB")
        openai_links_db = db['openai_api'] # Add to constructor
        # query = db.openai_links_db.find({ "$and" : [{datetime.today().strftime('%Y-%m-%d'): {"$exists": True}},{"Result":{"$exists": True}}]})
        # for doc in query:
        #     print("DOC id ",doc)
        # write_to_file(str([doc for doc in query]), "query.txt")
        openai_links_db.insert_one({result_type:{self.today_date: result}})  # Changed


# content = check_news_in_db()
# run_sumarizing_threads()
# push_results_to_db(result)
    def fetch_todays_results(self):
        openai_links_db = db['openai_api']   # Add to constructor
        today_date = self.today_date
        query = {f"Result.{self.today_date}": {"$exists": True}}  # Changed
        # print(f"[DEBUG] Query: {query}")
        results_cursor = openai_links_db.find(query)
        if not results_cursor:
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] No results found in MongoDB for today's date")
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Fetching today's results from MongoDB: {results_cursor}")
        # print("executing loop now")
        result_json = None
        for result in results_cursor:
            # print("IN LOOP")
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Query result: {result['_id']}")
            # Convert ObjectId to string representation
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Processing result: {result['_id']}")
            # print(result)
            result['_id'] = str(result['_id'])
            result_json =json.dumps(result, indent=4)
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Result JSON: {result_json}")
        return result_json



# run_sumarizing_threads()
# if thread_result:
#     push_results_to_db(thread_result)
#     append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] Successfully pushed summarized results to MongoDB")
    def fetch_content_and_run_summary(self)->None:  # Create checks to see if previous work has been completed before proceeding
        result_json = self.fetch_todays_results()
        if not result_json:
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No results found for today")
            self.run_sumarizing_threads() #Summarizing each news individually
            if self.thread_result:
                self.push_results_to_db(self.thread_result, "Result")
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Successfully pushed summarized results to MongoDB")
            else:
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No thread_result found, nothing to push to MongoDB")
        else: #Summarizing the whole thing
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Result JSON length: {len(result_json)}")
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Result : {result_json}")
            result_length = len(result_json)
            json_parts =  []

            if result_length > 256000:
                json_parts = [result_json[i:i+255533] for i in range(0, len(result_json), 255533)]
            else:
                json_parts.append(result_json)
            for json_part in json_parts:
                content=f"""Please analyze this news data and create a summary of 1000 words:
                1. Key bullet points for each category
                2. Important trends or patterns
                3. A brief executive summary
                4. Highlight any critical developments
                Data: {json_part}"""
                self.summary[json_part] = self.openai_api_request(content)
            if bool(self.summary):
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] SUMMARY IS PRESENT")
                print("Summary is present")
                self.check_summary_present()
                

# if bool(summary):
    def check_summary_present(self)-> None:
        print(" THERE is SUMMARY")
        # push_results_to_db(summary, "Summary")
        formatted_result= {}
        today_date = self.today_date
        for _, summary_response in self.summary.items():
                    # Extract the actual summary text from the OpenAI response
                    summary_text = summary_response.data[0].content[0].text.value
                    formatted_result[self.today_date] = summary_text  # Changed
        self.push_results_to_db(formatted_result, "Summary")
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_summary_present] Successfully pushed summary to MongoDB")


    def chk_news(self):
        # news = self.get_news_src()
        flag = []
        i = 0
        for category in self.get_news_src():
            if  self.db.count_documents({f"{self.today_date}.{category}": {"$exists":True}}) > 0:  #check if None the false? also does it always return something?
                flag.append(1)
            else:
                flag.append(0)
        return flag
        # query = {f"Result.{self.today_date}": {"$exists": True}}


    def chk_results(self):
        if self.db.count_documents( {f"Result.{self.today_date}": {"$exists": True}}) > 0:
            print(f"Results are present {self.db.find( {f"Result.{self.today_date}": {"$exists": True}})}")
            return True
        return False
    
    def chk_summary(self):
        if self.db.count_documents({f"Summary.{self.today_date}": {"$exists": True}}) > 0:
            print(f"Summary is present {self.db.find({f"Summary.{self.today_date}": {"$exists": True}})}")
            return True
        return False


    def grd_nws(self, links, category):
        news = links
        summary = self.summary
        new_links = []
        result_links = {}
        categories = self.get_categories()
        
        if news and summary:
            return None
        elif news:
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] News is present for category {category}")
            # for category, value in list(news.items()):
            for top_url in list(links.keys()):
                step = max(1, int(len(list(news[top_url].items()))/self.MAX_BATCHES))
                link_items = [list(news[top_url].items())[j:j+step] for j in range(0, len(list(news[top_url].items())), step)]
                # with self.thread_lock:
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing {len(link_items)} batches for {category}")
                for link_item in link_items:
                    try:
                        grading_response = self.grding_assistant(f"""
                            Analyze these articles: {link_item}
                            Categorize each article into the most appropriate categories from this list: {list(categories.keys())}
                            An article can belong to multiple categories if relevant.
                            
                            Return the result as a dictionary where:
                            - Keys are category names from the provided categories list
                            - Values are lists of tuples containing (article_url, [title, content])
                            
                            Only include articles that are relevant to at least one category.
                            Format the response as a valid Python dictionary.

                            Only return the python dict and nothing else, avoid ``` and word python in the string
                            """)
                        
                        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Received grading response: {grading_response.data[0].content[0].text.value}")
                        
                        categorized_data = eval(grading_response.data[0].content[0].text.value)
                        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Received categorization: {categorized_data}")
                        
                        # Merge the categorized data into result_links
                        for cat, articles in categorized_data.items():
                            if cat not in result_links:
                                result_links[cat] = {}
                            if articles:  # Only process if there are articles
                                if top_url not in result_links[cat]:
                                    result_links[cat][top_url] = {}
                                for article_url, content in articles:
                                    result_links[cat][top_url][article_url] = content
                        
                    except Exception as e:
                        append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Error processing batch: {str(e)}")
                        continue
                
            # Remove empty categories
            result_links = {k: v for k, v in result_links.items() if v}
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Final categorized news: {result_links}")
            
        return result_links


    # def grding_assistant():
    def grding_assistant(self, txt):
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Creating message for grading: {txt}")
        thread = self.grd_thread
        message = self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=txt
        )
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Created message with ID: {message.id}")
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id='asst_yBgMEeLeT7DTFiBs1xo4MeLc'
        )
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Created run with ID: {run.id}")
        run = self.wait_on_run(run, thread)
        if run.status == 'failed' or run.status == 'stopped' or run.status == 'expired':
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Run failed or stopped: {run}")
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Run failed, attempting retry")
            retries = 0
            while retries < self.MAX_RETRY:
                run = self.client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id='asst_yBgMEeLeT7DTFiBs1xo4MeLc'
                )
                run = self.wait_on_run(run, thread)
                if run.status != 'failed' and run.status != 'stopped' and run.status != 'expired':
                    break
                retries += 1
                append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Grading run failed: {run}")
            # raise Exception(f"Grading run failed or stopped: {run}")
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Getting Message List")
        messages = self.client.beta.threads.messages.list(
            thread_id=thread.id, 
            order='asc', 
            after=message.id
        )
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Returning messages")
        return messages
    

        # append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grding_assistant] Grading messages: {messages}")
# else:   
#     append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] No summary data to push to MongoDB")
# if result_json:
#     summary_request = client.beta.threads.messages.create(
#         thread_id=client.beta.threads.create().id,
#         role="user",
#         content=f"""Please analyze this news data and create:
#         1. Key bullet points for each category
#         2. Important trends or patterns
#         3. A brief executive summary
#         4. Highlight any critical developments
        
#         Data: {result_json}"""
#     )
    
    # formatted_summary = openai_api_request("Please format the above news data into clear, eye-catching bullet points. For each category, include the most impactful headlines and key takeaways. Use emoji indicators where appropriate.")
    


# for message in summary:
#     print(message)
#     print("\n-------------------\n")

# print("Content from DB" , content)


# start_openai_assistant()
    # for key in links:
    #     print(f"Content from {key}")
    #     for link in links[key]:
    #         print(f"Title: {links[key][link][0]}")
    #         print(f"Content: {links[key][link][1]}")
    #         content = openai_api_request(f"Summarize the news from {link} with the title {links[key][link][0]} and content {links[key][link][1]}")
    #         print("Summary:")
    #         print(content.data[0].content[0].text.value)
    #     print("\n\n")