import requests
import json

#############################################
# Configuration
#############################################

# Sonarr configuration
sonarr_host = 'XXXX'  # e.g., 'localhost' or IP address
sonarr_port = '8989'
sonarr_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue/details'
sonarr_api_key = 'XXXX'

# Radarr configuration
radarr_host = 'localhost'
radarr_port = '7878'
radarr_url = f'http://{radarr_host}:{radarr_port}/api/v3/queue/details'
radarr_api_key = 'XXXX'

# Choose torrent client: set to either 'transmission' or 'qbittorrent'
torrent_client = 'transmission'  # Change to 'qbittorrent' if desired

# Transmission configuration (only used if torrent_client == 'transmission')
transmission_url = 'http://XXXX:9091/transmission/rpc'
transmission_username = 'username'
transmission_password = 'password'

# qBittorrent configuration (only used if torrent_client == 'qbittorrent')
qbittorrent_url = 'http://XXXX:8080'
qb_username = 'username'
qb_password = 'password'

#############################################
# Functions
#############################################

# Fetch the download queue from Sonarr/Radarr
def fetch_queue(api_url, api_key):
    headers = {'X-Api-Key': api_key}
    response = requests.get(api_url, headers=headers)
    return response.json()

# Remove (and block) a download via Sonarr/Radarr API
def remove_and_block_download(api_url, api_key, download_id, block_torrent=False):
    params = {
        'removeFromClient': True,
        'blocklist': block_torrent,  # Block the torrent if True
        'skipRedownload': True
    }
    delete_url = f'{api_url}/{download_id}'
    headers = {
        'X-Api-Key': api_key,
        'Content-Type': 'application/json'
    }
    response = requests.delete(delete_url, headers=headers, params=params)
    if response.status_code == 200:
        print(f"Successfully removed download {download_id} from queue.")
    else:
        print(f"Failed to remove download {download_id}. Response: {response.status_code} - {response.text}")

#############################################
# Transmission-related functions
#############################################

def get_transmission_session_id():
    response = requests.post(transmission_url, auth=(transmission_username, transmission_password))
    if 'X-Transmission-Session-Id' in response.headers:
        return response.headers['X-Transmission-Session-Id']
    return None

def get_transmission_torrent_files(session_id, torrent_hash):
    payload = {
        "method": "torrent-get",
        "arguments": {
            "fields": ["files"],
            "ids": [torrent_hash]
        }
    }
    headers = {
        'X-Transmission-Session-Id': session_id,
        'Content-Type': 'application/json'
    }
    response = requests.post(transmission_url, headers=headers, json=payload,
                             auth=(transmission_username, transmission_password))
    if response.status_code == 200:
        return response.json().get('arguments', {}).get('torrents', [])
    elif response.status_code == 409:
        # If session ID expired, refresh and retry
        new_session_id = get_transmission_session_id()
        headers['X-Transmission-Session-Id'] = new_session_id
        response = requests.post(transmission_url, headers=headers, json=payload,
                                 auth=(transmission_username, transmission_password))
        if response.status_code == 200:
            return response.json().get('arguments', {}).get('torrents', [])
        else:
            print(f"Error fetching torrent files: {response.text}")
            return None
    else:
        print(f"Error fetching torrent files: {response.text}")
        return None

#############################################
# qBittorrent-related functions
#############################################

# We'll use a session to handle authentication cookies
qb_session = None

def qbittorrent_login():
    global qb_session
    qb_session = requests.Session()
    login_url = f'{qbittorrent_url}/api/v2/auth/login'
    payload = {'username': qb_username, 'password': qb_password}
    r = qb_session.post(login_url, data=payload)
    if r.text != "Ok.":
        print("Failed to log in to qBittorrent")
        qb_session = None
    else:
        print("Logged in to qBittorrent successfully.")

def get_qbittorrent_torrent_files(torrent_hash):
    if qb_session is None:
        print("qBittorrent session is not established.")
        return None
    url = f'{qbittorrent_url}/api/v2/torrents/files'
    params = {'hash': torrent_hash}
    response = qb_session.get(url, params=params)
    if response.status_code == 200:
        # qBittorrent returns a list of file objects
        return response.json()
    else:
        print(f"Error fetching qBittorrent torrent files: {response.text}")
        return None

#############################################
# Initialization of the torrent client session
#############################################

if torrent_client.lower() == 'transmission':
    transmission_session_id = get_transmission_session_id()
    if not transmission_session_id:
        print("Failed to get Transmission session ID.")
elif torrent_client.lower() == 'qbittorrent':
    qbittorrent_login()

#############################################
# Main processing: Check queues and verify torrent file names
#############################################

for app_name, api_url, api_key in [
    ('Sonarr', sonarr_url, sonarr_api_key),
    ('Radarr', radarr_url, radarr_api_key)
]:
    downloads_data = fetch_queue(api_url, api_key)
    downloads = []
    downloadIds = []

    #Filetring multi-file downloads to check them only once

    for elem in downloads_data:
        downloadId = elem["downloadId"]
        if downloadId not in downloadIds:
            downloads.append(elem)
            downloadIds.append(downloadId)
    
    if isinstance(downloads, list):
        for download in downloads:
            # The 'downloadId' is assumed to be the torrent hash
            torrent_hash = download['downloadId']
            title = download['title']
            
            # Get the torrent file list using the chosen client's API
            torrent_files = None
            if torrent_client.lower() == 'transmission':
                torrent_files = get_transmission_torrent_files(transmission_session_id, torrent_hash)
            elif torrent_client.lower() == 'qbittorrent':
                torrent_files = get_qbittorrent_torrent_files(torrent_hash)
            
            if torrent_files:
                print(f"Checking torrent contents for: {title}")
                remove_torrent_flag = False

                if torrent_client.lower() == 'transmission':
                    # For Transmission, the response is a list of torrents with a "files" key.
                    for torrent in torrent_files:
                        for file in torrent.get('files', []):
                            filename = file.get('name', '')
                            if filename.endswith(('.zipx', '.lnk', '.arj')):
                                print(f"Identified suspicious file: {filename}. Marking download for removal...")
                                remove_torrent_flag = True
                                break
                        if remove_torrent_flag:
                            break

                elif torrent_client.lower() == 'qbittorrent':
                    # For qBittorrent, the API returns a list of file objects directly.
                    for file in torrent_files:
                        filename = file.get('name', '')
                        if filename.endswith(('.zipx', '.lnk', '.arj')):
                            print(f"Identified suspicious file: {filename}. Marking download for removal...")
                            remove_torrent_flag = True
                            break

                if remove_torrent_flag:
                    remove_and_block_download(api_url, api_key, download['id'], block_torrent=True)
            else:
                print(f"Failed to fetch torrent info for {title} in {app_name}")
    else:
        print(f"Unexpected data structure from {app_name} API. Expected a list.")

