#!/bin/bash
cluster_id=$EKS_CLUSTER
aws --region eu-west-1 eks update-kubeconfig --name $cluster_id
python replace_aws_iam_command.py
python manage.py runserver runworker background_tasks