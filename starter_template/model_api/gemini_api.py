












news_sources = {
    "climate_tech_general": [
        "https://www.reuters.com/",
        "https://www.bloomberg.com/",
        "https://www.theguardian.com/",
        "https://www.ft.com/"
    ],
    "climate_tech_specialized": [
        "https://climateinsider.com/",
        "https://www.canarymedia.com/",
        "https://www.greentechmedia.com/",
        "https://sifted.eu/sector/climatetech"
    ],
    "climate_tech_research": [
        "https://www.nature.com/",
        "https://www.science.org/"
    ],
    "government_politics_general": [
        "https://apnews.com/",
        "https://www.reuters.com/",
        "https://www.bbc.com/news",
        "https://www.nytimes.com/",
        "https://www.politico.com/"
    ],
    "government_politics_websites": [
        "https://www.whitehouse.gov/",
        "https://www.gov.uk/",
        "https://ec.europa.eu/"
        # Add other government websites as needed
    ],
    "travel_specialized": [
        "https://skift.com/",
        "https://www.travelweekly.com/",
        "https://thepointsguy.com/",
        "https://www.phocuswire.com/"
    ],
    "travel_general": [
        "https://www.nytimes.com/section/travel",
        "https://www.latimes.com/travel",
        "https://www.cntraveler.com/"
    ],
    "stock_market": [
        "https://www.bloomberg.com/",
        "https://www.reuters.com/",
        "https://www.wsj.com/",
        "https://www.cnbc.com/",
        "https://www.marketwatch.com/"
    ]
}

# # Example of how to access the lists:
# climate_tech_sites = news_sources["climate_tech_general"]
# print(climate_tech_sites)

# # Example of iterating through a list within the dictionary:
# for site in news_sources["travel_specialized"]:
#     print(site)

# # Example of accessing a specific site:
# first_travel_site = news_sources["travel_specialized"][0]
# print(first_travel_site)