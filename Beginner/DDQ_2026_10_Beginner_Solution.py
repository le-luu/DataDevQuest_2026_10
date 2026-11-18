"""
DataDevQuest - DDQ2026_10
Challenged By: Pablo Gomez
Level: Beginner
Created By: Le Luu

Objective: Export the same view as PNG and SVG with the REST API, then ask an AI to write alt text and a short summary from the PNG.
Challenge Link: https://datadevquest.com/challenges/ddq2026-10-describe-a-tableau-view-with-ai-beginner
"""
import pandas as pd
import json
import tableauserverclient as TSC
from dotenv import load_dotenv
import os 
import requests

# Get token and site id from Tableau Server/ Cloud
def get_token(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID):
    url = SERVER_ADDRESS + "api/3.29/auth/signin"
    payload = json.dumps({
        "credentials": {
            "personalAccessTokenName": PAT_NAME,
            "personalAccessTokenSecret": PAT_SECRET,
            "site": {
                "contentUrl": SITE_ID
            }
        }
    })
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    response.raise_for_status()
    credentials = response.json()['credentials']
    return credentials['token'], credentials['site']['id']


# List workbooks from Tableau Server/ Cloud with metadata API via TSC
def list_workbook_views(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID, workbook_name):
    tableau_auth = TSC.PersonalAccessTokenAuth(token_name=PAT_NAME, personal_access_token=PAT_SECRET, site_id=SITE_ID)
    server = TSC.Server(SERVER_ADDRESS, use_server_version=True)

    query = f"""
        query get_view_workbooks($workbook_name: String) {{
            workbooks(filter:{{name: $workbook_name}}){{
                id
                name
                views{{
                    luid
                    name
                }}
            }}
        }}
    """

    with server.auth.sign_in(tableau_auth):
        response = server.metadata.query(query, variables={"workbook_name": workbook_name})
    return response

# Parse the response from the metadata API to extract workbook information
def parse_workbooks_response(response):
    workbooks = response['data']['workbooks']
    workbook_list = []
    for workbook in workbooks:
        workbook_list.append({
            "id": workbook['id'],
            "name": workbook['name'],
            "views": [{"luid": view['luid'], "name": view['name']} for view in workbook['views'] if view.get('luid')]
        })
    return workbook_list

# Download the image of a specific view from Tableau Server/ Cloud with 2 formats: PNG and SVG
def get_view_image(SERVER_ADDRESS, site_luid, view_id, token, file_name, img_dir, viz_width=1200, viz_height=900):

    url = f"{SERVER_ADDRESS}api/3.29/sites/{site_luid}/views/{view_id}/image"
    url2 = f"{SERVER_ADDRESS}api/3.29/sites/{site_luid}/views/{view_id}/image?format=SVG"

    payload = {}
    headers = {
        'X-Tableau-Auth': token
    }
    size_params = {"vizWidth": viz_width, "vizHeight": viz_height}

    for image_url, extension in [(url, "png"), (url2, "svg")]:
        response = requests.request("GET", image_url, headers=headers, params=size_params, data=payload)
        response.raise_for_status()

        file_path = os.path.join(img_dir, f"{file_name}.{extension}")
        with open(file_path, "wb") as f:
            f.write(response.content)
        print(f"Saved image to {file_path}")

# Ask user to choose the view
def choose_view(views):
    views_by_name = {view['name'].lower(): view for view in views}
    while True:
        view_name = input("\nEnter the view name to download: ").strip()
        if view_name.lower() in views_by_name:
            return views_by_name[view_name.lower()]
        print(f"'{view_name}' is not a view in this workbook. Please choose one of the names above.")


def main():

    # Load environment variables from .env file
    load_dotenv()
    PAT_NAME = os.getenv("PAT_NAME")
    PAT_SECRET = os.getenv("PAT_SECRET")
    SERVER_ADDRESS = os.getenv("SERVER_ADDRESS")
    SITE_ID = os.getenv("SITE_ID")


    workbooks_response = list_workbook_views(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID, "Superstore")
    workbooks_list = parse_workbooks_response(workbooks_response)
    print("===================================================")
    print(f"Views for workbook ===> {workbooks_list[0]['name']} <===")
    print("===================================================\n")

    for view in workbooks_list[0]['views']:
        print(f"View Name: {view['name']} \n--->>>  LUID: {view['luid']}")

    selected_view = choose_view(workbooks_list[0]['views'])


    token, site_luid = get_token(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID)

    img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
    os.makedirs(img_dir, exist_ok=True)

    get_view_image(SERVER_ADDRESS, site_luid, selected_view['luid'], token, workbooks_list[0]['name'] + "_" + selected_view['name'], img_dir)

if __name__ == "__main__":
    main()