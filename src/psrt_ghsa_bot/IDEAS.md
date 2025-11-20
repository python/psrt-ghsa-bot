- When someone @'s the bot, since they are a real user, can we use GH api
 to find all mentions from their notification and act on that instead of scraping?
 that would mean we wouldnt have to keep state tracking and processing things
 "AFTER or ON" whenever the gh action ran las based on state
- When someone duplicate a coammand we shouldnt run it twice:
 ```
 2025-11-19 21:56:42,654 - __main__ - INFO - Command executed successfully: help
 2025-11-19 21:56:42,655 - __main__ - INFO - Executing command: help from @JacobCoffee on GHSA-j5pm-9w6r-h5rr
 2025-11-19 21:56:46,917 - __main__ - INFO - Command executed successfully: help
 2025-11-19 21:56:46,918 - __main__ - INFO - Checking GHSA: jolt-org/ghsa-testing/GHSA-f3x5-4pp6-r2mf (state: draft)
 ```
 Caused 2 bot responses that were huge, so we should just do one somehow.
- If Playwright action runs before cron action, should we have playwright kick it off
  so that the right groups are assigned?

- When someone duplicate a coammand we shouldnt run it twice:
 ```
 2025-11-19 21:56:42,654 - __main__ - INFO - Command executed successfully: help
 2025-11-19 21:56:42,655 - __main__ - INFO - Executing command: help from @JacobCoffee on GHSA-j5pm-9w6r-h5rr
 2025-11-19 21:56:46,917 - __main__ - INFO - Command executed successfully: help
 2025-11-19 21:56:46,918 - __main__ - INFO - Checking GHSA: jolt-org/ghsa-testing/GHSA-f3x5-4pp6-r2mf (state: draft)
 ```
 Caused 2 bot responses that were huge, so we should just do one somehow.
- for running out of headless, record video, etc. set sentinels in settings.py then use make targets
- if someone has multiple @s in the bot maybe we can process all found