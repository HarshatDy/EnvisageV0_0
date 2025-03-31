import os
import json
import time
from threading import Thread, Lock
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv

# Handle imports for both Django and standalone execution
try:
    # Try relative imports (for Django)
    from .web_scrapper_test_time_based import get_links_and_content_from_page
    from .mongo import db
    from .logging_scripts import *
    from .hugging_face_api_enhanced import check_url_content_relevance, categorize_content, summarize_articles
except ImportError:
    try:
        # Try absolute imports (for standalone script)
        from web_scrapper_test_time_based import get_links_and_content_from_page
        from mongo import db
        from logging_scripts import *
        from hugging_face_api_enhanced import check_url_content_relevance, categorize_content, summarize_articles
    except ImportError:
        print("Warning: Could not import some modules. Some functionality may be limited.")
        # Define fallback or dummy functions/variables if needed
        db = {}

from google import genai
import google.generativeai as google_genai
# from genai import types


class GeminiAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.client = genai.Client(api_key=self.api_key)
        
        self.today_now = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"gemini_{self.today_now}_log.txt"
        try:
            create_log_file(self.log_file)
        except NameError:
            print(f"Warning: create_log_file function not available. Log file {self.log_file} not created.")
        
        self.thread_lock = Lock()
        self.thread_result = {}
        self.summary = {}
        self.db = db['gemini_api']
        
        # Modified to use the new date format with time constraint
        self.today_date = self._get_date_with_time_constraint()
        
        self.MAX_RETRY = 5
        self.MAX_BATCHES = 5
        self.user_personalized_urls = {}
        
        # Initialize model
        # self.model = genai.GenerativeModel('gemini-pro')

    def _get_date_with_time_constraint(self):
        """
        Determine the current time constraint and create a date string with it.
        
        Returns:
            str: Date string with time constraint in format 'YYYY-MM-DD_HH:00'
                Example: '2023-06-15_06:00' or '2023-06-15_18:00'
        """
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Set time constraints based on current time
        if 6 <= current_hour < 18:  # Between 6am and 6pm
            # Morning to evening constraint - use 18:00 (6pm) of current day
            constraint_date = current_time.strftime('%Y-%m-%d')
            constraint_time = "18:00"
        else:  # Between 6pm and 6am
            if current_hour >= 18:  # Evening (6pm to midnight)
                # Evening to next morning constraint - use 06:00 (6am) of next day
                next_day = current_time + timedelta(days=1)
                constraint_date = next_day.strftime('%Y-%m-%d')
                constraint_time = "06:00"
            else:  # Early morning (midnight to 6am)
                # Previous evening to morning constraint - use 06:00 (6am) of current day
                constraint_date = current_time.strftime('%Y-%m-%d')
                constraint_time = "06:00"
        
        date_with_constraint = f"{constraint_date}_{constraint_time}"
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][_get_date_with_time_constraint] Date with time constraint: {date_with_constraint}")
        
        return date_with_constraint

    def get_personalized_news_sources(self, categories):
        """
        Get personalized news sources based on user-provided categories.
        
        Args:
            categories (list): List of strings representing content categories
                Example: ['Technology', 'Business', 'Health']
        
        Returns:
            dict: Dictionary mapping categories (str) to lists of URL strings
                Example: {'Technology': ['https://www.techcrunch.com/', 'https://www.wired.com/'], 
                          'Business': ['https://www.forbes.com/', 'https://www.bloomberg.com/']}
        """
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][get_personalized_news_sources] Getting personalized news sources for categories: {categories}")
        
        # Format the categories for the prompt
        categories_str = ", ".join(categories)
        
        prompt = f"""
        I need a list of reliable news sources (URLs) for the following categories: {categories_str}.
        
        Please return your response as a Python dictionary where:
        - Each key is one of the categories provided
        - Each value is a list of 10-15 legitimate news website URLs for that category
        - Only include URLs for major, reputable news sources
        - Include only the domain part of the URLs (e.g., "https://www.example.com/")
        - Do not include any explanations or notes in your response
        
        Format the response as a valid Python dictionary.
        """
        
        try:
            response = self.openai_api_request(prompt)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][get_personalized_news_sources] Received response from API")
            
            response_text = response.text
            # Remove markdown formatting if present
            if "```python" in response_text:
                response_text = response_text.split("```python")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Convert string to Python dictionary
            self.user_personalized_urls = eval(response_text)
            
            # Log the result
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][get_personalized_news_sources] Successfully generated personalized URLs: {self.user_personalized_urls}")
            
            return self.user_personalized_urls
            
        except Exception as e:
            append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][get_personalized_news_sources] Error generating personalized URLs: {str(e)}")
            exit(0)
            # Return an empty dictionary if there's an error
            return {}
    
    def get_news_src(self):
        """
        Provides a predefined dictionary of news sources categorized by topic.
        
        Args:
            None
        
        Returns:
            dict: Dictionary mapping category names (str) to lists of URL strings
                Example: {'new_source_1': ['https://www.techcrunch.com/', ...], 
                          'new_source_2': ['https://www.forbes.com/', ...]}
        """
        news_sources ={
  "new_source_1": [  # Politics
    "https://www.ndtv.com/",
    "https://www.indiatoday.in/",
    "https://www.hindustantimes.com/",
    "https://www.scroll.in/",
    "https://www.thehindu.com/",
    "https://www.bbc.com/news/politics",
    "https://www.nytimes.com/section/politics",
    "https://www.washingtonpost.com/politics/",
    "https://www.reuters.com/politics",
    "https://www.cnn.com/politics"
  ],
  "new_source_2": [  # Business
    "https://www.moneycontrol.com/",
    "https://www.livemint.com/",
    "https://www.business-standard.com/",
    "https://www.economictimes.indiatimes.com/",
    "https://www.financialexpress.com/",
    "https://www.bbc.com/news/business",
    "https://www.nytimes.com/section/business",
    "https://www.wsj.com/news/business",
    "https://www.reuters.com/markets",
    "https://www.cnbc.com/business/"
  ],
  "new_source_3": [  # Economy
    "https://www.moneycontrol.com/",
    "https://www.livemint.com/",
    "https://www.business-standard.com/",
    "https://www.economictimes.indiatimes.com/",
    "https://www.financialexpress.com/",
    "https://www.bbc.com/news/business",
    "https://www.nytimes.com/section/business",
    "https://www.wsj.com/news/business",
    "https://www.reuters.com/markets",
    "https://www.cnbc.com/business/"
  ],
  "new_source_4": [  # Finance
    "https://www.moneycontrol.com/",
    "https://www.livemint.com/",
    "https://www.business-standard.com/",
    "https://www.economictimes.indiatimes.com/",
    "https://www.financialexpress.com/",
    "https://www.bbc.com/news/business",
    "https://www.nytimes.com/section/business",
    "https://www.wsj.com/news/business",
    "https://www.reuters.com/markets",
    "https://www.cnbc.com/business/"
  ],
  "new_source_5": [  # Health
    "https://www.healthline.com/",
    "https://www.webmd.com/",
    "https://www.mayoclinic.org/",
    "https://www.who.int/",
    "https://www.cdc.gov/",
    "https://www.bbc.com/news/health",
    "https://www.nytimes.com/section/health",
    "https://www.reuters.com/health",
    "https://www.medicalnewstoday.com/",
    "https://www.nih.gov/"
  ],
  "new_source_6": [  # Science
    "https://www.scientificamerican.com/",
    "https://www.nationalgeographic.com/",
    "https://www.newscientist.com/",
    "https://www.sciencealert.com/",
    "https://www.bbc.com/news/science_and_environment",
    "https://www.nytimes.com/section/science",
    "https://www.washingtonpost.com/science/",
    "https://www.reuters.com/science",
    "https://www.nature.com/",
    "https://www.sciencedaily.com/"
  ],
  "new_source_7": [  # Technology
    "https://www.techcrunch.com/",
    "https://www.theverge.com/",
    "https://www.wired.com/",
    "https://www.cnet.com/",
    "https://www.bbc.com/news/technology",
    "https://www.nytimes.com/section/technology",
    "https://www.reuters.com/technology",
    "https://www.cnbc.com/technology/",
    "https://www.engadget.com/",
    "https://www.zdnet.com/"
  ],
  "new_source_8": [  # Environment
    "https://www.worldwildlife.org/",
    "https://www.greenpeace.org/",
    "https://www.nature.org/",
    "https://www.bbc.com/news/science_and_environment",
    "https://www.nytimes.com/section/climate",
    "https://www.washingtonpost.com/climate-environment/",
    "https://www.reuters.com/environment",
    "https://www.scientificamerican.com/environment/",
    "https://www.environmentaldefensefund.org/",
    "https://www.climatecentral.org/"
  ],
  "new_source_9": [  # Education
    "https://www.edutopia.org/",
    "https://www.thetechedvocate.org/",
    "https://www.education.com/",
    "https://www.teachthought.com/",
    "https://www.bbc.com/news/education",
    "https://www.nytimes.com/section/education",
    "https://www.washingtonpost.com/education/",
    "https://www.reuters.com/education",
    "https://www.educationworld.com/",
    "https://www.theteachingchannel.org/"
  ],
  "new_source_10": [  # Sports
    "https://www.espn.com/",
    "https://www.sports.yahoo.com/",
    "https://www.sportingnews.com/",
    "https://www.cricbuzz.com/",
    "https://www.bbc.com/sport",
    "https://www.nytimes.com/section/sports",
    "https://www.washingtonpost.com/sports/",
    "https://www.reuters.com/sports",
    "https://www.sportsillustrated.com/",
    "https://www.foxsports.com/"
  ],
  "new_source_11": [  # Entertainment
    "https://www.hollywoodreporter.com/",
    "https://www.variety.com/",
    "https://www.rollingstone.com/",
    "https://www.billboard.com/",
    "https://www.bbc.com/news/entertainment_and_arts",
    "https://www.nytimes.com/section/arts",
    "https://www.washingtonpost.com/entertainment/",
    "https://www.reuters.com/entertainment",
    "https://www.eonline.com/",
    "https://www.tmz.com/"
  ],
  "new_source_12": [  # Culture
    "https://www.smithsonianmag.com/",
    "https://www.theatlantic.com/culture/",
    "https://www.nationalgeographic.com/culture/",
    "https://www.bbc.com/news/magazine",
    "https://www.nytimes.com/section/magazine",
    "https://www.washingtonpost.com/magazine/",
    "https://www.reuters.com/lifestyle/culture",
    "https://www.theguardian.com/culture",
    "https://www.newyorker.com/culture",
    "https://www.politico.com/culture"
  ],
  "new_source_13": [  # Lifestyle
    "https://www.marthastewart.com/",
    "https://www.oprah.com/",
    "https://www.goop.com/",
    "https://www.bbc.com/news/magazine",
    "https://www.nytimes.com/section/style",
    "https://www.washingtonpost.com/lifestyle/",
    "https://www.reuters.com/lifestyle",
    "https://www.elle.com" ,
  ],
  "new_source_14": [  # Travel
    "https://www.lonelyplanet.com/",
    "https://www.tripadvisor.in/",
    "https://www.cntraveler.com/",
    "https://www.nytimes.com/section/travel",
    "https://www.bbc.com/travel",
    "https://www.indiatimes.com/travel",
    "https://www.makemytrip.com/",
    "https://www.cleartrip.com/",
    "https://www.yatra.com/",
    "https://www.expedia.co.in/"
  ],
  "new_source_15": [  # Food
    "https://www.foodnetwork.com/",
    "https://www.allrecipes.com/",
    "https://www.seriouseats.com/",
    "https://www.bbc.com/food",
    "https://www.nytimes.com/section/food",
    "https://www.food52.com/",
    "https://www.tasteofhome.com/",
    "https://www.epicurious.com/",
    "https://www.spoonforkbacon.com/",
    "https://www.cookinglight.com/"
  ],
  "new_source_16": [  # Fashion
    "https://www.vogue.in/",
    "https://www.fashionista.com/",
    "https://www.elle.com/in/",
    "https://www.gqindia.com/",
    "https://www.highsnobiety.com/",
    "https://www.bbc.com/news/fashion",
    "https://www.nytimes.com/section/fashion",
    "https://www.harpersbazaar.com/",
    "https://www.wmagazine.com/",
    "https://www.fashionweekonline.com/"
  ],
  "new_source_17": [  # Art
    "https://www.artsy.net/",
    "https://www.moma.org/",
    "https://www.metmuseum.org/",
    "https://www.saatchigallery.com/",
    "https://www.bbc.com/news/entertainment_and_arts",
    "https://www.nytimes.com/section/arts",
    "https://www.artnews.com/",
    "https://www.artforum.com/",
    "https://www.tate.org.uk/",
    "https://www.guggenheim.org/"
  ],
  "new_source_18": [  # Music
    "https://www.billboard.com/",
    "https://www.rollingstone.com/",
    "https://www.nme.com/",
    "https://www.bbc.com/news/entertainment_and_arts",
    "https://www.nytimes.com/section/arts/music",
    "https://www.indiatimes.com/entertainment/music",
    "https://www.pastemagazine.com/music/",
    "https://www.stereogum.com/",
    "https://www.spin.com/",
    "https://www.rocksound.tv/"
  ],
  "new_source_19": [  # Film
    "https://www.imdb.com/",
    "https://www.rottentomatoes.com/",
    "https://www.boxofficemojo.com/",
    "https://www.filmfare.com/",
    "https://www.bbc.com/news/entertainment_and_arts",
    "https://www.nytimes.com/section/movies",
    "https://www.indiatimes.com/entertainment/bollywood",
    "https://www.hollywoodreporter.com/",
    "https://www.variety.com/",
    "https://www.filmcompanion.in/"
  ],
  "new_source_20": [  # Television
    "https://www.tv.com/",
    "https://www.rottentomatoes.com/",
    "https://www.bbc.com/news/entertainment_and_arts",
    "https://www.nytimes.com/section/television",
    "https://www.indiatimes.com/entertainment/television",
    "https://www.tvline.com/",
    "https://www.ew.com/",
    "https://www.hollywoodreporter.com/",
    "https://www.variety.com/",
    "https://www.metacritic.com/"
  ],
  "new_source_21": [  # Theater
    "https://www.playbill.com/",
    "https://www.broadway.com/",
    "https://www.nationaltheatre.org.uk/",
    "https://www.royalshakespearecompany.co.uk/",
    "https://www.bbc.com/news/entertainment_and_arts",
    "https://www.nytimes.com/section/theater",
    "https://www.indiatimes.com/entertainment/theater",
    "https://www.stagecraftcircle.com/",
    "https://www.dramatistsguild.com/",
    "https://www.theatrecrafts.com/"
  ],
  "new_source_22": [  # Books
    "https://www.goodreads.com/",
    "https://www.amazon.in/books-used-books-textbooks/b?ie=UTF8&node=976389031",
    "https://www.flipkart.com/books",
    "https://www.bookdepository.com/",
    "https://www.barnesandnoble.com/",
    "https://www.penguinrandomhouse.com/",
    "https://www.harpercollins.co.in/",
    "https://www.hachetteindia.com/",
    "https://www.nytimes.com/section/books",
    "https://www.bbc.com/news/entertainment_and_arts"
  ],
  "new_source_23": [  # Automotive
    "https://www.carwale.com/",
    "https://www.autocarindia.com/",
    "https://www.motortrend.com/",
    "https://www.topgearmag.in/",
    "https://www.bbc.com/news/technology",
    "https://www.nytimes.com/section/automobiles",
    "https://www.autoblog.com/",
    "https://www.indiatimes.com/auto",
    "https://www.carscoops.com/",
    "https://www.motor1.com/"
  ],
  "new_source_24": [  # Real Estate
    "https://www.magicbricks.com/",
    "https://www.99acres.com/",
    "https://www.commonfloor.com/",
    "https://www.realtor.com/",
    "https://www.zillow.com/",
    "https://www.nytimes.com/section/realestate",
    "https://www.bbc.com/news/business",
    "https://www.indiatimes.com/real-estate",
    "https://www.propertyguru.com.sg/",
    "https://www.domain.com.au/"
  ],
  "new_source_25": [  # Law
    "https://www.law.com/",
    "https://www.barandbench.com/",
    "https://www.legal500.com/",
    "https://www.livemint.com/",
    "https://www.lawctopus.com/",
    "https://www.nytimes.com/section/law",
    "https://www.bbc.com/news/law",
    "https://www.indiatimes.com/india",
    "https://www.legallyindia.com/",
    "https://www.barandbench.com/"
  ],
  "new_source_26": [  # Crime
    "https://www.crimeonline.com/",
    "https://www.criminaldefenseattorneytampa.com/",
    "https://www.nytimes.com/section/us/crime",
    "https://www.bbc.com/news/world-us-canada",
    "https://www.indiatimes.com/india",
    "https://www.cnn.com/crime",
    "https://www.reuters.com/crime",
    "https://www.theguardian.com/us-news/crime",
    "https://www.policeone.com/",
    "https://www.nbcnews.com/news/crime-courts"
  ],
  "new_source_27": [  # Public Safety
    "https://www.cdc.gov/",
    "https://www.nhtsa.gov/",
    "https://www.fema.gov/",
    "https://www.usfa.fema.gov/",
    "https://www.firehouse.com/",
    "https://www.police1.com/",
    "https://www.bbc.com/news/world-us-canada-",
    "https://www.nytimes.com/section/us/crime",
    "https://www.reuters.com/crime",
    "https://www.indiatimes.com/india"
  ],
  "new_source_28": [  # Weather
    "https://www.weather.com/",
    "https://www.accuweather.com/",
    "https://www.weather.gov/",
    "https://www.metoffice.gov.uk/",
    "https://www.wunderground.com/",
    "https://www.bbc.com/weather",
    "https://www.nytimes.com/section/weather",
    "https://www.reuters.com/article/weather",
    "https://www.climate.gov/",
    "https://www.worldweatheronline.com/"
  ],
  "new_source_29": [  # Natural Disasters
    "https://www.nasa.gov/earth-science",
    "https://www.usgs.gov/natural-hazards",
    "https://www.un.org/en/climatechange",
    "https://www.fema.gov/",
    "https://www.reuters.com/article/natural-disasters",
    "https://www.cnn.com/weather",
    "https://www.bbc.com/news/weather",
    "https://www.weather.com/news/natural-disasters",
    "https://www.ndtv.com/natural-disasters",
    "https://www.theguardian.com/environment/natural-disasters"
  ],
  "new_source_30": [  # Space
    "https://www.nasa.gov/",
    "https://www.space.com/",
    "https://www.space.com/nasa",
    "https://www.esa.int/Space_in_mission",
    "https://www.indiatimes.com/science/space",
    "https://www.bbc.com/news/world-49411500",
    "https://www.reuters.com/space",
    "https://www.nytimes.com/section/science/space",
    "https://www.washingtonpost.com/space/",
    "https://www.cnn.com/world/space"
  ],
  "new_source_31": [  # Agriculture
    "https://www.fao.org/",
    "https://www.agriculture.com/",
    "https://www.indiatimes.com/india/agriculture",
    "https://www.nationalgeographic.com/environment/freshwater/",
    "https://www.reuters.com/industry/agriculture",
    "https://www.bbc.com/news/science_and_environment",
    "https://www.cnbc.com/agriculture/",
    "https://www.bbc.com/news/world-56434488",
    "https://www.worldagriculture.com/",
    "https://www.theguardian.com/environment/2025/mar/10/farming"
  ],
  "new_source_32": [  # Energy
    "https://www.energy.gov/",
    "https://www.reuters.com/business/energy",
    "https://www.greentechmedia.com/",
    "https://www.energycentral.com/",
    "https://www.bbc.com/news/business",
    "https://www.nytimes.com/section/energy",
    "https://www.washingtonpost.com/energy-environment/",
    "https://www.solarpowerworldonline.com/",
    "https://www.worldenergy.org/",
    "https://www.cnbc.com/energy/"
  ],
  "new_source_33": [  # Transportation
    "https://www.transportation.gov/",
    "https://www.indiatimes.com/auto",
    "https://www.cnbc.com/transportation/",
    "https://www.autoblog.com/",
    "https://www.washingtonpost.com/road-to-recovery/",
    "https://www.bbc.com/news/business",
    "https://www.reuters.com/article/transportation",
    "https://www.nytimes.com/section/automobiles",
    "https://www.indiatimes.com/auto",
    "https://www.theguardian.com/environment/transport"
  ],
  "new_source_34": [  # Military
    "https://www.armytimes.com/",
    "https://www.navytimes.com/",
    "https://www.military.com/",
    "https://www.defense.gov/",
    "https://www.cnn.com/us/military",
    "https://www.reuters.com/defense",
    "https://www.bbc.com/news/defence",
    "https://www.armytimes.com/news/defense/",
    "https://www.nytimes.com/section/military",
    "https://www.indianexpress.com/defense/"
  ],
  "new_source_35": [  # International Affairs
    "https://www.foreignaffairs.com/",
    "https://www.councilforeignrelations.org/",
    "https://www.nytimes.com/section/world",
    "https://www.bbc.com/news/world",
    "https://www.reuters.com/international",
    "https://www.theguardian.com/world",
    "https://www.aljazeera.com/",
    "https://www.washingtonpost.com/world/",
    "https://www.hindustantimes.com/world-news",
    "https://www.indiatimes.com/world"
  ],
  "new_source_36": [  # Human Rights
    "https://www.amnesty.org/en/",
    "https://www.humanrightswatch.org/",
    "https://www.un.org/en/sections/issues-depth/human-rights/",
    "https://www.reuters.com/article/human-rights",
    "https://www.bbc.com/news/human-rights",
    "https://www.nytimes.com/section/world/human-rights",
    "https://www.theguardian.com/world/human-rights",
    "https://www.indiatimes.com/india",
    "https://www.hindustantimes.com/india-news",
    "https://www.washingtonpost.com/world/human-rights/"
  ],
  "new_source_37": [  # Social Issues
    "https://www.smithsonianmag.com/social-issues/",
    "https://www.theatlantic.com/social-issues/",
    "https://www.theguardian.com/world/social-issues",
    "https://www.nytimes.com/section/us/social-issues",
    "https://www.reuters.com/social-issues",
    "https://www.washingtonpost.com/social-issues/",
    "https://www.bbc.com/news/world-56611000",
    "https://www.indiatimes.com/india",
    "https://www.hindustantimes.com/india-news",
    "https://www.aljazeera.com/social-issues"
  ],
  "new_source_38": [  # Religion
    "https://www.bbc.com/religion",
    "https://www.religionnews.com/",
    "https://www.nytimes.com/section/religion",
    "https://www.theguardian.com/world/religion",
    "https://www.hindustantimes.com/india-news",
    "https://www.indiatimes.com/religion",
    "https://www.aljazeera.com/religion",
    "https://www.christianitytoday.com/",
    "https://www.patheos.com/",
    "https://www.americanthinker.com/religion"
  ],
  "new_source_39": [  # Philanthropy
    "https://www.philanthropy.com/",
    "https://www.huffpost.com/philanthropy",
    "https://www.nytimes.com/section/philanthropy",
    "https://www.washingtonpost.com/philanthropy/",
    "https://www.reuters.com/philanthropy",
    "https://www.bbc.com/news/philanthropy",
    "https://www.indiatimes.com/philanthropy",
    "https://www.theguardian.com/philanthropy",
    "https://www.cnbc.com/philanthropy/",
    "https://www.forbes.com/philanthropy/"
  ],
  "new_source_40": [  # Technology Innovations
    "https://www.techcrunch.com/",
    "https://www.theverge.com/",
    "https://www.wired.com/",
    "https://www.cnet.com/",
    "https://www.engadget.com/",
    "https://www.reuters.com/technology",
    "https://www.bbc.com/news/technology",
    "https://www.nytimes.com/section/technology",
    "https://www.zdnet.com/",
    "https://www.cnbc.com/technology/"
  ],
  "new_source_41": [  # Cybersecurity
    "https://www.cybersecurity.gov/",
    "https://www.darkreading.com/",
    "https://www.infosecurity-magazine.com/",
    "https://www.cnbc.com/cybersecurity/",
    "https://www.bbc.com/news/technology",
    "https://www.scmagazine.com/",
    "https://www.techcrunch.com/",
    "https://www.thehackernews.com/",
    "https://www.nytimes.com/section/technology",
    "https://www.reuters.com/technology"
  ],
  "new_source_42": [  # Artificial Intelligence
    "https://www.singularityhub.com/",
    "https://www.technologyreview.com/ai/",
    "https://www.turing.com/blog/",
    "https://www.theverge.com/ai",
    "https://www.wired.com/category/ai/",
    "https://www.bbc.com/news/technology",
    "https://www.nytimes.com/section/technology",
    "https://www.reuters.com/technology",
    "https://www.forbes.com/ai/",
    "https://www.forbes.com/ai/"
  ],
  "new_source_43": [  # Blockchain
    "https://www.coindesk.com/",
    "https://www.blockchain.com/",
    "https://www.cnbc.com/blockchain/",
    "https://www.reuters.com/technology/blockchain",
    "https://www.cryptoslate.com/",
    "https://www.theblock.co/",
    "https://www.coindesk.com/markets",
    "https://www.techcrunch.com/cryptocurrency",
    "https://www.indiatimes.com/blockchain",
    "https://www.theguardian.com/technology/blockchain"
  ],
  "new_source_44": [  # Startups
    "https://www.techcrunch.com/startups/",
    "https://www.entrepreneur.com/",
    "https://www.startupgrind.com/",
    "https://www.inc.com/startups",
    "https://www.forbes.com/startups/",
    "https://www.nytimes.com/section/business/startups",
    "https://www.businessinsider.com/startups",
    "https://www.washingtonpost.com/business/startups/",
    "https://www.reuters.com/business/startups",
    "https://www.cnbc.com/startups/"
  ],
  "new_source_45": [  # Investments
    "https://www.forbes.com/investing/",
    "https://www.bbc.com/news/business",
    "https://www.cnbc.com/investing/",
    "https://www.reuters.com/finance/investing",
    "https://www.nytimes.com/section/business",
    "https://www.wsj.com/news/markets",
    "https://www.moneycontrol.com/",
    "https://www.money.cnn.com/investing",
    "https://www.indiatimes.com/finance",
    "https://www.bloomberg.com/markets"
  ],
  "new_source_46": [  # Cryptocurrency
    "https://www.coindesk.com/",
    "https://www.binance.com/",
    "https://www.cryptoslate.com/",
    "https://www.bitcoin.com/",
    "https://www.theblock.co/",
    "https://www.reuters.com/technology/cryptocurrency",
    "https://www.forbes.com/cryptocurrency/",
    "https://www.cnbc.com/cryptocurrency/",
    "https://www.theguardian.com/technology/cryptocurrency",
    "https://www.cnbc.com/cryptocurrency/"
  ],
  "new_source_47": [  # Economics
    "https://www.economist.com/",
    "https://www.reuters.com/finance/economics",
    "https://www.nytimes.com/section/business",
    "https://www.bbc.com/news/business",
    "https://www.wsj.com/news/economy",
    "https://www.forbes.com/economy/",
    "https://www.cnbc.com/economy/",
    "https://www.businessinsider.com/economy",
    "https://www.moneycontrol.com/",
    "https://www.money.cnn.com/economy"
  ],
        }

        return news_sources
    
    def get_categories(self):
        """
        Returns a predefined dictionary of news categories with empty lists.
        
        Args:
            None
        
        Returns:
            dict: Dictionary mapping category names (str) to empty lists
                Example: {'Politics': [], 'Business': [], 'Technology': []}
        """
        news_categories = {
            "Politics": [], "Business": [], "Economy": [], "Finance": [], "Health": [], "Science": [], "Technology": [], 
            "Environment": [], "Education": [], "Sports": [], "Entertainment": [], "Culture": [], "Lifestyle": [], "Travel": [], 
            "Food": [], "Fashion": [], "Art": [], "Music": [], "Film": [], "Television": [], "Theater": [], "Books": [], 
            "Automotive": [], "Real Estate": [], "Law": [], "Crime": [], "Public Safety": [], "Weather": [], "Natural Disasters": [], 
            "Space": [], "Agriculture": [], "Energy": [], "Transportation": [], "Military": [], "International Affairs": [], 
            "Human Rights": [], "Social Issues": [], "Religion": [], "Philanthropy": [], "Technology Innovations": [], 
            "Cybersecurity": [], "Artificial Intelligence": [], "Blockchain": [], "Startups": [], "Investments": [], 
            "Cryptocurrency": [], "Economics": [], "Trade": [], "Labor": [], "Consumer Affairs": [], "Public Health": [], 
            "Mental Health": [], "Nutrition": [], "Fitness": []
        }
        return news_categories

    def openai_api_request(self, prompt_text):
        """
        Makes an API request to Gemini model and returns response in an OpenAI-compatible format.
        
        Args:
            prompt_text (str): The prompt text to send to the Gemini API
                Example: "Summarize the latest news about AI advancements."
        
        Returns:
            ResponseWrapper: Custom object containing response data with attributes:
                - text (str): The generated text response
                - data (list): List containing nested object structure similar to OpenAI response
                - candidates (list): Original Gemini response candidates
        """
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][openai_api_request] Received Gemini request for content {prompt_text}")
        
        model_info = google_genai.get_model("models/gemini-2.0-flash-lite")
        model = google_genai.GenerativeModel("models/gemini-2.0-flash-lite")
        required_input_tokens = model.count_tokens(prompt_text)
        # print(f"Required Token for prompt_text ={required_input_tokens=}")
        
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[prompt_text])
        
        # print(response)
        # print(f"Finish reason: {response.candidates[0].finish_reason}")
        
        # Create a structure similar to OpenAI's response for compatibility
        class ResponseWrapper:
            def __init__(self, gemini_response):
                self.data = [type('obj', (object,), {
                    'content': [type('obj', (object,), {
                        'text': type('obj', (object,), {'value': gemini_response.text})
                    })]
                })]
                self.text = gemini_response.text
                self.candidates = gemini_response.candidates
                
        return ResponseWrapper(response)
    
    def start_gemini_assistant(self): #for news retrival 
        """
        Starts the Gemini assistant process to scrape news from sources, process them in threads,
        and store results in MongoDB.
        
        Args:
            None
        
        Returns:
            None: Results are stored directly in MongoDB
        """
        gemini_links_db = self.db
        
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Starting Gemini Assistant")
        # Use personalized URLs if available, otherwise use default news sources
        if hasattr(self, 'user_personalized_urls') and self.user_personalized_urls:
            news_sources = self.user_personalized_urls
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Using personalized news sources: {len(news_sources)} categories")
        else:
            news_sources = self.get_news_src()
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Using default news sources: {len(news_sources)} categories")
        links = {}
        lock = self.thread_lock
        result_grded_news = {}
        
        def process_lnks(category, sources):
            nonlocal links    
            if category not in links:
                links[category] = {}
                
            for source in sources:
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Getting news from {source}")
                try:
                    links[category][source] = get_links_and_content_from_page(source)
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Successfully extracted news from {source}")
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] *****************************************************")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] ************************ERROR************************")
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Failed to extract news from {source}: {e}")
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] *****************************************************")
                    
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Before processing category: {links[category]} and length {len(str(links[category]))} and for category {category}")
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Thread ID for {category}: {thread.ident}")
            
            if category not in result_grded_news:
                result_grded_news[category] = []
                
            with lock:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Thread {thread.ident} acquired lock for {category}")
                
                # Step 1: Check URL relevance using HuggingFace API
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Checking URL content relevance for {category}")
                relevance_results = check_url_content_relevance(links[category], threshold=0.4)
                
                # Filter out irrelevant content
                filtered_links = {}
                for base_url, articles in links[category].items():
                    filtered_links[base_url] = {}
                    for article_url, content in articles.items():
                        if base_url in relevance_results and article_url in relevance_results[base_url] and relevance_results[base_url][article_url] == 1:
                            filtered_links[base_url][article_url] = content
                            
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Filtered {sum(len(articles) for articles in links[category].values()) - sum(len(articles) for articles in filtered_links.values())} irrelevant articles")
                
                # Step 2: Categorize content using HuggingFace API
                news_categories = self.get_categories()
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Categorizing content for {category}")
                categorized_content = categorize_content(filtered_links, news_categories)
                
                # Clean the categorized content to remove empty categories
                categorized_content = self._clean_categorized_content(categorized_content)
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Cleaned categorized content for {category}")
                
                # Convert categorized content to the expected format for result_grded_news
                result_grded_news[category] = categorized_content
                
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] After processing category: {result_grded_news[category]} and length {len(str(result_grded_news[category])) if result_grded_news[category] else 0} and for category {category}")
            
            with lock:
                try:
                    # Using the date with time constraint for storage
                    gemini_links_db.insert_one({self.today_date: {category: result_grded_news[category]}})
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Successfully inserted data for {category} into MongoDB with date-time constraint: {self.today_date}")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Failed to insert data into MongoDB: {e}")
                    print(f"Failed to insert data into MongoDB: {e}")
                    
        threads = []
        for category, sources in news_sources.items():
            thread = Thread(target=process_lnks, args=(category, sources))
            threads.append(thread)
            thread.start()
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] Starting thread for {category} with thread ID: {thread.ident}")
            
        for thread in threads:
            thread.join()
            
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][start_gemini_assistant] News retrieval complete")
        return None

    def grd_nws(self, links, category):
        """
        Processes news links for a specific category and grades their relevance.
        
        Args:
            links (dict): Dictionary mapping source URLs to article content
                Example: {'https://source.com/': {'https://source.com/article1': ['Title', 'Content']}}
            category (str): Category name for the news
                Example: 'Technology'
        
        Returns:
            dict: Dictionary of categorized and relevant news links
                Example: {'AI': {'https://source.com/': {'https://source.com/ai-article': ['Title', 'Content']}}}
                Returns None if processing fails or no news is available
        """
        news = links
        summary = self.summary
        result_links = {}
        categories = self.get_categories()
        
        if news and summary:
            return None
        elif news:
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] News is present for category {category}")
            
            for top_url in list(links.keys()):
                step = max(1, int(len(list(news[top_url].items()))/self.MAX_BATCHES))
                link_items = [list(news[top_url].items())[j:j+step] for j in range(0, len(list(news[top_url].items())), step)]
                
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing {len(link_items)} batches for {category}")
                
                for link_item in link_items:
                    # Log the size of link_item in bytes and KB
                    try:
                        link_item_str = str(link_item)
                        link_item_size_bytes = len(link_item_str)
                        link_item_size_kb = link_item_size_bytes / 1024
                        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing batch with size: {link_item_size_bytes} bytes ({link_item_size_kb:.2f} KB)")
                    except Exception as e:
                        append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to calculate batch size: {str(e)}")
                    
                    # Process the batch with retry logic and batch splitting
                    self._process_batch_with_retry(link_item, result_links, categories, top_url, self.MAX_RETRY)
                
            # Remove empty categories
            result_links = {k: v for k, v in result_links.items() if v}
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Final categorized news: {result_links}")
            
        return result_links

    def _process_batch_with_retry(self, link_item, result_links, categories, top_url, retries_remaining):
        """
        Helper method to process a batch of links with retry logic and batch splitting.
        
        Args:
            link_item (list): List of tuples containing article URLs and their content
                Example: [('https://example.com/article1', ['Title1', 'Content1'])]
            result_links (dict): Dictionary to store categorized results, modified in place
                Example: {'Technology': {'https://source.com/': {'https://article-url': ['Title', 'Content']}}}
            categories (dict): Dictionary of category names to empty lists
                Example: {'Politics': [], 'Technology': []}
            top_url (str): Base URL of the news source
                Example: 'https://www.techcrunch.com/'
            retries_remaining (int): Number of retry attempts left
                Example: 3
        
        Returns:
            None: Results are stored directly in the result_links parameter
        """
        if retries_remaining <= 0:
            append_to_log(self.log_file, f"[GEMINI][CRITICAL][{datetime.today().strftime('%H:%M:%S')}][grd_nws] CRITICAL ERROR: Could not process the data after all retry attempts")
            return
        
        try:
            # Log the size of link_item after converting to string
            try:
                link_item_str = str(link_item)
                link_item_size = len(link_item_str)
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Processing batch of size {link_item_size} bytes ({link_item_size/1024:.2f} KB)")
            except Exception as e:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to log link_item size: {str(e)}")
                
            # Create lists of categories and article items for index reference
            categories_list = list(categories.keys())
            
            prompt = f"""
            Analyze these articles: {link_item}
            
            I'll provide you with:
            1. A list of article items where each item is a tuple of (article_url, [title, content])
            2. A list of category names: {categories_list}
            
            Return a dictionary mapping category indices to lists of article indices that belong to that category.
            For example: {{2: [0, 3], 5: [1, 2]}} means:
            - Articles at indices 0 and 3 belong to the category at index 2
            - Articles at indices 1 and 2 belong to the category at index 5
            
            An article can belong to multiple categories if relevant.
            Only include articles that are relevant to at least one category.
            Format the response as a valid Python dictionary of indices.

            Only return a python dict data structure, avoid ``` and word python in the string
            """
            
            response = self.openai_api_request(prompt)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Received grading response")
            
            # Log the raw response text for debugging
            try:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Raw response text: {response.text}")
            except Exception as log_error:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to log response text: {str(log_error)}")
                
            # Parsing response
            response_text = response.text
            # Remove markdown formatting if present
            if "```python" in response_text:
                response_text = response_text.split("```python")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            try:
                index_mapping = eval(response_text)
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Successfully parsed index mapping")
                
                # Convert the index mapping to actual data
                categorized_data = {}
                for cat_idx, article_indices in index_mapping.items():
                    if cat_idx < len(categories_list):
                        cat_name = categories_list[cat_idx]
                        if cat_name not in categorized_data:
                            categorized_data[cat_name] = []
                        
                        for article_idx in article_indices:
                            if article_idx < len(link_item):
                                categorized_data[cat_name].append(link_item[article_idx])
                
                # Merge the categorized data into result_links
                for cat, articles in categorized_data.items():
                    if cat not in result_links:
                        result_links[cat] = {}
                    if articles:  # Only process if there are articles
                        if top_url not in result_links[cat]:
                            result_links[cat][top_url] = {}
                        for article_url, content in articles:
                            result_links[cat][top_url][article_url] = content
            except Exception as parsing_error:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Failed to parse response: {str(parsing_error)}")
                raise parsing_error  # Re-raise to trigger the split and retry
                        
        except Exception as e:
            append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Error processing batch: {str(e)}. Retries remaining: {retries_remaining-1}")
            
            # If batch processing failed, split the batch into smaller pieces
            if len(link_item) > 1:
                mid = len(link_item) // 2
                append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][grd_nws] Splitting batch of size {len(link_item)} into two smaller batches")
                
                # Process first half
                self._process_batch_with_retry(link_item[:mid], result_links, categories, top_url, retries_remaining-1)
                # Process second half
                self._process_batch_with_retry(link_item[mid:], result_links, categories, top_url, retries_remaining-1)
            else:
                # If we're already down to a single item and still failing, try one more time with reduced retries
                time.sleep(2)  # Longer pause before retrying a single item
                self._process_batch_with_retry(link_item, result_links, categories, top_url, retries_remaining-1)

    def process_category(self, category, sources):
        """
        Process news sources for a specific category, generating summaries for each article.
        
        Args:
            category (str): Category name for the news
                Example: 'Technology'
            sources (dict): Dictionary of news sources and their content for the category
                Example: {'https://techcrunch.com/': {'https://techcrunch.com/article1': ['Title', 'Content']}}
        
        Returns:
            None: Results are stored in the self.thread_result dictionary
        """
        result = {}
        
        # Initialize the category in the result dictionary
        if category not in result:
            result[category] = {}
        
        for source, articles in sources.items():
            if source not in result[category]:
                result[category][source] = []
                
            for article_url, article_data in articles.items():
                try:
                    # Check if article data is in expected format
                    if not isinstance(article_data, list) or len(article_data) < 2:
                        append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][process_category] Skipping article {article_url} as it has insufficient details")
                        continue
                    
                    title, news_content = article_data
                    
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Processing summary for {article_url} with title: {title}")
                    
                    prompt = f"Summarize the news from {article_url} with the title {title} and content {news_content} with at least 100 words"
                    summary = self.openai_api_request(prompt)
                    
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Summary result: {summary.data[0].content[0].text.value}")
                    
                    result[category][source].append({
                        "link": article_url,
                        "title": title,
                        "content": news_content,
                        "summary": summary.data[0].content[0].text.value
                    })
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][process_category] Error processing article {article_url}: {str(e)}")
        
        with self.thread_lock:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][process_category] Thread acquired lock for {category}")
            # Update thread_result with this category's results
            if category in self.thread_result:
                # Merge with existing results
                for source, articles in result[category].items():
                    if source in self.thread_result[category]:
                        self.thread_result[category][source].extend(articles)
                    else:
                        self.thread_result[category][source] = articles
            else:
                # Add new category
                self.thread_result[category] = result[category]

    def check_news_in_db(self, preferred_category=None):
        """
        Check if news for today's date exists in the database.
        
        Args:
            preferred_category (str, optional): Category to filter news by
                Example: 'Technology'
                Default: None (all categories)
        
        Returns:
            dict: Dictionary of news content from database
                Example: {'Technology': {'https://source.com/': {'https://article-url': ['Title', 'Content']}}}
                Returns None if no news found
        """
        gemini_links_db = self.db
        today_date = self.today_date
        
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] Checking news for date: {today_date}")
        
        if not preferred_category:
            query = {self.today_date: {"$exists": True}}
        else:
            query = {f"{today_date}.{preferred_category}": {"$exists": True}}
            
        news_data_cursor = gemini_links_db.find(query)
        
        collected_news = {}
        
        for news_data in news_data_cursor:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] Found news data in database {news_data}")
            
            for date, categories in news_data.items():
                if date == "_id":
                    continue
                for category, sources in categories.items():
                    if category not in collected_news:
                        collected_news[category] = {}
                    for source, content in sources.items():
                        collected_news[category][source] = content
                        
        if not collected_news:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_news_in_db] No news data found for today in the database")
            return None
            
        return collected_news

    def run_sumarizing_threads(self):
        """
        Run threads to summarize news content for each category.
        
        Args:
            None
        
        Returns:
            None: Results are stored in the self.thread_result dictionary
        """
        threads = []
        self.thread_result.clear()
        content = self.check_news_in_db()
        
        if not content:
            append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] No content found in database")
            return None
            
        for category, sources in content.items():
            thread = Thread(target=self.process_category, args=(category, sources))
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] Starting thread")
            threads.append(thread)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][run_sumarizing_threads] Starting thread for {category} with {thread.ident}")
            thread.start()
            
        for thread in threads:
            thread.join()

    def push_results_to_db(self, result, result_type):
        """
        Push summarized results to the database.
        
        Args:
            result (dict): Dictionary containing processed news content or summaries
                Example: {'Technology': {'https://source.com/': [{'title': 'Title', 'content': 'Content', 'summary': 'Summary'}]}}
            result_type (str): Type of result being stored ('Result' or 'Summary')
                Example: 'Result'
        
        Returns:
            None: Results are stored directly in MongoDB
        """
        print("Result from Gemini") 
        print("CONTENT FROM DB")
        gemini_links_db = self.db
        gemini_links_db.insert_one({result_type:{self.today_date: result}})
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][push_results_to_db] Pushed {result_type} to database with time constraint: {self.today_date}")

    def fetch_todays_results(self):
        """
        Fetch today's results from the database.
        
        Args:
            None
        
        Returns:
            str: JSON string containing today's results
                Example: '{"_id": "123", "Result": {"2023-06-15_18:00": {"Technology": {...}}}}'
                Returns None if no results found
        """
        gemini_links_db = self.db
        query = {f"Result.{self.today_date}": {"$exists": True}}
        
        results_cursor = gemini_links_db.find(query)
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Fetching today's results from MongoDB for {self.today_date}")
        
        result_json = None
        for result in results_cursor:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Query result: {result['_id']}")
            # Convert ObjectId to string representation
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Processing result: {result['_id']}")
            result['_id'] = str(result['_id'])
            result_json = json.dumps(result, indent=4)
            
        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_todays_results] Result JSON: {result_json}")
        return result_json

    def fetch_content_and_run_summary(self):
        """
        Fetch content and run summary generation if not already done.
        
        Args:
            None
        
        Returns:
            None: Results are stored directly in MongoDB and class properties
        """
        result_json = self.fetch_todays_results()
        # Check if results already exist in the database
        if not result_json:
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No results found for today, Checking for NEWS")
            
            # Get content from database first
            content = self.check_news_in_db()
            if not content:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No content found in database")
                return None
            
            # No need for explicit mapping since we'll use categories directly from the JSON data
            # Just organize the content for processing
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Processing content from {len(content)} categories")
                
            # Use Hugging Face's summarize_articles instead of Gemini API
            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Starting RESULT URL summarization with Hugging Face's summarize_articles function")
            
            try:
                # Process each category with summarize_articles
                summarized_content = {}
                for news, cat_list in content.items():
                    for category, sources in cat_list.items():
                        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Summarizing articles for category: {category}")
                        
                        # Transform data to the format expected by summarize_articles
                        # summarize_articles expects: {'base_url': {'article_url': [title, content], ...}, ...}
                        category_summaries = summarize_articles(sources, min_words=100)
                        
                        # Skip if no summaries were generated
                        if not category_summaries:
                            append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No summaries generated for category: {category}")
                            continue
                        
                        if category not in summarized_content:
                            summarized_content[category] = {}
                        
                        # Convert summaries to the expected format for thread_result
                        for source, article_summaries in category_summaries.items():
                            if source not in summarized_content[category]:
                                summarized_content[category][source] = []
                                
                            for article_url, summary in article_summaries.items():
                                # Get original article content
                                if article_url in sources[source]:
                                    original_content = sources[source][article_url]
                                    title = original_content[0] if isinstance(original_content, list) and len(original_content) >= 1 else "Unknown Title"
                                    content = original_content[1] if isinstance(original_content, list) and len(original_content) >= 2 else ""
                                    
                                    summarized_content[category][source].append({
                                        "link": article_url,
                                        "title": title,
                                        "content": content,
                                        "summary": summary
                                    })
                                    
                                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Generated summary for article: {article_url}")
                    
                # Save summarized content to thread_result for database storage
                self.thread_result = summarized_content
                
                # Push results to database if we have summarized content
                if self.thread_result:
                    # Clean up empty categories before pushing to database
                    cleaned_result = self._clean_empty_categories(self.thread_result)
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Cleaned up empty categories. Before: {len(self.thread_result)} categories, After: {len(cleaned_result)} categories")
                    self.thread_result = cleaned_result
                    
                    # Only push to DB if we have actual content after cleaning
                    if cleaned_result:
                        self.push_results_to_db(self.thread_result, "Result")
                        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Successfully pushed summarized results to MongoDB")
                    else:
                        append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No content after cleaning, skipping database push")
                else:
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No thread_result found, nothing to push to MongoDB")
                
                # Generate an overall summary using Gemini
                try:
                    overall_summary = self._generate_overall_summary(self.thread_result)
                    
                    # Check if overall summary has actual content before pushing to DB
                    has_content = False
                    if isinstance(overall_summary, dict):
                        # Check introduction content
                        if overall_summary.get("overall_introduction") and overall_summary["overall_introduction"] != "No news content available for summarization.":
                            has_content = True
                        
                        # Check if there are categories with content
                        if overall_summary.get("categories") and len(overall_summary["categories"]) > 0:
                            has_content = True
                    
                    if has_content:
                        self.summary = {"gemini_summary": overall_summary}
                        formatted_result = {self.today_date: overall_summary}
                        self.push_results_to_db(formatted_result, "Summary")
                        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Successfully generated and stored overall summary")
                    else:
                        append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Generated summary has no content, skipping database push")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Error generating overall summary: {str(e)}")
                
            except Exception as e:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Error during Hugging Face summarization: {str(e)}")
                # Fall back to original threading approach but with flattened content
                self.thread_result = {}
                threads = []
                for category, sources in flattened_content.items():
                    thread = Thread(target=self.process_category, args=(category, sources))
                    threads.append(thread)
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Starting thread for {category}")
                    thread.start()
                    
                for thread in threads:
                    thread.join()
                    
                if self.thread_result:
                    cleaned_result = self._clean_empty_categories(self.thread_result)
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Cleaned up empty categories. Before: {len(self.thread_result)} categories, After: {len(cleaned_result)} categories")
                    
                    # Only push to DB if we have actual content after cleaning
                    if cleaned_result:
                        self.thread_result = cleaned_result
                        self.push_results_to_db(self.thread_result, "Result")
                        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Successfully pushed summarized results to MongoDB")
                    else:
                        append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] No content after cleaning, skipping database push")
        else:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Results already exist in DB - skipping summarization")
            # Convert JSON string to Python dictionary
            result_json_obj = json.loads(result_json)
            if "Result" in result_json_obj and self.today_date in result_json_obj["Result"]:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Using existing results")
                self.thread_result = result_json_obj["Result"][self.today_date]
            
            # Check if we need to generate a summary
            if not self.chk_summary():
                try:
                    # Get content directly from the result_json_obj
                    if "Result" in result_json_obj and self.today_date in result_json_obj["Result"]:
                        content_for_summary = result_json_obj["Result"][self.today_date]
                        append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Extracted content for summarization")
                        
                        # Call the summary function with Gemini
                        overall_summary_result = self._generate_overall_summary(content_for_summary)
                        
                        # Check if summary has actual content before pushing to DB
                        has_content = False
                        if isinstance(overall_summary_result, dict):
                            # Check introduction content
                            if overall_summary_result.get("overall_introduction") and overall_summary_result["overall_introduction"] != "No news content available for summarization.":
                                has_content = True
                            
                            # Check if there are categories with content
                            if overall_summary_result.get("categories") and len(overall_summary_result["categories"]) > 0:
                                has_content = True
                        
                        if has_content:
                            self.summary = {"gemini_summary": overall_summary_result}
                            formatted_result = {self.today_date: overall_summary_result}
                            self.push_results_to_db(formatted_result, "Summary")
                            append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Generated and stored overall summary")
                        else:
                            append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Generated summary has no content, skipping database push")
                    else:
                        append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Content structure not in expected format")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][fetch_content_and_run_summary] Error generating overall summary: {str(e)}")

    def _summarize_articles_with_gemini(self, sources):
        """
        Helper method to summarize articles using Gemini API.
        
        Args:
            sources (dict): Dictionary of news sources and their articles
                Example: {'https://techcrunch.com/': {'https://techcrunch.com/article1': ['Title', 'Content']}}
        
        Returns:
            dict: Dictionary of summarized articles by source
                Example: {'https://techcrunch.com/': {'https://techcrunch.com/article1': {
                    'title': 'Title', 'content': 'Content', 'summary': 'Generated summary'}}}
        """
        summarized_articles = {}
        
        for source, articles in sources.items():
            summarized_articles[source] = {}
            
            for article_url, content in articles.items():
                try:
                    # Extract title and content
                    if isinstance(content, list) and len(content) >= 2:
                        title = content[0]
                        article_content = content[1]
                    else:
                        title = "Unknown Title"
                        article_content = str(content)
                    
                    if not article_content or len(article_content.strip()) < 50:
                        append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][_summarize_articles_with_gemini] Skipping article with insufficient content: {article_url}")
                        continue
                    
                    # Prepare the prompt for Gemini
                    prompt = f"""Please analyze this news data and create a summary of 100-150 words:
                    1. Key bullet points of the main story
                    2. Important facts and figures
                    3. A brief executive summary
                    4. Highlight any critical developments
                    
                    Title: {title}
                    Source: {source}
                    Content: {article_content[:4000]}  # Limiting content to avoid token limits
                    
                    Provide only the summary with no additional text or explanations.
                    """
                    
                    # Get summary from Gemini API
                    response = self.openai_api_request(prompt)
                    summary = response.text.strip()
                    
                    # Log successful summary generation
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][_summarize_articles_with_gemini] Generated summary for article: {article_url}")
                    
                    # Store the summary with original content
                    summarized_articles[source][article_url] = {
                        "title": title,
                        "content": article_content,
                        "summary": summary
                    }
                    
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][_summarize_articles_with_gemini] Error summarizing article {article_url}: {str(e)}")
        
        return summarized_articles
    
    def _generate_overall_summary(self, content):
        """
        Generate a structured summary of all news content with separate sections by category.
        Aggregates all source summaries in each category into a single comprehensive category summary.
        
        Args:
            content (dict): Dictionary of news content by category
            
        Returns:
            dict: Structured summary with introduction, categories, and conclusion
        """
        if not content:
            append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] No content provided for summarization")
            return {"overall_introduction": "No news content available for summarization.", "categories": {}, "overall_conclusion": ""}
        
        # Extract time constraint information from date key
        date_parts = self.today_date.split('_')
        date = date_parts[0]
        time_constraint = date_parts[1]
        
        # Determine if this is a morning or evening report
        if time_constraint == "06:00":
            time_period = "overnight to early morning"
        else:  # 18:00
            time_period = "morning to evening"
            
        all_category_summaries = {}
        
        # Process each category separately
        for category, sources in content.items():
            # Skip empty categories
            if not sources:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Skipping empty category: {category}")
                continue
                
            # Extract ALL summaries and content from every source in this category
            all_source_articles = []
            combined_summaries = []
            
            for source, articles in sources.items():
                if isinstance(articles, list):
                    for article in articles:
                        if isinstance(article, dict):
                            # Extract article information
                            title = article.get("title", "No title")
                            article_summary = article.get("summary", "")
                            url = article.get("link", "")
                            
                            # Add the summary to our combined list
                            if article_summary:
                                combined_summaries.append(article_summary)
                            
                            # Keep track of the article for reference
                            all_source_articles.append({
                                "title": title,
                                "source": source,
                                "url": url
                            })
            
            # Skip categories with no articles
            if not all_source_articles:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] No articles found for category: {category}")
                continue
                
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Creating summary for category: {category} with {len(all_source_articles)} articles")
            
            # If we have existing summaries, use them as input for our category synthesis
            if combined_summaries:
                synthesis_prompt = f"""
                Create a comprehensive synthesis of all the following news summaries from the {category} category.
                These summaries cover news from the {time_period} period on {date}.
                
                SOURCE SUMMARIES:
                {' '.join(combined_summaries[:20])}  # Limiting to first 20 summaries to avoid token limits
                
                YOUR TASK:
                1. Create a single coherent summary that integrates all the information from these sources
                2. Highlight the most important developments in {category}
                3. Organize the information logically by topic or theme
                4. Include specific details, facts, figures, and important quotes where relevant
                5. Maintain objectivity and balance in presenting different perspectives
                
                Write about 600-800 words in a journalistic style that gives a complete overview of the 
                {category} news during this period. Use a structure with clear paragraphs and logical flow.
                """
                
                try:
                    # Generate the synthesized summary from existing article summaries
                    synthesis_response = self.openai_api_request(synthesis_prompt)
                    category_summary = synthesis_response.text.strip()
                    append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Generated synthesized summary of {len(category_summary.split())} words for category: {category}")
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Error generating synthesized summary: {str(e)}")
                    # Fall back to listing approach
                    category_summary = f"Error generating synthesized summary for {category}. Key stories include: " + ", ".join([article["title"] for article in all_source_articles[:10]])
            else:
                # If no existing summaries, create a summary from the article titles and sources
                fallback_prompt = f"""
                Create a comprehensive summary of {category} news based on these article titles:
                
                {json.dumps(all_source_articles, indent=2)}
                
                Write about 400-500 words covering the key stories. Focus on extracting meaning and
                connections between these stories to create a coherent narrative of {category} news
                for {date} during the {time_period} period.
                """
                
                try:
                    fallback_response = self.openai_api_request(fallback_prompt)
                    category_summary = fallback_response.text.strip()
                except Exception as e:
                    append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Error generating fallback summary: {str(e)}")
                    category_summary = f"Unable to generate summary for {category}."
            
            # Create an engaging title for this category
            title_prompt = f"""
            Create a catchy, informative title for a news summary section about {category}.
            The title should be engaging and relevant to today's {category} news ({date}).
            Keep it under 10 words. Only return the title text, nothing else.
            """
            
            try:
                title_response = self.openai_api_request(title_prompt)
                category_title = title_response.text.strip()
            except Exception as e:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Error generating title: {str(e)}")
                category_title = f"{category} News Roundup"
            
            # Store title and combined summary
            all_category_summaries[category] = {
                "title": category_title,
                "summary": category_summary,
                "article_count": len(all_source_articles),
                "source_count": len(sources)
            }
        
        # If no categories had content, return a default message
        if not all_category_summaries:
            append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] No category summaries were generated")
            return {"overall_introduction": "No news content available for summarization.", "categories": {}, "overall_conclusion": ""}
        
        # Create an overall introduction
        category_names = list(all_category_summaries.keys())
        top_categories = sorted(category_names, key=lambda cat: all_category_summaries[cat]["article_count"], reverse=True)[:5]
        
        intro_prompt = f"""
        Write a brief introduction (about 200-250 words) for a daily news summary covering the following categories:
        {", ".join(category_names)}
        
        This introduction should:
        1. Mention the date ({date}) and the time period ({time_period})
        2. Highlight that this is a comprehensive news roundup
        3. Highlight the most important stories from these top categories: {", ".join(top_categories[:3])}
        4. Provide a brief overview of the major themes across all categories
        
        Just provide the introduction paragraph, nothing else.
        """
        
        try:
            intro_response = self.openai_api_request(intro_prompt)
            introduction = intro_response.text.strip()
        except Exception as e:
            append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Error generating introduction: {str(e)}")
            introduction = f"Today's News Summary ({date}) - {time_period}\n\nHere's your daily roundup of important news across {len(category_names)} categories including {', '.join(category_names[:5])}."
        
        # Generate a conclusion
        conclusion = ""
        if len(all_category_summaries) > 1:
            conclusion_prompt = f"""
            Write a thoughtful conclusion (about 150-200 words) for a daily news summary that has covered the following categories:
            {", ".join(category_names)}
            
            This conclusion should:
            1. Synthesize the key themes across all categories
            2. Highlight connections between different news stories where relevant
            3. Mention that this summary covers the {time_period} period on {date}
            4. Provide forward-looking statements or questions about how these stories might develop
            
            Just provide the conclusion paragraph, nothing else.
            """
            
            try:
                conclusion_response = self.openai_api_request(conclusion_prompt)
                conclusion = conclusion_response.text.strip()
            except Exception as e:
                append_to_log(self.log_file, f"[GEMINI][ERR][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Error generating conclusion: {str(e)}")
        
        # Create the final structured summary
        structured_summary = {
            "overall_introduction": introduction,
            "categories": all_category_summaries,
            "overall_conclusion": conclusion
        }
        
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][_generate_overall_summary] Successfully generated structured summary for {len(all_category_summaries)} categories")
        return structured_summary

    def check_summary_present(self):
        """
        Check if summary is present and push to database.
        
        Args:
            None
        
        Returns:
            None: Summary is pushed directly to MongoDB
        """
        print(" THERE is SUMMARY")
        formatted_result = {}
        for _, summary_response in self.summary.items():
            # Modified to use the new response wrapper structure
            summary_text = summary_response.data[0].content[0].text.value
            
            # Only add to formatted_result if summary_text has content
            if summary_text and len(summary_text.strip()) > 0:
                formatted_result[self.today_date] = summary_text
        
        # Only push to DB if we have actual content
        if formatted_result:
            self.push_results_to_db(formatted_result, "Summary")
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][check_summary_present] Successfully pushed summary to MongoDB")
        else:
            append_to_log(self.log_file, f"[GEMINI][WARN][{datetime.today().strftime('%H:%M:%S')}][check_summary_present] Empty summary content, skipping database push")

    def chk_news(self):
        """
        Check if news exists in the database for all categories.
        
        Args:
            None
        
        Returns:
            list: List of binary flags (0 or 1) indicating presence of news for each category
                Example: [1, 0, 1, 1, 0] - where 1 indicates news exists for the category
        """
        flag = []
        for category in self.get_news_src():
            if self.db.count_documents({f"{self.today_date}.{category}": {"$exists": True}}) > 0:
                flag.append(1)
            else:
                flag.append(0)
        return flag

    def chk_results(self):
        """
        Check if results exist in the database for today's date.
        
        Args:
            None
        
        Returns:
            bool: True if results exist, False otherwise
        """
        if self.db.count_documents({f"Result.{self.today_date}": {"$exists": True}}) > 0:
            print(f"Results are present {self.db.find({f'Result.{self.today_date}': {'$exists': True}})}")
            return True
        return False
    
    def chk_summary(self):
        """
        Check if summary exists in the database for today's date.
        
        Args:
            None
        
        Returns:
            bool: True if summary exists, False otherwise
        """
        count = self.db.count_documents({f"Summary.{self.today_date}": {"$exists": True}})
        print(f"Summary count: {count}")
        if count > 0:
            print(f"Summary is present")
            cursor = self.db.find({f'Summary.{self.today_date}': {'$exists': True}})
            for doc in cursor:
                print(f"Found summary document: {doc}")
            return True
        return False

    def get_all_available_dates(self):
        """
        Returns a list of all unique dates available in the database.
        
        Args:
            None
        
        Returns:
            list: List of date strings in format 'YYYY-MM-DD_HH:00', sorted in reverse chronological order
                Example: ['2023-06-15_18:00', '2023-06-15_06:00', '2023-06-14_18:00']
        """
        gemini_links_db = self.db
        date_pattern = r"\d{4}-\d{2}-\d{2}_\d{2}:\d{2}"  # Regex pattern for YYYY-MM-DD_HH:MM format

        # Aggregate pipeline to extract all field names that match the date pattern
        pipeline = [
            {"$project": {"documentFields": {"$objectToArray": "$$ROOT"}}},
            {"$unwind": "$documentFields"},
            {"$match": {"documentFields.k": {"$regex": date_pattern}}},
            {"$group": {"_id": None, "dates": {"$addToSet": "$documentFields.k"}}},
            {"$project": {"_id": 0, "dates": 1}}
        ]

        result = list(gemini_links_db.aggregate(pipeline))

        if result and 'dates' in result[0]:
            dates = result[0]['dates']
            # Sort dates chronologically with custom sort function
            dates.sort(key=lambda x: x.replace('_', 'T'), reverse=True)
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][get_all_available_dates] Found {len(dates)} dates in database")
            return dates
        else:
            append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][get_all_available_dates] No dates found in database")
            return []

    def _clean_empty_categories(self, content_dict):
        """
        Remove empty categories from the content dictionary.
        
        Args:
            content_dict (dict): Dictionary of content by category
                Example: {'Technology': {'https://source.com/': {}}, 'Politics': {'https://news.org/': {'article1': ['Title', 'Content']}}}
        
        Returns:
            dict: Cleaned dictionary with only populated categories
                Example: {'Politics': {'https://news.org/': {'article1': ['Title', 'Content']}}}
        """
        cleaned_dict = {category: sources for category, sources in content_dict.items() if sources}
        return cleaned_dict

    def _clean_categorized_content(self, categorized_content):
        """
        Cleans categorized content by removing empty categories and empty base URLs.
        
        Args:
            categorized_content (dict): Dictionary mapping categories to news sources and articles
                Structure: {category: {base_url: {article_url: [title, content]}, ...}, ...}
                
        Returns:
            dict: Cleaned dictionary with empty categories and empty base URLs removed, 
                preserving the original structure for non-empty content
        """
        if not categorized_content:
            return {}
            
        cleaned_content = {}
        
        for category, sources in categorized_content.items():
            # Skip categories with no sources dictionary
            if not sources:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][_clean_categorized_content] Removing empty category: {category}")
                continue
                
            # Create a filtered version of sources with only non-empty base_urls
            filtered_sources = {}
            for base_url, articles in sources.items():
                # Only add base_url if it has articles
                if articles:
                    filtered_sources[base_url] = articles
                else:
                    append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][_clean_categorized_content] Removing empty base URL: {base_url} from category: {category}")
            
            # Only add the category if it has at least one non-empty base_url
            if filtered_sources:
                cleaned_content[category] = filtered_sources
            else:
                append_to_log(self.log_file, f"[GEMINI][DBG][{datetime.today().strftime('%H:%M:%S')}][_clean_categorized_content] Removing category with only empty base URLs: {category}")
        
        # Log summary of cleaning operations
        categories_removed = len(categorized_content) - len(cleaned_content)
        append_to_log(self.log_file, f"[GEMINI][INF][{datetime.today().strftime('%H:%M:%S')}][_clean_categorized_content] Cleaning complete. Removed {categories_removed} empty categories.")
        
        return cleaned_content
