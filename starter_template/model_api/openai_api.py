from openai import OpenAI
import os
import json
import time
from dotenv import load_dotenv
from web_scrapper_api import get_links_and_content_from_page
from mongo import db
from datetime import datetime
from threading import Thread, Lock
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
                "https://www.climatechangenews.com/",
                "https://insideclimatenews.org/",
                "https://www.technologyreview.com/topic/climate-change/",
                "https://www.bloomberg.com/green",
                "https://www.theguardian.com/environment/climate-crisis"
            ],
            "Government Politics": [
                "https://www.politico.com/news/climate-energy",
                "https://www.bbc.com/news/politics",
                "https://www.reuters.com/business/environment/",
                "https://www.nytimes.com/section/climate",
                "https://www.ft.com/climate-capitalism",
                "https://www.eenews.net/"
            ],
            "Travel Industry": [
                "https://skift.com/",
                "https://www.cnbc.com/travel/",
                "https://www.travelweekly.com/",
                "https://www.cntraveler.com/story-type/news",
                "https://www.iata.org/en/pressroom/",
                "https://www.phocuswire.com/"
            ],
            "Stock Market": [
                "https://www.bloomberg.com/markets",
                "https://www.ft.com/markets",
                "https://www.cnbc.com/markets/",
                "https://www.wsj.com/market-data",
                "https://www.marketwatch.com/investing/esg",
                "https://www.morningstar.com/lp/sustainable-investing"
            ]
        }
        return news_sources




    def openai_api_request(self, txt):
        
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Recieved OPENAI request for content {txt}")
        thread = self.client.beta.threads.create()  # Create a new thread
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
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] Failed run : {run}")
            raise Exception(f"Run failed or stopped with error: {run}")
        while run.status == 'requires_action':  # Handle required actions if the run status is 'requires_action'
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Tool name: {run.required_action.submit_tool_outputs.tool_calls[0].id}")
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
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Messages retrieved from thread: {messages}")
        # print(f"Messages: {messages}")  # Debugging line
        return messages



    def wait_on_run(self, run, thread):
        while run.status=='queued' or run.status=='in_progress':
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Run status: {run.status}")
            # print(f"Run status: {run.status}")  # Debugging line
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            time.sleep(0.5)
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Run status after completion: {run.status}, Run ID: {run.id}")
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
        
        append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] Starting OpenAI Assistant")
        news_sources = self.get_news_src()
        for key in news_sources:
            links={}
            # print(f"News for {key}")
            for source in news_sources[key]:
                # print(f"Getting news from {source}")
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] Getting news from {source}")
                try:
                    links[source] = get_links_and_content_from_page(source)
                except Exception as e:
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] ************************ERROR************************")
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] Failed to extract news from {source}: {e}")
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] *****************************************************")
                    # print("************************ERROR************************")
                    # print(f"Failed to extract news from {source} with error: {e}")
                    # print("*****************************************************")
            # print("\n\n")
            # print("--------------------------------------------")
            # # print(links)
            # print("--------------------------------------------")
            today_date = datetime.today().strftime('%Y-%m-%d')
            try:
                openai_links_db.insert_one({today_date:{key: links}})
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] Successfully inserted data for {key} into MongoDB")
            except Exception as e:
                append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] Failed to insert data into MongoDB: {e}")
                print(f"Failed to insert data into MongoDB: {e}")
            # openai_links_db.insert_one({today_date:{key: links}})
        # print("News retrieval complete")
        append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] News retrieval complete")
        # client.close()
        # print(links)
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
        today_date = datetime.today().strftime('%Y-%m-%d')
        print(today_date)
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Checking news for date: {today_date}")
        
        news_data_cursor = openai_links_db.find({today_date: {"$exists": True}})
        collected_news = {}
        
        for news_data in news_data_cursor:
            # print("ITS HERE")
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Found news data in database {news_data}")
            
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
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] No news data found for today in the database")

        return collected_news

# print(f" NEWS are present {check_news_in_db()}")
    def process_category(self, category, sources):
        result = {}
        for source, content in sources.items():
            # print(f"Processing news from {source} in category {category}")
            for link, details in content.items():
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] LINK from the news: {link}")
                # write_to_file(str(details), "details.txt")
                if len(details) != 2:
                    append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] Skipping link {link} as it has insufficient details")
                    print(f"Skipping link {link} as it has insufficient details")
                    continue
                title, news_content = details
                # exit()
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Processing summary for {link} with title: {title}")
                summary = self.openai_api_request(f"Summarize the news from {link} with the title {title} and content {news_content}")   # Neeeds better prompt
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Summary result: {summary.data[0].content[0].text.value}")
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
                    append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Thread acquired lock for {result[category]}") # Check with result.category.title
                    self.thread_result[category] = result
                # write_to_file(result, "result.txt")

    def run_sumarizing_threads(self)-> None:
        threads = []
        self.thread_result.clear()
        content = self.check_news_in_db()
        if not content:
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] No content found in database")
            return None
        for category, sources in content.items():
            thread = Thread(target=self.process_category, args=(category, sources))
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Starting thread")
            threads.append(thread)
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Starting thread for {category} with {thread.ident}")
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
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] No results found in MongoDB for today's date")
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Fetching today's results from MongoDB: {results_cursor}")
        # print("executing loop now")
        result_json = None
        for result in results_cursor:
            # print("IN LOOP")
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Query result: {result['_id']}")
            # Convert ObjectId to string representation
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Processing result: {result['_id']}")
            # print(result)
            result['_id'] = str(result['_id'])
            result_json =json.dumps(result, indent=4)
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Result JSON: {result_json}")
        return result_json



# run_sumarizing_threads()
# if thread_result:
#     push_results_to_db(thread_result)
#     append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] Successfully pushed summarized results to MongoDB")
    def fetch_content_and_run_summary(self)->None:  # Create checks to see if previous work has been completed before proceeding
        result_json = self.fetch_todays_results()
        if not result_json:
            append_to_log(self.log_file, f"[OPENAI][ERR][{datetime.today().strftime('%H:%M:%S')}] No results found for today")
            self.run_sumarizing_threads() #Summarizing each news individually
            if self.thread_result:
                self.push_results_to_db(self.thread_result, "Result")
                append_to_log(self.log_file, f"[OPENAI][INF][{datetime.today().strftime('%H:%M:%S')}] Successfully pushed summarized results to MongoDB")
            else:
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] No thread_result found, nothing to push to MongoDB")
        else: #Summarizing the whole thing
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Result JSON length: {len(result_json)}")
            append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Result : {result_json}")
            result_length = len(result_json)
            json_parts =  []

            if result_length > 256000:
                json_parts = [result_json[i:i+255733] for i in range(0, len(result_json), 255733)]
            else:
                json_parts.append(result_json)
            
            for json_part in json_parts:
                content=f"""Please analyze this news data and create:
                1. Key bullet points for each category
                2. Important trends or patterns
                3. A brief executive summary
                4. Highlight any critical developments
                Data: {json_part}"""
                self.summary[json_part] = self.openai_api_request(content)
            if bool(self.summary):
                append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] SUMMARY IS PRESENT")
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
        append_to_log(self.log_file, f"[OPENAI][DBG][{datetime.today().strftime('%H:%M:%S')}] Successfully pushed summary to MongoDB")


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