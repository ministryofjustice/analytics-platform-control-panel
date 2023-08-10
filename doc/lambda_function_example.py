import json
import requests
import os


def _get_access_token():
    request_headers = {
        "content-type": "application/x-www-form-urlencoded"
    }
    token_url = f'https://{os.environ["AUTH0_OIDC_DOMAIN"]}/oauth/token'
    data = {
        'client_id': os.environ['CLIENT_ID'],
        'client_secret': os.environ['CLIENT_SECRET'],
        'audience': os.environ['AUDIENCE'],
        'grant_type': os.environ['GRANT_TYPE'],
    }
    response = requests.post(
        url=token_url,
        data=data,
        headers=request_headers
    )
    try:
        content = json.loads(response.text)
        if content.get("access_token"):
            print("got the access_token")
            return content.get("access_token")
        else:
            raise Exception(response.text)
    except ValueError:
        raise Exception("No result is returned")


def _get_user_info(access_token, user_id):
    request_headers = {
        "content-type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    user_api_url = f'{os.environ["CPANEL_API_URL"]}/users/{user_id}'
    response = requests.get(
        url=user_api_url,
        headers=request_headers
    )
    try:
        print("getting user_info from cpanel.")
        return json.loads(response.text)
    except ValueError:
        raise Exception("No result is returned")


def create_user_in_data_catalogue(user_info):
    request_headers = {
        "content-type": "application/json",
        "Authorization": f'Bearer {os.environ["OPEN_METADATA_JWT_TOKEN"]}'
    }
    api_url = f'{os.environ["OPEN_METADATA_API_DOMAIN"]}/users'
    data = {
        'displayName': user_info.get("username"),
        'email': user_info.get("email"),
        'name': user_info.get("username")
    }
    response = requests.post(
        url=api_url,
        json=data,
        headers=request_headers
    )
    try:
        content = json.loads(response.text)
        if content.get("id"):
            print("user has been created")
            return content
        else:
            print(response.text)
            raise Exception(response.text)
    except ValueError:
        raise Exception("No result is returned")


def process_user(user_id):
    access_token = _get_access_token()
    user_info = _get_user_info(access_token, user_id)
    try:
        created_user = create_user_in_data_catalogue(user_info)
        if created_user:
            print(created_user)
    except Exception as ex:
        print(f"Failed to create the user {user_id}. due to error {str(ex)}")


def lambda_handler(event, context):
    print("testing....")
    for record in event["Records"]:
        print(record['body'])
        try:
            body_message = json.loads(record['body'])
            if body_message.get('user_id'):
                process_user(body_message.get('user_id'))
        except ValueError:
            pass
    return {
        'statusCode': 200,
        'body': json.dumps('ok')
    }
