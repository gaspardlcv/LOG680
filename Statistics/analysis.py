#!/usr/bin/env python3
# coding: utf8

import re
import sys

import requests
import urllib3
import configparser
import pandas as pd
from datetime import datetime, timezone

# CONSTANTS
COLUMN = 'column'
ITEMS_NUMBER = 'items_number'
MEAN_DURATION = 'mean_duration'
OLDEST_DURATION = 'oldest_duration'
OLDEST_NAME = 'oldest_name'
AVAILABLE_FORMATS = [
    {
        'label': "CSV",
        'ext': "csv"
    }, {
        'label': "JSON",
        'ext': "json"
    }, {
        'label': "Excel",
        'ext': "xlsx"
    }
]

# import configuration from '.ini' file
config = configparser.ConfigParser()
config.read('.ini')
API_URL = config['TULEAP_API']['api_url']
ACCESS_KEY = config['TULEAP_API']['access_key']
API_PARAMS = {
    'X-Auth-AccessKey': ACCESS_KEY
}

# suppress the warning linked to the deactivation of ssl verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_user_projects(api: str) -> list:
    """
    Returns the list of visible projects for the user
    by requesting tuleap API\n
    :param api: (str) tuleap api to requests\n
    :return: (list) list of the projects
    """
    url = f"{api}/projects"
    raw_projects = requests.get(
        url, params=API_PARAMS, verify=False).json()

    return [
        {
            'label': project['label'],
            'uri': project['uri']
        } for project in raw_projects
    ]


def check_artifact_existence(api: str, tracker_id) -> bool:
    """
    Checks if a given tracker has some artifacts
    by requesting artifacts from the tuleap API and checking
    if the result of the request is empty or not\n
    :param api: (str) tuleap api to requests\n
    :param tracker_id: (str) id of the tracker to request\n
    :return: (bool): existence of artifacts for the tracker
    """
    url = f"{api}/trackers/{tracker_id}/artifacts"
    return requests.get(url=url, params={
        **API_PARAMS,
        **{
            'offset': 1
        }
    }, verify=False).json() or False


def get_tuleap_artifacts(api: str, tracker_id: str) -> list:
    """
    Requests artifacts from the tuleap API for given tracker.
    If the requests is splitted into several pages, makes
    several requests to get the whole dataset\n
    :param api: (str) tuleap api to requests\n
    :param tracker_id: (str) id of the tracker to request\n
    :return: results: (list) data requested
    """

    url = f"{api}/trackers/{tracker_id}/artifacts"
    offset, size, total_items = 0, 0, 0
    results = []

    while offset + size <= total_items:
        request = requests.get(url=url, params={
            **API_PARAMS,
            **{
                'offset': offset + size
            }
        }, verify=False)

        offset = int(request.headers['X-PAGINATION-OFFSET'])
        size = int(request.headers['X-PAGINATION-LIMIT'])
        total_items = int(request.headers['X-PAGINATION-SIZE'])

        results += request.json()

    return results


def get_human_duration(time: int) -> str:
    """
    Return a string corresponding to the approximated duration of time
    passed as parameter in a more readable format.
    It can give the number of years, months, days, hours or minutes.
    For instance, for 3700s, it will return '1 hour'\n
    :param time: (int) time in seconds\n
    :return: (str) duration time to be returned
    """

    readable_time = [
        ("year", 365.25 * 24 * 3600),
        ("month", 30.24 * 24 * 3600),
        ("day", 24 * 3600),
        ("hour", 60),
        ("minute", 60)
    ]

    human_time = ""

    for date_type, division in readable_time:
        reduce_time = time / division
        time -= division * int(reduce_time)
        time_to_display = int(reduce_time + .5)
        if time_to_display > 0:
            if time_to_display > 1:
                date_type += 's'
            human_time = f"{time_to_display} {date_type}"
            break

    return human_time


def get_project_trackers(api: str, project_uri: str) -> list:
    """
    Returns a list containing the id and labels of all trackers
    associated to a given project\n
    :param api: (str) tuleap api to requests\n
    :param project_uri: (int) id of the project to analyze\n
    :return: (list) list of tracker info
    """
    url = f"{api}/{project_uri}/trackers"

    results = requests.get(url, params=API_PARAMS, verify=False).json()
    return [
        {
            'id': result['id'],
            'label': result['label']
        } for result in results
    ]


def get_columns_stats(artifacts: list) -> pd.DataFrame:
    """
    Extracts statistics from a list of artifacts\n
    :param artifacts: (list) data to be analyzed\n
    :return: stats (pd.DataFrame): resulting statistics
    """
    current_date = datetime.now(timezone.utc)

    no_column_artifact_number = 0

    # dataframe that will contain results
    stats = pd.DataFrame(
        columns=[
            COLUMN,
            ITEMS_NUMBER,
            MEAN_DURATION,
            OLDEST_DURATION,
            OLDEST_NAME
        ]
    ).set_index(COLUMN)

    for artifact in artifacts:
        # we get the column and the submitted date of the artifact
        column_name = artifact['status']
        label = artifact['title']
        submitted_date_str = artifact['submitted_on'][:-3] + "00"

        if column_name == "":
            no_column_artifact_number += 1
            continue

        # the date is converted into python date
        submitted_date = datetime.strptime(
            submitted_date_str, '%Y-%m-%dT%H:%M:%S%z')
        duration = (current_date - submitted_date).total_seconds()

        if column_name not in stats.index:
            stats.loc[column_name] = [
                1, duration, submitted_date, label
            ]
        else:
            stats.loc[column_name, ITEMS_NUMBER] += 1
            stats.loc[column_name, MEAN_DURATION] += duration

            if submitted_date < stats.loc[column_name, OLDEST_DURATION]:
                stats.loc[column_name, OLDEST_DURATION] = submitted_date
                stats.loc[column_name, OLDEST_NAME] = label

    # calculates the mean duration time for each column
    stats[MEAN_DURATION] = stats.apply(
        lambda df: df[MEAN_DURATION] / df[ITEMS_NUMBER], axis=1
    )

    # duration time is converted in a more readable format
    stats[MEAN_DURATION] = stats[MEAN_DURATION].map(
        get_human_duration)

    stats[OLDEST_DURATION] = stats[OLDEST_DURATION].map(
        lambda t: datetime.replace(t, tzinfo=None)
    )

    return stats


