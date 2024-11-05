import requests
import json
from qbittorrent import Client

# Configuration
sonarr_host = 'xxxx'  # Update with your actual Sonarr host (e.g., 'localhost', '192.168.1.10', etc.)
sonarr_port = '8989'  # Update with the actual port where Sonarr is running
sonarr_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue'
sonarr_api_key = '<api_key>'  # Replace with your actual Sonarr API key

qbit_url = 'http://xxxx:8080'  # Replace with your qBittorrent host and port
qbit_password_needed = False # Is password needed? e.g. No password set, bypass localhost, ...
qbit_username = 'username'  # If qBittorrent has authentication
qbit_password = 'password'

# Fetch the current Sonarr download queue
sonarr_headers = {'X-Api-Key': sonarr_api_key}
response = requests.get(sonarr_url, headers=sonarr_headers)
downloads_data = response.json()

# Now access the 'records' key from the response, which contains the actual download records
downloads = downloads_data.get('records', [])

# Function to get the qb session
def get_qbittorrent_login():
    qb = Client(qbit_url)
    if qbit_password_needed:
        qb.login(qbit_username,qbit_password)
    else:
        qb.login()
    return qb
 
def get_torrent_files(qb, torrent_hash):
    return(qb.get_torrent_files(torrent_hash))

# Function to delete the download from Sonarr's queue and optionally block it
def remove_and_block_download(sonarr_download_id, block_torrent=False):
    # Set the query parameters for the DELETE request
    params = {
        'removeFromClient': True,
        'blocklist': block_torrent,  # Block the torrent if set to True
        'skipRedownload': True  # If True, skips re-downloading
    }
    
    # Send the DELETE request to remove the torrent
    delete_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue/{sonarr_download_id}'
    headers = {
        'X-Api-Key': sonarr_api_key,
        'Content-Type': 'application/json'
    }

    response = requests.delete(delete_url, headers=headers, params=params)
    
    if response.status_code == 200:
        print(f"Successfully removed download {sonarr_download_id} from Sonarr's queue.")
    else:
        # Print detailed error response for debugging
        print(f"Failed to remove download {sonarr_download_id}. Response: {response.status_code} - {response.text}")

qb = get_qbittorrent_login()
    
# Ensure 'downloads' is now a list of records
if isinstance(downloads, list):
    # Iterate through downloads and get torrent file details from Transmission
    for download in downloads:
        download_id = download['downloadId']  # This is the torrent hash
        series_title = download['title']
        
        # Fetch torrent file list from Transmission
        torrent_files = get_torrent_files(qb, download_id)
        
        if torrent_files:
            print(f"Checking torrent contents for: {series_title}")
            remove_torrent_flag = False  # Flag to indicate if the torrent should be marked for removal
        
            for file in torrent_files:
                filename = file['name']
                
                # Check if the file extension is .zipx or .lnk
                if filename.endswith('.zipx') or filename.endswith('.lnk'):
                    print(f"Identified suspicious file: {filename}. Marking download for removal...")
                    remove_torrent_flag = True
                    break  # Exit the loop since we found a file to trigger removal
                
                if remove_torrent_flag:
                    break
                    
                        # If a suspicious file was found, remove the torrent from Sonarr and block it
            if remove_torrent_flag:
                remove_and_block_download(download['id'], block_torrent=True)
        
        else:
            print(f"Failed to fetch torrent info for {series_title}")
else:
    print("Unexpected data structure from Sonarr API. Expected a list.")
