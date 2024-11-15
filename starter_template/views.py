from django.shortcuts import render, redirect
from django.http import HttpResponse
import os
import openai
from . import openai_api as api, file_operations as fo 
from . import urls 

# For managing generated pages
generated_pages = []
for filename in os.listdir(os.path.join((os.path.dirname(os.path.abspath(__file__))), "templates")):
    if filename.endswith(".html"):
        generated_pages.append(filename)




def homepage(request):
    return render(request, 'homepage.html', {'pages': generated_pages})


def get_page(request):

    page_name = request.POST.get('page_name')
    print(f" THe requested paage is {page_name}")

    # Get the page name from the request #### TODO : make this available from openai api
    content=f"Create an HTML page with the title {page_name} and content 'Envisage - Creativity Meets Technology' in a sleek design."
    content = api.openai_api_request(content)
    # print(content.data[0].content[0].text.value) ## print the content of the output form openai API.
    
    ################################ ---> Create a new URL and get the prints
    
    path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(path, "templates")
    
    # filename  = request.GET.get('page_name') ## Get the content from POST request.
    # print(f"{path} {page_name} THIS IS THE OUTPUT PUT") ## print the file directory and the file name

    fo.create_file(path, page_name)
    fo.write_file(path, page_name, content.data[0].content[0].text.value)

    generated_pages.append(page_name+".html")

    return redirect('homepage')


def show_generated_page(request, page_name):
    return render(request, f'{page_name}', {'page_name' :page_name})
