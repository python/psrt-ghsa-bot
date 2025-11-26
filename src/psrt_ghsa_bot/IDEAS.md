- When someone @'s the bot, since they are a real user, can we use GH api
 to find all mentions from their notification and act on that instead of scraping?
 that would mean we wouldnt have to keep state tracking and processing things
 "AFTER or ON" whenever the gh action ran las based on state
- If Playwright action runs before cron action, should we have playwright kick it off
  so that the right groups are assigned?
