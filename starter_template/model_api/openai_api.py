from openai import OpenAI
import os
import json
import time
from dotenv import load_dotenv
from web_scrapper_api import get_links_and_content_from_page
from mongo import db
from datetime import datetime




load_dotenv()
client=OpenAI(
    organization=os.getenv('ORG'),
    project=os.getenv('PROJ'),
    api_key=os.getenv('OPENAI_API_KEY')
)

print(os.getenv('PROJ'))


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




def openai_api_request(txt):
    """
    Sends a request to the OpenAI API and processes the response.

    This function creates a new thread, sends a message to the thread, initiates a run,
    waits for the run to complete, and handles any required actions. Finally, it retrieves
    and returns the list of messages from the thread.

    Args:
        txt (str): The content of the message to be sent to the OpenAI API.

    Returns:
        list: A list of messages from the thread after processing the run.

    Raises:
        Exception: If there is an error in creating the thread, message, or run, or if the run
                   requires an action that cannot be completed.
    """

    thread = client.beta.threads.create()  # Create a new thread
    # print(f"Thread created: {thread.id}")  # Debugging line
    message = client.beta.threads.messages.create(  # Create a new message in the thread
        thread_id=thread.id,
        role="user",
        content=txt
    )
    # print(f"Message created: {message.id}")  # Debugging line
    run = client.beta.threads.runs.create(  # Create a new run in the thread
        thread_id=thread.id,
        assistant_id='asst_WqxlAhEY2ktg9mj5fGHqvNaq',
    )
    # print(f"Run created: {run.id}")  # Debugging line
    run = wait_on_run(run, thread)
    while run.status == 'requires_action':  # Handle required actions if the run status is 'requires_action'
        print(f"Tool name {run.required_action.submit_tool_outputs.tool_calls[0].id}")  # Debugging line
        run = client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=[{"tool_call_id": run.required_action.submit_tool_outputs.tool_calls[0].id, "output": "true"}]
        )
        wait_on_run(run, thread)  # Wait for the run to complete
        print(f"FINAL Run requires action: {run.status}")  # Debugging line
    messages = client.beta.threads.messages.list(
        thread_id=thread.id, order='asc', after=message.id,
    )
    # print(f"Messages: {messages}")  # Debugging line
    return messages



def wait_on_run(run,thread):
    while run.status=='queued' or run.status=='in_progress':
        print(f"Run status: {run.status}")  # Debugging line
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    print(f"Run status after completion: {run.status}")  # Debugging line
    return run
    

def list_assistant():
    my_assistant= client.beta.assistants.list(
        order="desc",
        limit="4",
    )
    print(my_assistant.data)




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

new_list = []

def get_todays_news() -> None:
    for key in news_sources:
        print(f"News for {key}")
        for source in news_sources[key]:
            print(f"Getting news from {source}")
            response = openai_api_request(f"Get today's news from {source} in 350 words")
            if response:
                new_list.append(response.data[0].content[0].text.value)
                print(response.data[0].content[0].text.value)
            else:
                print("Failed to get news")
        print("\n\n")
    print("News retrieval complete")




# get_todays_news()
links={}
openai_links_db = db['openai_api']

for key in news_sources:
    print(f"News for {key}")
    for source in news_sources[key]:
        print(f"Getting news from {source}")
        try:
            links[source] = get_links_and_content_from_page(source)
        except Exception as e:
            print("************************ERROR************************")
            print(f"Failed to extract news from {source} with error: {e}")
            print("*****************************************************")
    print("\n\n")
    print("--------------------------------------------")
    print(links)
    print("--------------------------------------------")
    today_date = datetime.today().strftime('%Y-%m-%d')
    openai_links_db.insert_one({today_date: links})
print("News retrieval complete")

print(links)
exit()

for key in links:
    print(f"Content from {key}")
    for link in links[key]:
        print(f"Title: {links[key][link][0]}")
        print(f"Content: {links[key][link][1]}")
        content = openai_api_request(f"Summarize the news from {link} with the title {links[key][link][0]} and content {links[key][link][1]}")
        print("Summary:")
        print(content.data[0].content[0].text.value)
    print("\n\n")