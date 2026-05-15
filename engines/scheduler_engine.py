from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def init_scheduler(app):
    if not scheduler.running:
        scheduler.start()
        print("✅ Chain scheduler started")
    return scheduler
