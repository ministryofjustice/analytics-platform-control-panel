#!/bin/bash
# cluster_id=$(aws --region eu-west-1 eks list-clusters --output text |  sed -n 1p| awk '{print $2}')
cluster_id=$EKS_CLUSTER
aws --region eu-west-1 eks update-kubeconfig --name $cluster_id
python replace_aws_iam_command.py
python manage.py runserver 0.0.0.0:8000
