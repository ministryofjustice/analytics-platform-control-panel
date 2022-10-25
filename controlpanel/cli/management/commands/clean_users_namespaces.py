import types
from datetime import date
from time import time
from dateutil.relativedelta import relativedelta
import csv

from django.core.management.base import BaseCommand, CommandError
from controlpanel.api.models.user import User
from controlpanel.api import cluster


class Command(BaseCommand):
    help = "Clean up users' namespace either based on the time that users haven't logged in CP for >= n months, or you " \
           "can provide the list of users you want to clean"

    def add_arguments(self, parser):
        parser.add_argument("-m", "--months", type=int,
                            help="input: The minimum idle months for an user to keep his/her namespace")
        parser.add_argument("-u", "--users", type=str,
                            help="input: The list of users in csv file whose namespace will be cleaned up")
        parser.add_argument("-l", "--log", type=str,
                            help="output: The path of recording the list of users whose "
                                 "namespace has been removed and other log information")
        parser.add_argument("-dr", "--dry-run", type=bool, default=False,
                            help="input: An option for not committing actual action but showing what will be done")

    def _log_info(self, info):
        with open(self._log_file_name, "a") as f:
            f.write(info)
            f.write("\n")

    def _read_scope_of_the_users(self, month_ago_number):
        months_ago = date.today() + relativedelta(months=-month_ago_number)
        inactive_user_list = User.objects.filter(last_login__lte=months_ago)
        return inactive_user_list

    def _clear_users_namespaces(self, user_list, dry_run=False):
        for counter, user in enumerate(user_list):
            cluster_user_instance = cluster.User(user)
            if cluster_user_instance.has_required_installation_charts():
                self.stdout.write(f"{str(counter)} - Removing namespace for username: {user.slug}")
                try:
                    cluster_user_instance.delete_user_helm_charts(dry_run=dry_run)
                    self._log_info(f"{user.slug}, {str(user.last_login)} : namespace has been removed")
                except Exception as ex:
                    self.stdout.write(f"{str(counter)} - Encountered error for username: {str(ex)}")
            else:
                self._log_info(f"{user.slug}, {str(user.last_login)} : no namespace exist")
                self.stdout.write(f"{str(counter)} - Removing namespace for username: {user.slug}")

    def _read_user_from_csv(self, user_csv_file):
        user_list = []
        with open(user_csv_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            next(csv_reader, None)
            for row in csv_reader:
                # mock User object to be consistent and also can be used as input when creating a User class
                user_obj = types.SimpleNamespace()
                user_obj.slug = row[0].strip()
                user_obj.last_login = row[1].strip()
                user_obj.email = "notexist@test.com"
                user_obj.name = user_obj.slug
                user_list.append(user_obj)
        return user_list

    def _print_out_user_list(self, user_list):
        self.stdout.write("Please check the following user list")
        for user in user_list:
            self.stdout.write(f"username: {user.slug}, last_login: {str(user.last_login)}")

    def handle(self, *args, **options):
        if not options.get('months') and not options.get('users'):
            raise CommandError("Please specific the months which will be used to query user table or "
                               "provide the csv file which has the list of users")

        self._log_file_name = options.get('log') or "./cleaning_namespaces_{}.log".format(int(time()))

        if options.get('users'):
            user_list = self._read_user_from_csv(options.get('users'))
        else:
            user_list = self._read_scope_of_the_users(options.get('months'))

        self._print_out_user_list(user_list)
        choice = input("Are you sure to clean the namespace for the following users?(Y/N)")
        if choice.lower() == 'y':
            self._clear_users_namespaces(user_list, dry_run=options.get('dry_run', False))
