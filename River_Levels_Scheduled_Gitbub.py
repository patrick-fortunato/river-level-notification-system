import schedule
import time
import subprocess

def my_task():
    # Run your external script here.
    # Replace "your_script.py" with the actual filename.
    # Users should place the script in the same directory OR update the path.
    subprocess.run(["python", "your_script.py"])

# Schedule the task to run every day at 6 AM
schedule.every().day.at("06:00:00").do(my_task)

# Run the scheduler loop
while True:
    schedule.run_pending()
    time.sleep(1)

