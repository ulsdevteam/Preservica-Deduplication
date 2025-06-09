import json
import requests
import xml.etree.ElementTree as ET
import sys
import csv
import logging
import configparser

logging.basicConfig(level=logging.INFO)

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
    logging.debug(f"file to use: {sys.argv[1]}")
    input_file_name = sys.argv[1].split(".")[0]

# create report log name from command line file


access_token = None


def login():
    """
    Generate an authentication token for the Preservica API

    Uses global variables of baseURL, username, and password.
    Returns an access token
    Terminates with an exit(1) on API error
    """
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
    """
    Move a Preservica object to the Trash folder

    Uses a parameter of the RefId and a global access token
    No returns used
    Errors logged if encountered
    """
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
    """
    Search the Preservica API for a sourceID, per the xip.identifier metadata

    Uses a sourceID parameter for the search data, a global access token, and a boolean parameter to recurse once on an expired session
    Returns the JSON of the search result, or None
    """
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
                "values": ["SourceID "+sourceID.replace(':', '\\:')]
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
    """
    Process search results for a sourceID to ignore, mark authorititive, or delete

    Uses an Islandora sourceId, and existing authoritative Preservica RefId
    No returned data
    Delete and Update actions are captured by warning level logging, multiple authoritative objects are captured by error level logging.

    We'll check if a match is exact, then check if the matched object has been procesed by Preservation
    Items processed by Preservation (moved out of IslandoraIngests) should be considered authoritative
    If a Preservica object is already deleted, or is already authoritative, no action is needed
    If a Preservica object duplicates an already authoritative object, it should be deleted
    If a Preservica object existing authoritative reference differs from the processed object, it should be updated
    """

    response_json = api_request(sourceID)
    if not response_json:
        return 
   
    total_hits = int(response_json["value"]["totalHits"])

    if total_hits == 0:
        logging.info(f"no preservica refs attached to this {sourceID}")
        return
    else: logging.info(f"{total_hits} matches for {sourceID}")

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
                    if 'SourceID '+sourceID == identifier:
                        matched = True
                        logging.info(f"exact match for {sourceID} and {identifier} on {obj_id}")
            if data["name"] == "xip.top_level_so": 
                parent = data["value"][0]

        if matched:
            logging.info(f"parent is {parent} and {authoritative_ref} authoritative")
            if parent == trash_folder_ref:
                logging.info(f"{obj_id} is already deleted")
            elif parent != islandora_ingest_ref:
                if authoritative_ref == None:
                    matched_object_ids.append(obj_id)
                    authoritative_ref = obj_id
                    logging.info(f"{obj_id} has been processed and is authoritative for {sourceID}")
                else:
                    manual_resolution = True
                    logging.error(f"{obj_id} and {authoritative_ref} need manual review for {sourceID}")
            else:
                logging.info(f"{obj_id} is pending")
                matched_object_ids.append(obj_id)

    if manual_resolution or len(matched_object_ids) == 0:
        return

    if authoritative_ref == None:
        if gameraRef in matched_object_ids:
            logging.info(f"using i7 {gameraRef} as authoritative")
            authoritative_ref = gameraRef
        else:
            logging.info(f"using last seen {obj_id} as authoritative")
            authoritative_ref = obj_id 

    for obj_id in matched_object_ids: 
        if obj_id != authoritative_ref:
            logging.warn(f"delete {obj_id} which already exists as {authoritative_ref} for {sourceID}")
            move_to_trash(obj_id)
    if gameraRef != authoritative_ref:
        logging.warn(f"update RELS-EXT {sourceID} from {gameraRef} to {authoritative_ref}")

def main():
    """
    Login to the Preservica API, then process a CSV line by line to check Islandora ID (field 0) and Preservica RefIds (field 3)
    """
    global access_token

    # # pull sourceID and gamera ref
    with open(sys.argv[1], 'r') as csvfile:
        linereader = csv.reader(csvfile)
        access_token = login()
        for line in linereader:
            if line[0].startswith('pitt:'): 
                sourceID = line[0]
                gameraRef = line[3]
                logging.info(f"sourceID: {sourceID} and the corresponding ref: {gameraRef}")
                run_query(sourceID, gameraRef)
                logging.info("----------------------------------------------------------------")
    

if __name__ == "__main__":
    main()

