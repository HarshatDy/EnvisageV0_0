import os
import datetime
from google.cloud import storage
from dotenv import load_dotenv
import json # Added for pretty printing the result
import argparse # Added for command-line flags
import re # Added for parsing article ID

# --- START MongoDB Import ---
# Assuming 'db' is initialized in a 'mongo.py' file in the same directory or accessible path
try:
    from mongo import db
    print("Successfully imported MongoDB connection.")
except ImportError:
    print("Error: Could not import MongoDB connection 'db' from 'mongo'. Database operations will fail.")
    db = None # Set db to None to handle the error gracefully later
# --- END MongoDB Import ---


def push_images_to_gcs(local_image_dir):
    """
    Uploads images from a local directory structure (category/image.ext)
    to Google Cloud Storage, organizing them by date and category.

    Args:
        local_image_dir (str): The path to the local directory containing
                                 category subdirectories with images.
    """
    load_dotenv()

    project_id = os.getenv("PROJECT_ID")
    bucket_name = os.getenv("BUCKET_NAME")
    key_filename = os.getenv("KEYFILENAME")

    if not all([project_id, bucket_name, key_filename]):
        print("Error: Missing required environment variables (PROJECT_ID, BUCKET_NAME, KEYFILENAME)")
        return

    try:
        storage_client = storage.Client.from_service_account_json(key_filename)
        bucket = storage_client.bucket(bucket_name)
        print(f"Connected to bucket: {bucket_name}")
    except Exception as e:
        print(f"Error connecting to GCS: {e}")
        return

    # Get the base directory name (e.g., 2025-04-06_1800)
    base_dir_name = os.path.basename(local_image_dir.rstrip(os.sep))
    gcs_top_level_folder = base_dir_name # Default in case formatting fails

    # Try to convert YYYY-MM-DD_HHMM to YYYY-MM-DD_HH:MM
    try:
        date_part_str, time_part_str = base_dir_name.rsplit('_', 1)
        # Validate date part format
        datetime.datetime.strptime(date_part_str, '%Y-%m-%d')
        if len(time_part_str) == 4 and time_part_str.isdigit():
            # Format time part as HH:MM
            gcs_top_level_folder = f"{date_part_str}_{time_part_str[:2]}:{time_part_str[2:]}"
            print(f"Using GCS top-level folder: {gcs_top_level_folder}")
        else:
            print(f"Warning: Time part '{time_part_str}' in '{base_dir_name}' doesn't match HHMM format. Using original name for GCS path.")
    except ValueError:
        print(f"Warning: Directory name '{base_dir_name}' doesn't match YYYY-MM-DD_HHMM format. Using original name for GCS path.")

    print(f"Scanning directory: {local_image_dir}")
    for category_dir in os.listdir(local_image_dir):
        category_path = os.path.join(local_image_dir, category_dir)
        if os.path.isdir(category_path):
            # Use the actual category directory name from the filesystem
            gcs_category_folder = category_dir
            print(f"Processing category: {gcs_category_folder}")
            for filename in os.listdir(category_path):
                local_file_path = os.path.join(category_path, filename)
                if os.path.isfile(local_file_path):
                    try:
                        # Construct the destination blob name using the formatted top-level folder
                        blob_name = f"{gcs_top_level_folder}/{gcs_category_folder}/{filename}"
                        blob = bucket.blob(blob_name)

                        print(f"Uploading {local_file_path} to gs://{bucket_name}/{blob_name}...")
                        blob.upload_from_filename(local_file_path)
                        print(f"Successfully uploaded {filename}")

                    except Exception as e:
                        print(f"Error uploading {filename}: {e}")

    print("Finished uploading images.")

def get_image_urls_from_gcs(gcs_folder_path):
    """
    Retrieves public URLs of images from a specified folder in GCS.

    Args:
        gcs_folder_path (str): The path within the bucket (e.g., '2025-04-06_18:00').

    Returns:
        dict: A dictionary where keys are category names and values are lists
              of public image URLs for that category. Returns None on error.
    """
    load_dotenv()

    project_id = os.getenv("PROJECT_ID")
    bucket_name = os.getenv("BUCKET_NAME")
    key_filename = os.getenv("KEYFILENAME")

    if not all([project_id, bucket_name, key_filename]):
        print("Error: Missing required environment variables (PROJECT_ID, BUCKET_NAME, KEYFILENAME)")
        return None

    try:
        storage_client = storage.Client.from_service_account_json(key_filename)
        bucket = storage_client.bucket(bucket_name)
        print(f"Connected to bucket: {bucket_name} for retrieving URLs.")
    except Exception as e:
        print(f"Error connecting to GCS: {e}")
        return None

    image_urls_by_category = {}
    prefix = f"{gcs_folder_path}/"
    print(f"Listing blobs with prefix: gs://{bucket_name}/{prefix}")

    try:
        blobs = bucket.list_blobs(prefix=prefix)
        count = 0
        for blob in blobs:
            count += 1
            # Ensure we don't process the folder itself if it appears as a blob
            if blob.name == prefix:
                continue

            # Extract category and filename from blob name
            # Example blob.name: 2025-04-06_18:00/Category_Name/image.jpg
            relative_path = blob.name[len(prefix):] # e.g., Category_Name/image.jpg
            parts = relative_path.split('/')
            if len(parts) == 2:
                category_name = parts[0]
                # filename = parts[1] # Not strictly needed here

                if category_name not in image_urls_by_category:
                    image_urls_by_category[category_name] = []

                # Ensure the image has public access configured in GCS for public_url to work reliably
                # Or consider generating signed URLs if access needs to be controlled/temporary
                image_urls_by_category[category_name].append(blob.public_url)
                print(f"Found URL: {blob.public_url} for category {category_name}")
            else:
                print(f"Warning: Skipping blob with unexpected path format: {blob.name}")

        if count == 0:
             print(f"No blobs found matching prefix: {prefix}")
        else:
             print(f"Processed {count} blobs.")


    except Exception as e:
        print(f"Error listing or processing blobs: {e}")
        return None

    return image_urls_by_category


