import os
import json
import logging
from xml.etree import ElementTree
import gzip

import toml
import requests

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


CONFIG_PATH = 'config.toml'
SCOPE = ['https://www.googleapis.com/auth/spreadsheets.readonly']
NATION_DUMP_URL = 'https://www.nationstates.net/archive/nations/{date}-nations-xml.gz'
NATION_DUMP_NAME = '{date}-nations-xml.gz'

logger = logging.getLogger(__name__)


def canonical_nation_name(nation_name: str) -> str:
    """Get canonical nation name (all lower case)

    Args:
        nation_name (str): Nation name

    Returns:
        str: Canonicalized name
    """

    return nation_name.lower()


def get_sheet_service(cred_path: str):
    """Perform authorization flow to get credential for spreadsheet access.

    Args:
        cred_path (str): Path to OAuth credential file

    Raises:
        ValueError: Failed to get credential for spreadsheet access

    Returns:
        Spreadsheet resource
    """

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPE)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPE)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    if not creds:
        raise ValueError

    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets().values()


def get_puppets_from_sheet(sheet_resource, spreadsheet_id: str, sheet_range: str) -> dict:
    """Get a dict of puppets and their owners from specified spreadsheet range.

    Args:
        sheet_resource: Spreadsheet resource
        spreadsheet_id (str): Spreadsheet Id
        range (str): Spreadsheet range
    Returns:
        dict: Puppets as keys and their owner
    """

    resp = sheet_resource.get(spreadsheetId=spreadsheet_id, range=sheet_range).execute()
    rows = resp.get('values', [])
    return {canonical_nation_name(row[0]): canonical_nation_name(row[1]) for row in rows}


def download_nation_dump(dump_date: str, dump_filename: str) -> None:
    """Download nation data dump of a specified date.

    Args:
        dump_date (str): Date in ISO format
        dump_filename (str): Filename to save as
    """

    url = NATION_DUMP_URL.format(date=dump_date)

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dump_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def download_nation_dump_if_not_exists(dump_date: str) -> str:
    """Download nation data dump if not exist and return dump filename.

    Args:
        dump_date (str): Date in ISO format

    Returns:
        str: Dump filename
    """

    dump_filename = NATION_DUMP_NAME.format(date=dump_date)
    if not os.path.exists(dump_date):
        download_nation_dump(dump_date, dump_filename)
    return dump_filename


def get_puppet_issue_counts(dump_file, puppets: dict) -> dict:
    """Get answered issue counts since founding  (ISSUE_ANSWERED tag)
    of puppets from nation data dump.

    Args:
        dump_file (file-like object): Dump file object
        puppets (dict): Puppets

    Returns:
        dict: Issue count keyed by puppet name
    """

    dump_file = gzip.open(dump_file)
    puppet_issue_counts = {}
    for event, elem in ElementTree.iterparse(dump_file):
        if event == 'end' and elem.tag == 'NATION':
            nation_name = canonical_nation_name(elem.find('NAME').text)
            if nation_name in puppets:
                issue_count = int(elem.find('ISSUES_ANSWERED').text)
                puppet_issue_counts[nation_name] = issue_count
    return puppet_issue_counts


def get_puppet_issue_counts_from_gzip(filename, puppets):
    dump_file = gzip.open(filename)
    return get_puppet_issue_counts(dump_file, puppets)


def get_leaderboard(puppets, start_date_issue_counts, end_date_issue_counts) -> dict:
    """Get issue leaderboard of owners.

    Args:
        puppets (dict): Puppets and their owners
        start_date_issue_counts (dict): Puppet issue counts on start date
        end_date_issue_counts (dict): Puppet issue counts on end date

    Returns:
        dict: Issue leaderboard
    """

    leaderboard = {}
    for puppet_name, owner_name in puppets.items():
        if owner_name not in leaderboard:
            leaderboard[owner_name] = 0

        if puppet_name not in end_date_issue_counts:
            continue
        end_date_count = end_date_issue_counts[puppet_name]

        if puppet_name not in start_date_issue_counts:
            leaderboard[owner_name] += end_date_count
        else:
            start_date_count = start_date_issue_counts[puppet_name]
            leaderboard[owner_name] += end_date_count - start_date_count

    return dict(sorted(leaderboard.items(), key=lambda item: item[1], reverse=True))


def export_to_json(issue_leaderboard: dict, file_path: str) -> None:
    with open(file_path, 'w') as file_obj:
        json.dump(issue_leaderboard, file_obj)


def main():
    try:
        config = toml.load(CONFIG_PATH)
    except FileNotFoundError:
        logger.error('Config file not found!')
        exit(-1)

    general_config = config['general']
    try:
        start_date_dump_name = download_nation_dump_if_not_exists(general_config['start_date'])
        end_date_dump_name = download_nation_dump_if_not_exists(general_config['end_date'])
    except requests.HTTPError as err:
        logger.error('Failed to download nation data dump. HTTP error: %s', err.response.status_code)
        exit(-1)

    sheet_config = config['puppet_spreadsheet']
    try:
        sheet_service = get_sheet_service(sheet_config['oauth_cred_path'])
    except ValueError:
        logger.error('Failed to get credential for Google spreadsheet.')
        exit(-1)

    puppets = get_puppets_from_sheet(sheet_service, sheet_config['spreadsheet_id'], sheet_config['range'])
    if not puppets:
        logger.warning('No puppets were found')
        exit(-1)

    start_date_issue_counts = get_puppet_issue_counts_from_gzip(start_date_dump_name, puppets)
    end_date_issue_counts = get_puppet_issue_counts_from_gzip(end_date_dump_name, puppets)

    leaderboard = get_leaderboard(puppets, start_date_issue_counts, end_date_issue_counts)

    export_to_json(leaderboard, config['export']['json_path'])

    if general_config.get('delete_dump_file_after_done', False):
        os.remove(start_date_dump_name)
        os.remove(end_date_dump_name)


if __name__ == '__main__':
    main()
