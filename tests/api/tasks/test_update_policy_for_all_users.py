# Third-party
import botocore
import pytest

# First-party/Local
from controlpanel.api.models import User
from controlpanel.api.tasks.update_policy import update_policy


@pytest.mark.django_db
@pytest.mark.parametrize(
    "policy, attach", [("a-test-policy", True), ("analytical-platform-textract-integration", False)]
)
def test_update_policy(iam, users, policy, attach):
    base_arn = "arn:aws:iam::123456789012:policy"
    update_policy(policy, attach)
    role = iam.Role(users["superuser"].iam_role_name)
    attached_policies = list(role.attached_policies.all())
    arns = [policy.arn for policy in attached_policies]
    if attach:
        assert f"{base_arn}/{policy}" in arns
    else:
        assert f"{base_arn}/{policy}" not in arns


@pytest.mark.django_db
def test_update_policy_error(users):
    with pytest.raises(botocore.exceptions.ClientError):
        update_policy("non-existant-policy", True)
