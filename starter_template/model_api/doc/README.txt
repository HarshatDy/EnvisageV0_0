# SummariseMe Project README

## Overview
SummariseMe is an automated, modular pipeline for news aggregation, summarization, and image enrichment. It fetches news from multiple sources, summarizes and categorizes content using advanced AI models (Google Gemini, OpenAI, DistilBert AI Model), and enriches news items with relevant images via web scraping and cloud APIs. The system is designed for robust, scheduled operation, storing results in MongoDB and Google Cloud Storage, and is extensible for future enhancements.

## Purpose
The project aims to address the overwhelming volume of online news by automating the end-to-end process of news aggregation, summarization, and enrichment. It provides concise, visually enhanced news digests for end users or downstream applications, improving user engagement and decision-making.

## Key Components
1. **Scheduler (Envisage_Schedule.py)**: Orchestrates the entire pipeline, running a sequence of scripts at scheduled times (3:00 AM and 2:45 PM daily) or on demand.
2. **Worker Thread (worker_thread.py)**: Initiates the news retrieval and summarization process using multi-threading and interfaces with the GeminiAPI.
3. **Web Content Controller (envisage_web_ct_ctr.py)**: Transforms summarized news data for web presentation.
4. **Thumbnail Scraper (web_scrapper_thumbnail.py)**: Enriches news categories with relevant images using multi-threading and thread pools.
5. **Thumbnail Push & DB Update (web_scrapper_thumbnail_push.py)**: Uploads images to Google Cloud Storage and updates MongoDB with image URLs.
6. **Gemini API Integration (gemini_api_test_time_based_scrapper_gemini.py)**: Central to news retrieval, categorization, and summarization.
7. **Database Access (mongo.py, sql_connection.py)**: Manages connections to MongoDB and MySQL for data storage.

## Setup Instructions
1. **Environment Setup**:
   - Ensure Python 3.6+ is installed.
   - Install required packages using `pip install -r requirements.txt`.
   - Set up environment variables for API keys, database credentials, and cloud configuration.

2. **Database Configuration**:
   - Configure MongoDB and MySQL connections as per the `mongo.py` and `sql_connection.py` files.

3. **Cloud Storage Setup**:
   - Set up Google Cloud Storage and configure the necessary credentials.

4. **Running the Pipeline**:
   - Execute the scheduler script: `python Envisage_Schedule.py`.
   - For immediate execution, use the `--run-now` flag.

## Usage
- The pipeline runs automatically at scheduled times (3:00 AM and 2:45 PM daily).
- Logs are generated for traceability and debugging.
- Results are stored in MongoDB and Google Cloud Storage.

## Extensibility
- The modular design allows for easy extension and maintenance.
- Each script is independently runnable and testable.

## Conclusion
SummariseMe is a robust, scalable, and extensible news aggregation and enrichment pipeline, leveraging advanced multi-threading, cloud APIs, and resilient scraping techniques. Its modular architecture allows for easy extension and maintenance, while its use of modern DSA and algorithms ensures efficiency and reliability at scale. 