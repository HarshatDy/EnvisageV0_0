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
        self.news_thread=self.client.beta.threads.create()
        self.grd_thread=self.client.beta.threads.create()
        self.MAX_RETRY = 5


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
                "https://www.ndtv.com/india-politics",
                # "https://www.timesofindia.indiatimes.com/india",
                "https://www.indiatoday.in/india",
                # "https://www.tribuneindia.com/news/punjab/politics",
                "https://www.eenaduindia.com/"
            ],
            "Travel Industry": [
                "https://www.indiatoday.in/travel",
                "https://www.businessinsider.in/business/news/india-travel",
                # "https://www.hindustantimes.com/india-news",
                "https://www.moneycontrol.com/news/travel/",
                "https://www.financialexpress.com/industry/tourism-travel-industry-news/"
            ],
            "Stock Market": [
                # "https://www.moneycontrol.com/",
                "https://www.bloombergquint.com/markets",
                # "https://www.business-standard.com/markets",
                # "https://economictimes.indiatimes.com/markets",
                "https://www.moneycontrol.com/markets/"
            ]
        }
      return news_sources




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




# def chat_with_function_calling(user_message: str):

#     response = client.ChatCompletion.create(
#         model="gpt-4-turbo",
#         messages=[{"role": "user", "content": user_message}],
#         functions=functions,
#         function_call="auto",
#     )

#     response_message = response["choices"][0]["message"]

#     if response_message.get("function_call"):
#         function_name = response_message["function_call"]["name"]
#         function_args = json.loads(response_message["function_call"]["arguments"])
#         if function_name == "fetch_web_data":
#             function_response = fetch_web_data(**function_args)
#             return function_response
    
#     return response_message["content"]

# # Example usage
# print(chat_with_function_calling("Get data from https://www.moneycontrol.com/technology/what-is-googleyness-google-ceo-sundar-pichai-finally-explains-what-it-means-for-company-article-12895142.html"))


# new_list = []

# def get_todays_news() -> None:
#     for key in news_sources:
#         print(f"News for {key}")
#         for source in news_sources[key]:
#             print(f"Getting news from {source}")
#             response = openai_api_request(f"Get today's news from {source} in 350 words")
#             if response:
#                 new_list.append(response.data[0].content[0].text.value)
#                 print(response.data[0].content[0].text.value)
#             else:
#                 print("Failed to get news")
#         print("\n\n")
#     print("News retrieval complete")
# get_todays_news()

    def start_openai_assistant(self)-> None:
        openai_links_db = db['openai_api']  # Add to constructor
        
        append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Starting OpenAI Assistant")
        news_sources = self.get_news_src()
        links = {}
        for key in news_sources:
            if key not in links:
                links[key] = {}
            # print(f"News for {key}")
            for source in news_sources[key]:
                # print(f"Getting news from {source}")
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Getting news from {source}")
                try:
                    links[key][source] = get_links_and_content_from_page(source)
                    append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Successfully extracted news from {source}")
                    append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] *****************************************************")
                except Exception as e:
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] ************************ERROR************************")
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Failed to extract news from {source}: {e}")
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] *****************************************************")
                    # print("************************ERROR************************")
                    # print(f"Failed to extract news from {source} with error: {e}")
                    # print("*****************************************************")
            # print("\n\n")
            # print("--------------------------------------------")
            # # print(links)
            # print("--------------------------------------------")
            today_date = datetime.today().strftime('%Y-%m-%d')
            print(" IT'S HEREEEEEEEEEEEEEEEEEEEEEEEEEEEE")
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Before processing Processing category: {links} and length {len(links)}")
            links = self.grd_nws(links)
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] After processing Processing category: {links} and length {len(links)}")
            try:
                openai_links_db.insert_one({today_date:{key: links[key]}})
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Successfully inserted data for {key} into MongoDB")
            except Exception as e:
                append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_openai_assistant] Failed to insert data into MongoDB: {e}")
                print(f"Failed to insert data into MongoDB: {e}")
            # openai_links_db.insert_one({today_date:{key: links}})
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

    def check_news_in_db(self):
        openai_links_db = db['openai_api'] # Add to constructor
        today_date = datetime.today().strftime('%Y-%m-%d') #add to constructor
        print(today_date)
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] Checking news for date: {today_date}")
        
        news_data_cursor = openai_links_db.find({today_date: {"$exists": True}})
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
                summary = self.openai_api_request(f"Summarize the news from {link} with the title {title} and content {news_content}")   # Neeeds better prompt
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
        openai_links_db.insert_one({result_type:{datetime.today().strftime('%Y-%m-%d'): result}})


# content = check_news_in_db()
# run_sumarizing_threads()
# push_results_to_db(result)
    def fetch_todays_results(self):
        openai_links_db = db['openai_api']   # Add to constructor
        today_date = datetime.today().strftime('%Y-%m-%d')
        query = {f"Result.{today_date}": {"$exists": True}}
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
        today_date = datetime.today().strftime('%Y-%m-%d')
        for _, summary_response in self.summary.items():
                    # Extract the actual summary text from the OpenAI response
                    summary_text = summary_response.data[0].content[0].text.value
                    formatted_result[today_date] = summary_text
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


    def grd_nws(self, links):
        news = links
        summary = self.summary
        new_links = []
        result_links= []
        if news and summary:
            return None
        elif news:
            append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] News is present, starting grading")
            print("News is present start summary")
            for category, value in list(news.items()):
                for key in list(value.keys()):
                    links_to_remove = []
                    # for link in list(news[category][key].items()):
                    step = int(len(list(news[category][key].items()))/self.MAX_RETRY)
                    link_items = [ list(news[category][key].items())[j:j+step] for j in range(0, len(list(news[category][key].items())), step)]
                    append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Links for processing: {link_items}")
                    # link_part = [ links[j:j+step] for j in range(0, len(links), step)]
                    print(f"Link part is {link_items}")
                    # new_links = []
                    for link_item in link_items :
                        print("calling grading assistant")
                        new_links.append((self.grding_assistant(f"""
                            Is this news with title and content in list '{link_item}' relevant to category '{category}'? 
                            If yes, return the structured data in the format: 
                            [("https://www.example.com/article1", ["Article Title 1", "Article Content 1"]), ("https://www.example.com/article2", ["Article Title 2", "Article Content 2"])]
                            If no, return an empty list [].
                            """)).data[0].content[0].text.value)
                        # messages = self.grding_assistant(f"Is this news with title {news[category][key][link][0]} and content {news[category][key][link][1]} relevant to category {category}? Remove the unwanted article and return the useful list of articles.")
                        # grade = int(messages.data[0].content[0].text.value)
                        # append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Grading result: {grade}")
                    
                    # If all links in a category are removed, remove the category
                    # if not news[category][key]:
                    #     news.pop(key)
                    #     append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Removed empty category {key}")
                        print(f"New links {new_links}")
                        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing new_links: {new_links}")
                    # Process new_links and structure into result_links
                    result_links = {}
                    for i in range(len(new_links)):
                        try:
                            # Convert string representation of list to actual list
                            links_data = eval(new_links[i])
                            if links_data:  # Only process if links_data is not empty
                                if category not in result_links:
                                    result_links[category] = {}
                                if key not in result_links[category]:
                                    result_links[category][key] = {}
                                for link, content in links_data:
                                    result_links[category][key][link] = content
                        except Exception as e:
                            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Error processing new_links: {e}")

                    # print( f"Result links {result_links}")
                    # return result_links if result_links else None
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] News refined, here's list of new news : {result_links}")
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