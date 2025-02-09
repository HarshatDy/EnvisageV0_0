from logging_scripts import append_to_log, create_log_file
from datetime import datetime

log_file = f"LOGGING_SCRIPTS_TESTING_{datetime.today().strftime("%d_%m_%Y")}.txt"

create_log_file(log_file)


append_to_log(log_file, "1. The quick brown fox jumps over the lazy dog while birds fly high through clouds.")
append_to_log(log_file, "2. Sunlight streams through window panes casting shadows on ancient wooden floors beneath dusty books.")
append_to_log(log_file, "3. Mountain peaks rise majestically against blue skies as rivers flow steadily downstream toward valleys.")
append_to_log(log_file, "4. Wind whispers secrets through tall grass meadows where butterflies dance among colorful wildflowers.")
append_to_log(log_file, "5. Ocean waves crash rhythmically against rocky shores while seabirds soar gracefully overhead seeking fish.")
append_to_log(log_file, "6. Ancient trees stand sentinel in forgotten forests where moss grows thick on stone paths.")
append_to_log(log_file, "7. Stars twinkle mysteriously in midnight skies as owls hunt silently through darkened woods below.")
append_to_log(log_file, "8. Rain drops fall softly on autumn leaves creating patterns of natural art on ground.")
append_to_log(log_file, "9. Desert sands shift endlessly under scorching sun while hawks circle searching for prey below.")
append_to_log(log_file, "10. Snow covered peaks reflect golden sunrise as mountain goats traverse treacherous rocky slopes carefully.")