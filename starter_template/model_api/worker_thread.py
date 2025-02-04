import threading
from openai_api import start_openai_assistant
from claude_api import start_claude_assistant
import time

def run_openai_assistant():
    start_openai_assistant()
    print("OpenAI Completed : Check DB for updated result!")

def run_claude_assistant():
    start_claude_assistant()
    print("Claude Completed : Check DB for updated result!")

if __name__ == "__main__":
    program_start = time.time()
    thread1 = threading.Thread(target=run_openai_assistant)
    print("Creating OpenAI Assistant")
    thread2 = threading.Thread(target=run_claude_assistant)
    print("Creating Claude Assistant")

    thread1.start()
    print("Starting OpenAI Assistant")
    thread2.start()
    print("Starting Claude Assistant")

    thread1.join()
    thread2.join()

    program_end = time.time()
    total_execution_time = program_end - program_start

    print("************ All tasks completed ************")
    print("*********************************************")
    print(f"\nTotal Program Execution Time: {total_execution_time:.2f} seconds")
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