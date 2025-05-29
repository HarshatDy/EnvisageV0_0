import schedule
import time
import subprocess
import os
import datetime
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"schedule_log_{datetime.datetime.now().strftime('%Y_%m_%d')}.txt"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Envisage_Scheduler")

# Get the directory of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script(script_path, args=None):
    """
    Run a Python script as a subprocess and wait for it to complete.
    
    Args:
        script_path (str): Path to the Python script to run
        args (list, optional): Command-line arguments to pass to the script
    
    Returns:
        bool: True if script executed successfully, False otherwise
    """
    try:
        full_path = os.path.join(SCRIPT_DIR, script_path)
        cmd = [sys.executable, full_path]
        
        if args:
            cmd.extend(args)
            
        logger.info(f"Starting: {' '.join(cmd)}")
        
        # Run the process and wait for it to complete
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Capture output
        stdout, stderr = process.communicate()
        
        # Log summary of output
        if stdout:
            logger.info(f"Script output summary: {stdout[:500]}..." if len(stdout) > 500 else f"Script output: {stdout}")
        
        # Check return code
        if process.returncode == 0:
            logger.info(f"Successfully completed: {script_path}")
            return True
        else:
            logger.error(f"Script failed with return code {process.returncode}: {script_path}")
            if stderr:
                logger.error(f"Error details: {stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Exception running {script_path}: {str(e)}")
        return False

def run_task_sequence():
    """Run all scripts in sequence, with each depending on the success of the previous."""
    logger.info("Starting scheduled task sequence")
    
    # Run worker_thread.py
    if run_script("worker_thread.py"):
        logger.info("worker_thread.py completed successfully, proceeding to envisage_web_ct_ctr.py")
        
        # Run envisage_web_ct_ctr.py
        if run_script("envisage_web_ct_ctr.py"):
            logger.info("envisage_web_ct_ctr.py completed successfully, proceeding to web_scrapper_thumbnail.py")
            
            # Run web_scrapper_thumbnail.py
            if run_script("web_scrapper_thumbnail.py"):
                logger.info("web_scrapper_thumbnail.py completed successfully, proceeding to web_scrapper_thumbnail_push.py")
                
                # Run web_scrapper_thumbnail_push.py with --push argument
                if run_script("web_scrapper_thumbnail_push.py", ["--push"]):
                    logger.info("web_scrapper_thumbnail_push.py --push completed successfully, proceeding to update database")
                    
                    # Run web_scrapper_thumbnail_push.py with --update-db argument
                    if run_script("web_scrapper_thumbnail_push.py", ["--update-db"]):
                        logger.info("web_scrapper_thumbnail_push.py --update-db completed successfully. Full sequence complete!")
                        return True
                    else:
                        logger.error("web_scrapper_thumbnail_push.py --update-db failed. Sequence incomplete.")
                        return False
                else:
                    logger.error("web_scrapper_thumbnail_push.py --push failed. Stopping sequence.")
                    return False
            else:
                logger.error("web_scrapper_thumbnail.py failed. Stopping sequence.")
                return False
        else:
            logger.error("envisage_web_ct_ctr.py failed. Stopping sequence.")
            return False
    else:
        logger.error("worker_thread.py failed. Stopping sequence.")
        return False

def main():
    """Main function to schedule and run tasks."""
    logger.info("Envisage Scheduler starting up")
    
    # Schedule the task for 3 AM and 3 PM every day
    schedule.every().day.at("02:45").do(run_task_sequence)
    schedule.every().day.at("14:45").do(run_task_sequence)
    
    logger.info("Scheduler set for daily runs at 03:00 AM and 03:00 PM")
    
    # Run immediately if requested via command line
    if len(sys.argv) > 1 and sys.argv[1] == "--run-now":
        logger.info("Running task sequence immediately due to --run-now flag")
        run_task_sequence()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.critical(f"Unexpected error: {str(e)}")
        raise

