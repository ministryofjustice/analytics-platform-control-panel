#!/bin/bash
python create_aws_conf.py
aws --region eu-west-1 eks update-kubeconfig --name $EKS_CLUSTER --profile=admin-dev
python replace_aws_iam_command.py
python manage.py migrate
