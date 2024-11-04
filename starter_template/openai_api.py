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

# print(client.project)

# def main()->None:
    
#     list_assistant()
    
#     thread=client.beta.threads.create()

#     message = client.beta.threads.messages.create(
#         thread_id=thread.id,
#         role="user",
#         content="Create an HTML page with the title '{page_name}' and content 'Envisage - Creativity Meets Technology' in a sleek design."
#     )  

#     run = client.beta.threads.runs.create(
#         thread_id=thread.id,
#         assistant_id='asst_GLoqwMMQjih3ziyj8LQCrcAf',
#     )
#     print(run)

#     run = wait_on_run(run,thread)
#     print(run)


#     messages=client.beta.threads.messages.list(
#         thread_id=thread.id, order='asc', after=message.id,
#     )
#     print(messages)


def openai_api_request(txt):

    thread= client.beta.threads.create()
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=txt
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id='asst_GLoqwMMQjih3ziyj8LQCrcAf',
    )
    run = wait_on_run(run,thread)

    messages=client.beta.threads.messages.list(
        thread_id=thread.id, order='asc', after=message.id,
    )
    return messages



def wait_on_run(run,thread):
    while run.status=='queued' or run.status=='in_progress':
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
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


# if __name__ == "__main__":
#     main()