# --- START New Function: update_mongodb_with_image_urls ---
def update_mongodb_with_image_urls(date_time_string):
    """
    Fetches image URLs from GCS for a given date/time folder, matches them
    to newsItems in MongoDB based on article ID, and updates the MongoDB
    document with an 'images' list for each newsItem.

    Args:
        date_time_string (str): The date and time string (e.g., '2025-04-06_18:00')
                                used as the key in MongoDB and folder name in GCS.
    """
    # Check if db object is None instead of using boolean evaluation
    if db is None: 
        print("MongoDB connection is not available. Cannot update database.")
        return

    print(f"Starting MongoDB update process for date: {date_time_string}")

    # 1. Retrieve image URLs from GCS
    gcs_image_data = get_image_urls_from_gcs(date_time_string)
    if gcs_image_data is None:
        print(f"Failed to retrieve image URLs from GCS for {date_time_string}. Aborting DB update.")
        return
    if not gcs_image_data:
        print(f"No image URLs found in GCS for {date_time_string}. Nothing to update in DB.")
        return

    # 2. Process GCS results: Map article ID to image URLs
    urls_by_article_id = {}
    for gcs_category_folder, urls in gcs_image_data.items():
        # Extract article ID (assuming format like '123_CategoryName')
        match = re.match(r"(\d+)_", gcs_category_folder)
        if match:
            article_id_str = match.group(1)
            try:
                article_id = int(article_id_str)
                if article_id not in urls_by_article_id:
                    urls_by_article_id[article_id] = []
                urls_by_article_id[article_id].extend(urls)
                print(f"Mapped {len(urls)} URLs for article ID {article_id} from folder '{gcs_category_folder}'")
            except ValueError:
                print(f"Warning: Could not parse integer ID from folder name '{gcs_category_folder}'")
        else:
            print(f"Warning: Could not extract article ID from GCS folder name '{gcs_category_folder}'")

    if not urls_by_article_id:
        print("Could not map any GCS URLs to article IDs. Aborting DB update.")
        return

    # 3. Fetch the MongoDB document
    try:
        web_collection = db['envisage_web']
        # Query for the document containing the specific date_time_string key
        mongo_doc = web_collection.find_one({f"envisage_web.{date_time_string}": {"$exists": True}})

        if not mongo_doc:
            print(f"Error: MongoDB document for date '{date_time_string}' not found.")
            return

        # Get the specific data structure for the date/time
        daily_data = mongo_doc.get("envisage_web", {}).get(date_time_string)
        if not daily_data or "newsItems" not in daily_data:
            print(f"Error: 'newsItems' not found in MongoDB document for date '{date_time_string}'.")
            return

        news_items_list = daily_data["newsItems"]
        updated_count = 0

        # 4. Update newsItems list in memory
        for item in news_items_list:
            article_id = item.get("id")
            if article_id is not None and article_id in urls_by_article_id:
                item["images"] = urls_by_article_id[article_id]
                print(f"Added/Updated 'images' list for newsItem ID {article_id} with {len(item['images'])} URLs.")
                updated_count += 1
            else:
                # Ensure the 'images' field exists, even if empty, for consistency
                if "images" not in item:
                     item["images"] = []
                print(f"No GCS URLs found for newsItem ID {article_id}. Setting 'images' to empty list.")


        # 5. Perform MongoDB update
        update_field = f"envisage_web.{date_time_string}.newsItems"
        result = web_collection.update_one(
            {"_id": mongo_doc["_id"]},
            {"$set": {update_field: news_items_list}}
        )

        if result.matched_count > 0:
            if result.modified_count > 0:
                print(f"Successfully updated MongoDB document (_id: {mongo_doc['_id']}). Matched: {result.matched_count}, Modified: {result.modified_count}. Updated {updated_count} newsItems with image lists.")
            else:
                 print(f"MongoDB document (_id: {mongo_doc['_id']}) matched but no modifications were needed (data might be identical). Matched: {result.matched_count}")
        else:
            print(f"Error: Failed to match MongoDB document (_id: {mongo_doc['_id']}) for update.")

    except Exception as e:
        print(f"An error occurred during MongoDB operation: {e}")
        import traceback
        traceback.print_exc()

