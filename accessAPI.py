import json
import requests
import xml.etree.ElementTree as ET
import sys
import csv
import logging
import configparser

logger = logging.getLogger(__name__)


# read config file to pull username and password
config = configparser.ConfigParser()
config.read('config.ini')

username = config['Login Credentials']['username']
password = config['Login Credentials']['password']
baseURL = config['base URI']['uri']

if len(sys.argv) < 2: 
    print('usage: python3 accessAPI.py <file> ')
    sys.exit(1)
else: 
    logging.info(f"file to use: {sys.argv[1]}")
    input_file_name = sys.argv[1].split(".")[0]

# create report log name from command line file


access_token = None


def login():
    url = baseURL

    data = {
        "username": username,
        "password": password,
        "tenant": "pitt"
    }

    response = requests.post(url, data=data)
    if response.status_code == 200: json_response = response.json() 
    else: 
        err_msg = f"login failed with status code {response.status_code}"
        logging.error(err_msg)
        sys.exit(1)
    
    access_token = json_response['token']
    return access_token


def move_to_trash(ref):
    global access_token

    # Trash folder RefID
    parentRef = '3781eb01-0e98-4b91-a947-65d59be8516f'
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/plain",
    }

    move_url = f"https://pitt.preservica.com/api/entity/information-objects/{ref}/parent-ref"
    response = requests.put(move_url, headers=headers, data=parentRef)
    if response.status_code != 202: 
        err_msg = f"{ref} trouble moving with status code {response.status_code}"
        logging.error(err_msg)
    else: logging.info(f"successfully started {ref} move to {parentRef}")

def api_request(sourceID, is_retry=False):
    global access_token

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/plain",
    }

    query = {
        "q": "",
        "fields": [
            {
                "name": "xip.identifier",
                "values": [sourceID]
            }
        ]
    }
    q = json.dumps(query)

    data = {
        "q": q,
        "start": 0,
        "max": 10,
        "metadata": "xip.title,xip.parent_ref,xip.identifier,xip.top_level_so"
    }

    search_url = "https://pitt.preservica.com/api/content/search"
    response = requests.post(search_url, headers=headers, params=data)
    # Check if the request was successful

    if response.status_code == 401 and is_retry == false: 
        access_token = login()
        return api_request(sourceID, True)
    
    if response.status_code != 200: 
        print(f"Error: {response.status_code}, {response.text}")
        return None
    
    return response.json()



def run_query(sourceID, gameraRef):

    response_json = api_request(sourceID)
    if not response_json:
        return 
   
    total_hits = int(response_json["value"]["totalHits"])

    if total_hits == 0:
        logger.info("no preservica refs attached to this SourceID")
        return
    else: logger.info(f"total hits: {total_hits}")

    # before making the new lists check to see if it's an exact match to the identifiers

    #list of refs and top folder refs
    object_ids = [item.split("|")[1] for item in response_json["value"]["objectIds"]]
    metadata = response_json["value"]["metadata"]

    matched_object_ids =[]
    
    authoritative_ref = None
    islandora_ingest_ref = '54346d6b-e9ec-4cc1-a102-63fb68ac9177'
    trash_folder_ref = '3781eb01-0e98-4b91-a947-65d59be8516f'
    manual_resolution = False

    for i, obj_id in enumerate(object_ids):
        matched = False
        parent = None
        for data in metadata[i]:
            if data["name"] == "xip.identifier":
                for identifier in data["value"]:
                    if 'SourceID pitt:'+sourceID == identifier:
                        matched = True
                        logger.info(f"exact match for {sourceID} and {identifier}")
            if data["name"] == "xip.top_level_so": 
                parent = data["value"][0]

        if matched:
            if parent == trash_folder_ref:
                logger.info(f"{obj_id} is already deleted")
            elif parent != islandora_ingest_ref and authoritative_ref == None:
                matched_object_ids.append(obj_id)
                authoritative_ref = obj_id
            elif parent != islandora_ingest_ref:
                manual_resolution = True
                logger.error(f"{obj_id} and {authoritative_ref} need manual review for {sourceID}")

    if manual_resolution:
        return

    if authoritative_ref == None:
        if gameraRef in matched_object_ids:
            authoritative_ref = gameraRef
        else:
            authoritative_ref = obj_id 

    for obj_id in matched_object_ids: 
        if obj_id != authoritative_ref:
            logger.error(f"{obj_id} already exists as {authoritative_ref} for {sourceID}")
            #move_to_trash(obj_id)

def main():
    global access_token

    logging.basicConfig(filename=input_file_name+'_report.log', level=logging.INFO)
    logging.basicConfig(filename=input_file_name+'_warning.log', level=logging.WARNING)
    logging.basicConfig(filename=input_file_name+'_errors.log', format='%(levelname)s: in function %(funcName)s:%(message)s', level=logging.ERROR)

    # # pull sourceID and gamera ref
    with open(sys.argv[1], 'r') as csvfile:
        linereader = csv.reader(csvfile)
        access_token = login()
        for line in linereader:
            if line[0].startswith('pitt'): 
                sourceID = (line[0]).rsplit( ':' , maxsplit=1)[-1]
                gameraRef = line[3]
                logger.info(f"sourceID: {sourceID} and the corresponding ref: {gameraRef}")
                run_query(sourceID, gameraRef)
                logger.info("----------------------------------------------------------------")
    

if __name__ == "__main__":
    main()

