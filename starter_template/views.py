from django.shortcuts import render, redirect
from django.http import HttpResponse
import os
import openai
from .model_api import openai_api as api, file_operations as fo 
from . import urls 

# For managing generated pages
generated_pages = []
for filename in os.listdir(os.path.join((os.path.dirname(os.path.abspath(__file__))), "templates")):
    if filename.endswith(".html"):
        generated_pages.append(filename)





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
    return render(request, 'homepage.html', {'pages': generated_pages})





"""
    get_page(request):
        Handles the creation of a new HTML page using OpenAI API and redirects to the homepage.
        Args:
            request: The HTTP request object containing metadata about the request.
        Returns:
            A redirect to the homepage view.
"""
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


def chat_with_function_calling(user_message: str):
    functions = [
        {
            "name": "fetch_web_data",
            "description": "Fetch real-time data from a given web URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL of the webpage"},
                },
                "required": ["url"],
            },
        }
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": user_message}],
        functions=functions,
        function_call="auto",
    )

    response_message = response["choices"][0]["message"]

    if response_message.get("function_call"):
        function_name = response_message["function_call"]["name"]
        function_args = json.loads(response_message["function_call"]["arguments"])
        if function_name == "fetch_web_data":
            function_response = fetch_web_data(**function_args)
            return function_response
    
    return response_message["content"]

# Example usage
print(chat_with_function_calling("Get data from https://example.com"))
