from os import environ

import yaml

if __name__ == '__main__':
    with open(".kube/config") as kube_file:
        kube_yaml = yaml.safe_load(kube_file)


    kube_yaml["users"][0]["user"]["exec"]["command"] = "aws"

    args = kube_yaml["users"][0]["user"]["exec"]["args"]

    cluster_id = args[-1]

    user_iam = kube_yaml["users"][0]["name"]

    region = user_iam.replace("arn:aws:eks:","").split(":")[0]
    new_args = [
        "--region",
        region,
        "eks",
        "get-token",
        "--cluster-name",
        cluster_id,
        "--profile",
        "admin-dev"
    ]
    kube_yaml["users"][0]["user"]["exec"]["args"] = new_args

    with open(".kube/config", "w") as kube_file:
        documents = yaml.dump(kube_yaml, kube_file)
