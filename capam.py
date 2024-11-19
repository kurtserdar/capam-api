###########################################################################
#                                                                         #
#   CyberArk API Automation Script                                        #
#                                                                         #
#   Author: Serdar Kurt                                                   #
#   Created: 2024                                                         #
#                                                                         #
#   Description:                                                          #
#   This script interacts with CyberArk's REST API to automate various    #
#   tasks, including:                                                     #
#     - Authenticating to the CyberArk system                             #
#     - Retrieving passwords securely                                     #
#     - Managing safes and accounts                                       #
#     - Fetching unused accounts and generating reports                   #
#                                                                         #
#   Note: Ensure proper configuration in the `config.ini` file.           #
#                                                                         #
###########################################################################
import configparser
import requests
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import openpyxl

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CyberArk:
    def __init__(self):
        self.config = self.load_config()
        self.token = None

    def load_config(self):
        """
        Loads the configuration file from the current file structure.

        Returns:
            configparser.ConfigParser: Loaded configuration object.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "config.ini")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        config = configparser.ConfigParser(inline_comment_prefixes="#")
        config.read(config_path)
        logging.info(f"The configuration file has been loaded: {config_path}")
        return config

    def api_request(self, method, url, headers=None, data=None, params=None):
        """
        Handles API requests and provides error management.

        Args:
            method (str): HTTP method (GET, POST, etc.).
            url (str): API endpoint URL.
            headers (dict): HTTP request headers.
            data (str): Request payload.
            params (dict): Query parameters.

        Returns:
            dict: JSON response, or None if an error occurs.
        """
        verify_ssl = self.config.getboolean('CyberArk', 'verify_ssl', fallback=True)

        try:
            response = requests.request(method, url, headers=headers, data=data, params=params, verify=verify_ssl)
            response.raise_for_status()

            logging.info(f"Raw Response: {response.text}")

            try:
                return response.json()
            except ValueError:
                logging.error(f"Response is not in JSON format: {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed: {e}")
            return None

    def get_password(self, base_url, app_id, safe, object_name):
        """
        Retrieves a password from CyberArk CCP API.
        """
        url = f"{base_url}"
        params = {"AppID": app_id, "Safe": safe, "Object": object_name}
        response = self.api_request("GET", url, params=params)
        if response:
            return response.get('Content')
        return None

    def authenticate(self):
        """
        Authenticates to CyberArk and retrieves a token.
        """
        base_url = self.config['CyberArk']['base_url']
        auth_path = self.config['CyberArk']['auth_path']
        username = self.config['CyberArk']['username']

        ccp_base_url = self.config['CyberArk_CCP']['ccp_base_url']
        ccp_app_id = self.config['CyberArk_CCP']['ccp_appid']
        ccp_safe = self.config['CyberArk_CCP']['ccp_safe']
        ccp_object = self.config['CyberArk_CCP']['ccp_object']

        password = self.get_password(ccp_base_url, ccp_app_id, ccp_safe, ccp_object)

        if not password:
            logging.error("Failed to retrieve the password from CCP.")
            return None

        url = f"{base_url}{auth_path}"
        headers = {'Content-Type': 'application/json'}
        data = json.dumps({"username": username, "password": password, "concurrentSession": True})

        response = self.api_request("POST", url, headers=headers, data=data)
        if response:
            self.token = response.strip('"')  # Store token in the instance
            return self.token
        logging.error("Authentication failed.")
        return None

    def create_safe(self, safe_name, description, managing_cpm):
        """
        Creates a new safe in CyberArk.
        """
        base_url = self.config['CyberArk']['base_url']
        url = f"{base_url}/PasswordVault/API/Safes"
        headers = {
            'Authorization': self.token,
            'Content-Type': 'application/json'
        }
        data = json.dumps({
            "safeName": safe_name,
            "description": description,
            "managingCPM": managing_cpm
        })

        response = self.api_request("POST", url, headers=headers, data=data)
        if response:
            logging.info(f"Safe '{safe_name}' created successfully.")
            return True
        else:
            logging.error(f"Failed to create safe '{safe_name}'.")
            return False

    def add_account(self, safe_name, platform_id, address, username, password):
        """
        Adds a new account to a safe.
        """
        base_url = self.config['CyberArk']['base_url']
        url = f"{base_url}/PasswordVault/API/Accounts"
        headers = {
            'Authorization': self.token,
            'Content-Type': 'application/json'
        }
        data = json.dumps({
            "safeName": safe_name,
            "platformId": platform_id,
            "address": address,
            "userName": username,
            "secretType": "password",
            "secret": password
        })

        response = self.api_request("POST", url, headers=headers, data=data)
        if response:
            logging.info(f"Account '{username}' added successfully to safe '{safe_name}'.")
            return True
        else:
            logging.error(f"Failed to add account '{username}' to safe '{safe_name}'.")
            return False

    def get_recordings(self, limit, frm_time, to_time):
        """
        Fetches recordings from CyberArk API within the specified time range.
        """
        base_url = self.config['CyberArk']['base_url']
        api_path = self.config['CyberArk']['api_path']
        offset = 0
        all_recordings = []

        headers = {'Content-Type': 'application/json', 'Authorization': self.token}

        while True:
            try:
                recordings_url = f"{base_url}{api_path}?recordings&offset={offset}&Limit={limit}&FromTime={frm_time}&ToTime={to_time}"
                logging.info(f"Fetching recordings with offset: {offset}")

                response = requests.get(recordings_url, headers=headers)
                response.raise_for_status()

                recordings = json.loads(response.content).get("Recordings", [])
                logging.info(f"Fetched {len(recordings)} recordings at offset: {offset}")

                all_recordings.extend(recordings)

                if not recordings:
                    break

                offset += len(recordings)

            except requests.exceptions.RequestException as err:
                logging.error(f"Error fetching recordings at offset {offset}: {err}")
                break
            except json.JSONDecodeError as json_err:
                logging.error(f"Error decoding JSON response: {json_err}")
                break

        logging.info(f"Total recordings fetched: {len(all_recordings)}")
        return all_recordings

    def get_unused_accounts(self, days, safe_name=None):
        """
        Fetches a list of accounts that have not been used for the specified number of days,
        optionally filtered by a specific safe.

        Args:
            days (int): Number of days to check for unused accounts.
            safe_name (str): (Optional) Name of the safe to filter accounts.

        Returns:
            list: List of unused accounts.
        """
        base_url = self.config['CyberArk']['base_url']
        accounts_path = self.config['CyberArk']['accounts_path']
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self.token
        }

        try:
            offset = 0
            limit = 1000

            logging.info(f"Fetching account list for safe: {safe_name if safe_name else 'All Safes'}")

            account_ids = []
            account_details = {}  # Dictionary to map AccountID to AccountName and SafeName

            while True:
                # Construct URL based on whether safe_name is provided
                if safe_name:
                    accounts_url = f"{base_url}{accounts_path}?offset={offset}&limit={limit}&filter=safeName eq {safe_name}"
                else:
                    accounts_url = f"{base_url}{accounts_path}?offset={offset}&limit={limit}"

                logging.debug(f"Requesting URL: {accounts_url}")

                # Make API request
                response = requests.get(accounts_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                datav = data['value']

                # Append account IDs and details
                for account in datav:
                    account_id = account['id']
                    account_ids.append(account_id)
                    account_details[account_id] = {
                        'AccountName': account.get('name', 'Unknown'),
                        'SafeName': account.get('safeName', 'Unknown')
                    }

                # Check if there are more pages
                if "nextLink" in data:
                    offset += limit
                else:
                    break

            logging.info(f"Fetched {len(account_ids)} accounts for analysis.")

            # Check account activities
            unused_accounts = []

            threshold_date = (datetime.now(ZoneInfo("Europe/Istanbul")) - timedelta(days=days))

            for account_id in account_ids:
                activity_url = f"{base_url}/PasswordVault/WebServices/PIMServices.svc/Accounts/{account_id}/Activities/"
                try:
                    activity_response = requests.get(activity_url, headers=headers)
                    activity_response.raise_for_status()
                    activities = activity_response.json()
                    activities = activities['GetAccountActivitiesSlashResult']

                    if isinstance(activities, list) and len(activities) > 0:
                        # Parse the last activity date in Istanbul timezone
                        last_activity_date = max(
                            datetime.strptime(activity['Time'], "%m/%d/%Y %H:%M:%S").replace(
                                tzinfo=ZoneInfo("Europe/Istanbul"))
                            for activity in activities
                            if 'Time' in activity
                        )
                        # Compare with threshold date
                        if last_activity_date < threshold_date:
                            unused_accounts.append({
                                'AccountID': account_id,
                                'AccountName': account_details[account_id]['AccountName'],
                                'SafeName': account_details[account_id]['SafeName'],
                                'LastActivityDate': last_activity_date.strftime("%Y-%m-%d %H:%M:%S")
                            })
                    else:
                        logging.warning(f"No valid activities found for AccountID {account_id}")
                        unused_accounts.append({
                            'AccountID': account_id,
                            'AccountName': account_details[account_id]['AccountName'],
                            'SafeName': account_details[account_id]['SafeName'],
                            'LastActivityDate': "No Activity"
                        })

                except requests.exceptions.RequestException as activity_err:
                    logging.error(f"Failed to fetch activities for AccountID {account_id}: {activity_err}")
                except Exception as e:
                    logging.error(f"An error occurred: {e}")

            logging.info(f"Found {len(unused_accounts)} unused accounts.")
            # Save the results to CSV and Excel
            df = pd.DataFrame(unused_accounts)
            df.to_csv("unused_accounts.csv", index=False)
            df.to_excel("unused_accounts.xlsx", index=False)
            return unused_accounts

        except requests.exceptions.RequestException as err:
            logging.error(f"API request failed: {err}")
            return []


    def destroy_token(self):
        """
        Destroys the authentication token.
        """
        base_url = self.config['CyberArk']['base_url']
        url = f"{base_url}/PasswordVault/API/Auth/Logoff"
        headers = {'Authorization': self.token}

        response = self.api_request("POST", url, headers=headers)
        if response:
            logging.info("Token successfully destroyed.")
            self.token = None
            return True
        logging.error("Failed to destroy the token.")
        return False


if __name__ == "__main__":
    cyberark = CyberArk()

    try:
        logging.info("Starting CyberArk operations.")
        token = cyberark.authenticate()
        if token:
            logging.info("Authenticated with token.")


        else:
            logging.error("Failed to authenticate.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
