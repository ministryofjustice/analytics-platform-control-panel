# Third-party
import botocore
from django.core.management.base import BaseCommand

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models.user import User


class Command(BaseCommand):
    help = "Attaches a policy to all users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--policy-name",
            "-pn",
            type=str,
            help="Name of the policy to attach to all users",
        )

        parser.add_argument(
            "--attach",
            "-a",
            default=True,
            type=lambda x: (str(x).lower() == "true"),
            help="whether to attach or remove policy",
        )

    def handle(self, *args, **options):
        policy_name = options.get("policy_name", None)
        attach = options.get("attach")

        if not policy_name:
            self.stdout.write("Please provide a policy name using --policy-name")
            return

        users = User.objects.filter(auth0_id__startswith="github|")

        for user in users:
            try:
                cluster.User(user).update_policy_attachment(policy=policy_name, attach=attach)
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchEntity":
                    self.stdout.write(f"Failed to attach policy to user '{user.username}': {e}")

                    if "does not exist or is not attachable" in e.response["Error"]["Message"]:
                        raise e
                elif e.response["Error"]["Code"] == "InvalidInput":
                    self.stdout.write(f"Policy name is invalid: {e}")
                    raise e
