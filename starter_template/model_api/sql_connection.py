import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv




def connect_to_mysql_database():
    load_dotenv()
    connection = None
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),          # Database host (usually localhost for local DB)
            user=os.getenv("MYSQL_USERNAME"),      # Your MySQL username
            password=os.getenv("MYSQL_PASSWORD"),  # Your MySQL password
            database=os.getenv("MYSQL_DATABASE")   # Fixed typo: DATABSE → DATABASE
        )
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"Connected to MySQL Server version {db_info}")
            
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            record = cursor.fetchone()
            print(f"You're connected to database: {record[0]}")
            
            return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None
    

def fetch_all_categories(connection):
    try:
        cursor = connection.cursor(dictionary=True)  # Returns results as dictionaries
        cursor.execute("SELECT * FROM categories;")
        categories = cursor.fetchall()
        
        print("\nCategories:")
        for category in categories:
            print(f"ID: {category['category_id']}, Name: {category['name']}")
            
        return categories
        
    except Error as e:
        print(f"Error while fetching categories: {e}")
        return []
    # 
# fetch_all_categories(connect_to_mysql_database())