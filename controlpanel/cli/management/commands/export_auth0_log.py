# Third-party
from django.core.management.base import BaseCommand, CommandError

import pandas
from datetime import datetime
from time import time

from controlpanel.api import auth0
from auth0.v3.management.logs import Logs


class Command(BaseCommand):
    """
    Due to the limitation in place for pulling log from auth0 via API
    https://auth0.com/docs/deploy-monitor/logs/retrieve-log-events-using-mgmt-api#limitations
    we cannot use the APIs which allow us to filter out the logs based on time frame or other conditions
    we can only get the logs for wider time window by using log_id

    The script has the assumption for the format of log id
    900<YYYY><MM><DD><HH><MM>....
    and the length is 56
    We will generate the log_id based on the start_date and end_date based on the above format
    """
    help = "Export auth log from auth0"

    BASE_CSV_FILE_FOR_AUTH0_LOG = 'auth0_log_result'

    LOG_ID_LENGTH = 56
    LOG_ID_PREFIX = "900"
    BREAKING_POINT_FOR_STORAGE = 500
    LOG_AMOUNT_TO_TAKE = 100

    def add_arguments(self, parser):
        parser.add_argument("start_date", type=str, help="start date (format: YYYY-MM-DD for the log")
        parser.add_argument("end_date", type=str, help="end date (format: YYYY-MM-DD) for the log")

    def read_logs_by_log_id(self, auth0_logs, require_header, start_log_id, end_id, csv_file_name):
        logs = auth0_logs.search(from_param=start_log_id, take=self.LOG_AMOUNT_TO_TAKE)
        is_empty = (len(logs) == 0)
        if is_empty:
            return True, None
        df = pandas.DataFrame(logs)
        df.to_csv(csv_file_name,
                  mode="a",
                  header=require_header,
                  index=False,
                  compression="gzip")
        current_end_log_id = logs[-1].get("log_id")
        if current_end_log_id >= end_id:
            return True, None
        return False, current_end_log_id

    def generate_log_id(self, date_in_string):
        log_id = f"{self.LOG_ID_PREFIX}{date_in_string.replace('-', '')}"
        return log_id.ljust(self.LOG_ID_LENGTH, "0")

    def export_auth0_to_csv(self, start_date: str, end_date: str):
        auth0_instance = auth0.ExtendedAuth0()
        auth0_logs = Logs(auth0_instance.domain, auth0_instance._token, timeout=30)

        start_log_id = self.generate_log_id(start_date)
        end_log_id = self.generate_log_id(end_date)
        base_csv_file_name = f"{self.BASE_CSV_FILE_FOR_AUTH0_LOG}_{int(time())}"

        file_cnt = 1
        page_no = 1
        is_finished = False
        require_header = True
        next_log_id = start_log_id
        while not is_finished:
            csv_file_name = f"{base_csv_file_name}_{file_cnt}.csv.gzip"
            is_finished, next_log_id = self.read_logs_by_log_id(
                auth0_logs, require_header, next_log_id, end_log_id, csv_file_name)
            if page_no == self.BREAKING_POINT_FOR_STORAGE:
                page_no = 1
                file_cnt += 1
                require_header = True
                self.stdout.write(f"Finished the file {file_cnt} for storing logs")
            else:
                page_no += 1
                require_header = False
                self.stdout.write(f"----Finished processing the page {page_no} of logs")

    def validate_date_string(self, date_string):
        try:
            datetime.strptime(date_string, "%Y-%m-%d")
        except ValueError:
            raise CommandError("date string is not valid format, it should be YYYY-MM-DD")

    def handle(self, *args, **options):
        self.validate_date_string(options["start_date"])
        self.validate_date_string(options["end_date"])
        self.export_auth0_to_csv(options["start_date"], options["end_date"])
