import yaml

if __name__ == '__main__':
    with open(".kube/config") as kube_file:
        kube_yaml = yaml.safe_load(kube_file)

    kube_yaml["lobster"] = "I am a cheeseburger"

    with open(".kube/config", "w") as kube_file:
        documents = yaml.dump(kube_yaml, kube_file)