def get_artifact_changesets(artifact: dict):
    permanent_youngest_date = None
    youngest_date = None

    url = f"{API_URL}/artifacts/{artifact['id']}/changesets"

    changesets = requests.get(url, params=API_PARAMS,
                              verify=False).json()

    status = []
    dates = []
    for changeset in changesets:
        submitted_on = datetime.strptime(
            changeset['submitted_on'][:-6],
            '%Y-%m-%dT%H:%M:%S'
        )
        values = changeset['values']

        # convert if needed values in a list
        if type(values) == dict:
            values = [v for v in values.values()]

        for value in values:
            if value['label'] == 'Status':
                for v in value['values']:
                    if v['label'] not in status:
                        status.append(v['label'])
                        dates.append(submitted_on)
                    if not youngest_date \
                            or youngest_date < submitted_on:
                        youngest_date = submitted_on

                    if v['label'] == 'Permanent':
                        # print(artifact['title'])
                        if not permanent_youngest_date or \
                                permanent_youngest_date < submitted_on:
                            permanent_youngest_date = submitted_on

    if 'Permanent' in status:
        print(artifact['title'], end=': ')
        for i in range(len(status)):
            print(status[i], ' -> ', dates[i], end=' ')

    if permanent_youngest_date and youngest_date \
            and permanent_youngest_date < youngest_date:
        print(f"{artifact['title']} ({artifact['id']})")


def ask_user(items: list, item_name) -> dict:
    """
    Generic function that asks user to select an item
    from a list of items by choosing a number.
    If no items are available, stops the execution.\n
    :param items: (list) list of available items.
        Each item must be a dict containing the key 'label'\n
    :param item_name: () name to be displayed for the user\n
    :return: (dict): item selected by the user
    """
    if len(items) == 0:
        print(f"Aucun {item_name} n'est disponible")
        sys.exit(0)

    if len(items) == 1:
        print(f"Le seul {item_name} disponible est le {item_name} "
              f"'{items[0]['label']}'")
        return items[0]

    print(f"Les {item_name}s disponibles sont : ")

    for i, item in enumerate(items, start=1):
        print(f" - {i} : {item['label']}")

    while True:
        number_choosen = input(
            f"Entrez un nombre entre 1 et {len(items)} : ")
        if re.match('^\d+$', number_choosen):
            if 1 <= int(number_choosen) <= len(items):
                selected_item = items[int(number_choosen) - 1]
                print(f"Vous avez sélectionné le {item_name} "
                      f"'{selected_item['label']}'")
                return selected_item

        print("La saisie est incorrecte")


def create_file(
        results: pd.DataFrame, output_name: str,
        output_format: str, tracker_name: str
) -> None:
    """
    Creates a file containing the results of the analysis\n
    :param results: (pd.DataFrame) raw results\n
    :param output_name: (str) name of the ouput file with no extension\n
    :param output_format: (str) format of the ouput file\n
    :param tracker_name: (str) name of the analyzed tracker\n
    :return: (None)
    """
    filename = f"{output_name}.{output_format}"
    print("Les stats seront enregistrées ici : " + filename)
    print("Analyse en cours...")

    if output_format == "xlsx":
        writer = pd.ExcelWriter(filename, engine='xlsxwriter')
        results.to_excel(writer, sheet_name=tracker_name)
        writer.sheets[tracker_name].set_column('A:D', 18)
        writer.sheets[tracker_name].set_column('D:D', 20)
        writer.sheets[tracker_name].set_column('E:E', 30)
        writer.save()
    elif output_format == "csv":
        results.to_csv(filename)
    elif output_format == "json":
        results.to_json(filename)


if __name__ == '__main__':
    projects = get_user_projects(API_URL)
    project_uri = ask_user(projects, 'projet')['uri']

    trackers = get_project_trackers(API_URL, project_uri)
    selected_tracker = ask_user(trackers, 'tracker')

    if not check_artifact_existence(API_URL, selected_tracker["id"]):
        print("Aucune tâche n'a été trouvée")
        sys.exit()

    filename = input("Choisissez un nom de fichier : ").split('.')[0]
    selected_format = ask_user(AVAILABLE_FORMATS, "format")['ext']

    stats = get_columns_stats(
        get_tuleap_artifacts(API_URL, selected_tracker["id"])
    )

    create_file(
        stats, filename, selected_format, selected_tracker['label']
    )
    print("Les résultats sont disponibles")
