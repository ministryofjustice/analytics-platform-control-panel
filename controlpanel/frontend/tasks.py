from celery import shared_task
from time import sleep


@shared_task
def sleep_then_print():
    print("Going to sleep...")
    sleep(3)
    print("Awake!")
    return "Done"
