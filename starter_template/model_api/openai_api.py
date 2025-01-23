from openai import OpenAI
import os
import json
import time
from dotenv import load_dotenv



load_dotenv()
client=OpenAI(
    organization=os.getenv('ORG'),
    project=os.getenv('PROJ'),
    api_key=os.getenv('OPENAI_API_KEY')
)

print(os.getenv('PROJ'))



def openai_api_request(txt):
    thread = client.beta.threads.create()
    print(f"Thread created: {thread.id}")  # Debugging line

    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=txt
    )
    print(f"Message created: {message.id}")  # Debugging line

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id='asst_WqxlAhEY2ktg9mj5fGHqvNaq',
    )
    print(f"Run created: {run.id}")  # Debugging line

    run = wait_on_run(run, thread)
    
    if run.status == 'requires_action':
        print(f"Tool name {run.tools[1].function.name}")
        # print(f"Tool id {run.tools[1].function}")
        run = client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=[{"tool_call_id": tool.id, "output": "true"} for tool in run.tools]
        )

        print(f"Run requires action: {run}")  # Debugging line

    messages = client.beta.threads.messages.list(
        thread_id=thread.id, order='asc', after=message.id,
    )
    print(f"Messages: {messages}")  # Debugging line
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
    

###########################
## Streaming the output using Event handler
###########################
# class EventHandler(AssistantEventHandler):
#     @override
#     def on_text_created(self,text)->None:
#         print(f"\nAssistant", end="", flush=true)

#     @override
#     def on_text_delta(self, delta, snapshot):
#         print(delta.value, end="", flush=True)

#     def on_tool_call_created(self, tool_call):
#         print(f"asssistant > {tool.call.type}\n", flush=True)

#     def on_tool_call_delta(self, delta, snapshot):
#         if delta.type == 'code_interpreter':
#             if delta.code_interpreter.input:
#                 print(delta.code_interpreter.input, end="", flush=True)
#             if delta.code_interpreter.outputs:
#                 print(f"\n\noutput >", flush=True)
#                 for output in delta.code_interpreter.outputs:
#                     if output.type == "logs":
#                         print(f"\n{output.logs}", flush=True)


###########################
## Logic to run the stream
###########################
# with client.beta.threads.run.stream(
#     thread_id=thread.id,
#     assistant_id=assistant.id,
#     instructions="Please address the user as Jane Doe. The user has a premium account.",
#     event_handler=EventHandler(),
# ) as stream:
#     stream.until_done()


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



def get_todays_news() -> None:
    response = openai_api_request("Get today's news from google")
    if response:
        print(response)
    else:
        print("Failed to get news")

get_todays_news()