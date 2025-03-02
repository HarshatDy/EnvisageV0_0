from django.shortcuts import render, redirect
from django.http import HttpResponse
import os
import openai
# from .model_api import openai_api as api
from .model_api.mongo import db
from .model_api.worker_thread import *
from . import urls 
from datetime import datetime
import random

from threading import Thread
# For managing generated pages

generated_pages = check_all_dates()

"""
This module contains views for the Envisage application.

Functions:
    homepage(request):
        Renders the homepage with a list of generated pages.
    get_page(request):
        Handles the creation of a new HTML page using OpenAI API and redirects to the homepage.
    show_generated_page(request, page_name):
        Renders a generated HTML page based on the provided page name.
"""
def homepage(request):
    # chk_news_content()
    openai_mongo = db['openai_api']

    pipeline = [
        {"$match": {"Summary": {"$exists": True}}},
        {"$project": {"_id": 0, "summaries": {"$objectToArray": "$Summary"}}},
        {"$unwind": "$summaries"},
        {"$project": {"date": "$summaries.k", "content": "$summaries.v"}}
    ]
    summary_docs = list(openai_mongo.aggregate(pipeline))
    

    if not summary_docs:
        return render(request, 'homepage_1.html', {
            'news_content': 'No news content available', 
            'pages': generated_pages,
            'summary_date': 'N/A'
        })
    
    if len(summary_docs) == 1:
        random_summary1 = random_summary2 = summary_docs[0]
    else:
        # Select two different summaries
        indices = random.sample(range(len(summary_docs)), 2)
        random_summary1 = summary_docs[indices[0]]
        random_summary2 = summary_docs[indices[1]]
    
     # Process the first summary
    summary_date1 = random_summary1['date']
    try:
        # If your structure is Summary -> date -> date -> content
        news_content1 = random_summary1['content'][summary_date1][summary_date1]
    except (KeyError, TypeError):
        try:
            # Alternative structure: Summary -> date -> content
            news_content1 = random_summary1['content'][summary_date1]
        except (KeyError, TypeError):
            news_content1 = "Error retrieving content for this summary"
    
    # Process the second summary
    summary_date2 = random_summary2['date']
    try:
        # If your structure is Summary -> date -> date -> content
        news_content2 = random_summary2['content'][summary_date2][summary_date2]
    except (KeyError, TypeError):
        try:
            # Alternative structure: Summary -> date -> content
            news_content2 = random_summary2['content'][summary_date2]
        except (KeyError, TypeError):
            news_content2 = "Error retrieving content for this summary"
    
    return render(request, 'homepage_1.html', {
        'summary1': news_content1, 
        'summary2': news_content2,
        'summary_date1': summary_date1,
        'summary_date2': summary_date2,
        'pages': generated_pages
    })
    # return render(request, 'homepage_1.html', {'news_content': 'No news content available', 'pages': generated_pages})




"""
    get_page(request):
        Handles the creation of a new HTML page using OpenAI API and redirects to the homepage.
        Args:
            request: The HTTP request object containing metadata about the request.
        Returns:
            A redirect to the homepage view.
"""
# def get_page(request): #Marking for removal

#     page_name = request.POST.get('page_name')
#     print(f" THe requested paage is {page_name}")

#     # Get the page name from the request #### TODO : make this available from openai api
#     content=f"Create an HTML page with the title {page_name} and content 'Envisage - Creativity Meets Technology' in a sleek design."
#     content = api.openai_api_request(content)
#     # print(content.data[0].content[0].text.value) ## print the content of the output form openai API.
    
#     ################################ ---> Create a new URL and get the prints
    
#     path = os.path.dirname(os.path.abspath(__file__))
#     path = os.path.join(path, "templates")
    
#     # filename  = request.GET.get('page_name') ## Get the content from POST request.
#     # print(f"{path} {page_name} THIS IS THE OUTPUT PUT") ## print the file directory and the file name

#     # fo.create_file(path, page_name)
#     # fo.write_file(path, page_name, content.data[0].content[0].text.value)

#     generated_pages.append(page_name+".html")

#     return redirect('homepage')



"""
    show_generated_page(request, page_name):
        Renders a generated HTML page based on the provided page name.
        Args:
            request: The HTTP request object containing metadata about the request.
            page_name: The name of the generated HTML page to be rendered.
        Returns:
            An HttpResponse object containing the rendered HTML page.
"""
def show_generated_page(request, page_name):
    return render(request, f'{page_name}', {'page_name' :page_name})



def chk_news_content():
    background_thread = Thread(target=run_worker_thread, daemon=True)
    background_thread.start()
    print(f"Background thread started at {datetime.today().strftime('%H:%M:%S')}")  
    return None