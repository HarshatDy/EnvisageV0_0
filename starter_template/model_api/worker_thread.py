import threading
from openai_api import  OpenAiAPI
from claude_api import start_claude_assistant
import time
from logging_scripts import create_log_file, append_to_log
from datetime import datetime

client = OpenAiAPI()

def get_openai_client():
    return client

def run_openai_assistant(client):
    # openai_api = get_openai_client()
    client.start_openai_assistant()
    print("OpenAI Completed : Check DB for updated result!")


def summarize():
    # client = get_openai_client()
    client.fetch_content_and_run_summary()
    print("OpenAI Completed : Check DB for updated result!")

def check_news():
    return client.chk_news()

def check_results():
    return client.chk_results()

def check_summary():
    return client.chk_summary()

# def run_claude_assistant():
#     start_claude_assistant()
#     print("Claude Completed : Check DB for updated result!")

if __name__ == "__main__":
    log_file =f"log_{time.strftime('%Y_%m_%d')}_threading.txt"
    create_log_file(log_file)
    nws_flg, rslt_flg, sum_flg = True, True, True
    program_start = time.time()
    news_list = check_news()
    for i in news_list:
        if i:
            nws_flg = True
        else :
            nws_flg = False

    if not nws_flg :
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] NEWS CHECK FAILED")
        thread1 = threading.Thread(target=run_openai_assistant)
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] CREATING THREAD FOR NEWS")
        # print("Creating OpenAI Assistant")
        # thread2 = threading.Thread(target=run_claude_assistant)
        # append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] Creating Claude Assistant")
        # print("Creating Claude Assistant")

        thread1.start()
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] STARTING NEWS THREAD")
        print("Starting OpenAI Assistant")
        # thread2.start()
        # append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] Starting Claude Assistant")
        # print("Starting Claude Assistant")
        thread1.join()
    # thread2.join()
        program_end = time.time()
        total_execution_time = program_end - program_start
    else:
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] NEWS CHECK SUCCESSFULL ")

    
    if not check_results():
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] RESULTS CHECK FAILED")
        thread2 = threading.Thread(target=summarize)
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] CREATING THREAD FOR RESULTS")
        # print("Creating OpenAI Assistant")
        # thread2 = threading.Thread(target=run_claude_assistant)
        # append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] Creating Claude Assistant")
        # print("Creating Claude Assistant")
        thread2.start()
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] STARTING RESULTS THREAD")
        print("Starting OpenAI Assistant")
        # thread2.start()
        # append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] Starting Claude Assistant")
        # print("Starting Claude Assistant")

        thread2.join()
    # thread2.join()
        program_end = time.time()
        total_execution_time = program_end - program_start
    else:
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] RESULTS CHECK SUCCESSFULL ")
    
    if not check_summary():
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] SUMMARY CHECK FAILED")
        thread3 = threading.Thread(target=summarize)
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] CREATING THREADS FOR SUMMARY")
        # print("Creating OpenAI Assistant")
        # thread2 = threading.Thread(target=run_claude_assistant)
        # append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] Creating Claude Assistant")
        # print("Creating Claude Assistant")
        thread3.start()
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] STARTING SUMMARY THREAD")
        print("STARTING SUMMARY THREAD")
        # thread2.start()
        # append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] Starting Claude Assistant")
        # print("Starting Claude Assistant")

        thread3.join()
    # thread2.join()
        program_end = time.time()
        total_execution_time = program_end - program_start
    else:
        append_to_log(log_file, f"[WORKER_THREAD][INF][{datetime.today().strftime('%H:%M:%S')}] SUMMARY CHECK SUCCESSFULL ")
    

    append_to_log(log_file, "[INF] All tasks completed")
    print("************ All tasks completed ************")
    append_to_log(log_file, "[INF] ************ All tasks completed ************")
    # append_to_log(log_file, f"[INF] Total Program Execution Time: {total_execution_time:.2f} seconds")
    # append_to_log(log_file, "[INF] *********************************************")
    # print("*********************************************")
    # print(f"\nTotal Program Execution Time: {total_execution_time:.2f} seconds")
    print("*********************************************")


    # barrier = threading.Barrier(4)

    # def run_openai_assistant_with_barrier():
    #     run_openai_assistant()
    #     barrier.wait()

    # def run_claude_assistant_with_barrier():
    #     run_claude_assistant()
    #     barrier.wait()

    # def run_additional_task_1():
    #     # Placeholder for additional task 1
    #     print("Additional Task 1 Completed")
    #     barrier.wait()

    # def run_additional_task_2():
    #     # Placeholder for additional task 2
    #     print("Additional Task 2 Completed")
    #     barrier.wait()

    # thread3 = threading.Thread(target=run_additional_task_1)
    # print("Creating Additional Task 1")
    # thread4 = threading.Thread(target=run_additional_task_2)
    # print("Creating Additional Task 2")

    # thread1 = threading.Thread(target=run_openai_assistant_with_barrier)
    # print("Creating OpenAI Assistant with Barrier")
    # thread2 = threading.Thread(target=run_claude_assistant_with_barrier)
    # print("Creating Claude Assistant with Barrier")

    # thread1.start()
    # print("Starting OpenAI Assistant with Barrier")
    # thread2.start()
    # print("Starting Claude Assistant with Barrier")
    # thread3.start()
    # print("Starting Additional Task 1")
    # thread4.start()
    # print("Starting Additional Task 2")

    # thread1.join()
    # thread2.join()
    # thread3.join()
    # thread4.join()

    # print("All tasks completed")