# --- END New Function ---

def get_default_datetime_strings():
    """
    Determines the appropriate date-time string based on current time:
    - Between 6am and 6pm (current day): Uses current day with 18:00 timestamp
    - Between 6pm and midnight (current day): Uses next day with 06:00 timestamp
    - Between midnight and 6am (current day): Uses current day with 06:00 timestamp

    Returns:
        tuple: (gcs_format, dir_format) where:
               - gcs_format is "YYYY-MM-DD_HH:MM" 
               - dir_format is "YYYY-MM-DD_HHMM"
    """
    current_time = datetime.datetime.now()
    current_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Define time thresholds
    morning_threshold = current_day.replace(hour=6)  # 6am current day
    evening_threshold = current_day.replace(hour=18)  # 6pm current day
    
    # Determine which time slot to use
    if morning_threshold <= current_time < evening_threshold:
        # Between 6am and 6pm current day -> use current day 18:00
        target_date = current_day
        hour_str = "18:00"
        hour_dir_str = "1800"
    else:
        if current_time < morning_threshold:
            # Between midnight and 6am -> use current day 06:00
            target_date = current_day
        else:
            # Between 6pm and midnight -> use next day 06:00
            target_date = current_day + datetime.timedelta(days=1)
        
        hour_str = "06:00"
        hour_dir_str = "0600"
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    # Format strings
    gcs_format = f"{date_str}_{hour_str}"
    dir_format = f"{date_str}_{hour_dir_str}"
    
    return gcs_format, dir_format

# Example usage (assuming you have a directory structure like 'images/cats/cat1.jpg'):
if __name__ == "__main__":
    # Get default datetime strings for our arguments
    default_gcs_folder, default_local_dir = get_default_datetime_strings()
    default_local_dir = f"thumbnail_images/{default_local_dir}"
    
    # --- START Argument Parsing ---
    parser = argparse.ArgumentParser(description="Push images to GCS, retrieve URLs, and/or update MongoDB.")
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push images from the local directory to Google Cloud Storage."
    )
    parser.add_argument(
        "--retrieve",
        action="store_true",
        help="Retrieve image URLs from the specified folder in Google Cloud Storage."
    )
    parser.add_argument(
        "--dir",
        default=default_local_dir,
        help=f"Specify the local directory (e.g., thumbnail_images/YYYY-MM-DD_HHMM) for pushing. Current default: '{default_local_dir}'."
    )
    parser.add_argument(
        "--gcs-folder",
        default=default_gcs_folder,
        help=f"Specify the GCS folder (e.g., YYYY-MM-DD_HH:MM) for retrieving. Current default: '{default_gcs_folder}'."
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="Update MongoDB 'envisage_web' collection with image URLs retrieved from GCS for the specified --gcs-folder date/time."
    )

    args = parser.parse_args()
    # --- END Argument Parsing ---

    local_image_directory = args.dir
    gcs_target_folder = args.gcs_folder # This is the date_time_string like '2025-04-06_18:00'

    action_taken = False # Flag to check if any action was performed

    # --- Conditional Push ---
    if args.push:
        action_taken = True
        print(f"--- Push flag enabled ---")
        if os.path.isdir(local_image_directory):
            print(f"--- Starting Upload from '{local_image_directory}' ---")
            push_images_to_gcs(local_image_directory)
            print(f"--- Upload Finished ---")
        else:
            print(f"Error: Local directory '{local_image_directory}' does not exist.")
            print("Please ensure the thumbnail scraper has run and created this directory, or provide the correct path using --dir.")
            # Optionally exit if push fails due to missing dir?
            # exit(1) 

    # --- Conditional Retrieve ---
    if args.retrieve:
        action_taken = True
        print(f"\n--- Retrieve flag enabled ---")
        print(f"--- Retrieving URLs from GCS folder: {gcs_target_folder} ---")
        retrieved_urls = get_image_urls_from_gcs(gcs_target_folder)

        if retrieved_urls is not None:
            print(f"\n--- Retrieved Image URLs ---")
            # Pretty print the dictionary
            print(json.dumps(retrieved_urls, indent=2))
            print(f"--- Finished Retrieving URLs ---")
        else:
            print("Failed to retrieve image URLs.")

    # --- START Conditional DB Update ---
    if args.update_db:
        action_taken = True
        print(f"\n--- Update DB flag enabled ---")
        # Use the gcs_target_folder as the date/time key for MongoDB
        update_mongodb_with_image_urls(gcs_target_folder)
        print(f"--- Finished DB Update Process ---")
    # --- END Conditional DB Update ---


    # --- No Action Message ---
    if not action_taken:
        print("\nNo action specified. Use --push, --retrieve, or --update-db.")
        parser.print_help()
