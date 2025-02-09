import os
from datetime import datetime




def create_log_file(filename):
    """
    Creates a new log file with the given filename if it doesn't exist
    
    Args:
        filename (str): Name/path of the log file to be created
    """
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_path = os.path.join(log_dir, filename)
    print(f"this is thhe log_path {log_path}")
    if not os.path.exists(log_path):
        try:
            with open(log_path, 'w') as file:
                pass  # Just create the file
        except Exception as e:
            print(f"Error creating log file: {str(e)}")

def append_to_log(filename, content):
    """
    Appends the given content to the specified log file
    
    Args:
        filename (str): Name/path of the log file
        content (str): Content to be appended to the file
    """
    log_dir = 'logs'
    log_path = os.path.join(log_dir, filename)
    try:
        with open(log_path, 'a') as file:
            file.write(f"{content}\n")
    except Exception as e:
        print(f"Error appending to log file: {str(e)}")