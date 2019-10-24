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


def get_user_projects(api: str):
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
    url = f"{api}/trackers/{tracker_id}/artifacts"
    return requests.get(url=url, params={
        **API_PARAMS,
        **{
            'offset': 1
        }
    }, verify=False).json() or False


def get_tuleap_artifacts(api: str, tracker_id: str) -> list:
    """
    Requests a route of the API of tuleap and return the results as a
    python object. If the requests is splitted into several pages, makes
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
    :param project_id: (int) id of the project to analyze\n
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


def get_columns_stats(artifacts):
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

    return stats


def ask_user(items: [], item_name):
    if len(items) == 0:
        print(f"Aucun {item_name} n'est disponible")
        sys.exit(0)

    if len(items) == 1:
        print(f"Le seul {item_name} disponible est le tracker "
              f"'{items[0]['label']}'")
        return items[0]

    print(f"Les {item_name}s disponibles sont : ")

    for i, item in enumerate(items, start=1):
        print(f" - {i} : {item['label']}")

    while True:
        number_choosen = input(
            f"Entrez un nombre entre 1 et {len(items)} : ")
        if re.match('^\d*$', number_choosen):
            if 1 <= int(number_choosen) <= len(items):
                selected_item = items[int(number_choosen) - 1]
                print(f"Vous avez sélectionné le {item_name} "
                      f"'{selected_item['label']}'")
                return selected_item

        print("La saisie est incorrecte")

def choose_file_format():
    avaliable_formats = [{
            'label': "CSV",
            'ext': "csv"
        },  {
            'label': "JSON",
            'ext': "json"
        },  {
            'label': "Excel",
            'ext': "xlsx"
        }]
    print("Choisissez le format de fichier : ")
    i = 0
    for format in avaliable_formats:
        i+=1
        print(str(i) + ": " + format["label"])

    while True:
        number_choosen = input(
            f"Entrez un nombre entre 1 et {len(avaliable_formats)} : ")
        if re.match('^\d*$', number_choosen):
            if 1 <= int(number_choosen) <= len(avaliable_formats):
                selected_format = avaliable_formats[int(number_choosen) - 1]
                print("Vous avez sélectionnez le format" + selected_format["label"])
                return selected_format

        print("La saisie est incorrecte")









if __name__ == '__main__':
    projects = get_user_projects(API_URL)
    project_uri = ask_user(projects, 'projet')['uri']

    trackers = get_project_trackers(API_URL, project_uri)
    selected_tracker = ask_user(trackers, 'tracker')

    if not check_artifact_existence(API_URL, selected_tracker["id"]):
        print("Aucune tâche n'a été trouvée")
        sys.exit()

    stats = pd.DataFrame()

    file_input = input("Choisissez un nom de fichier : ").split('.')[0]
    selected_format = choose_file_format()
    file_name = file_input + "." + selected_format["ext"]
    print("Les stats seront enregistrées ici : " + file_name)
    print("Analyse en cours...")

    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')

    df1 = get_columns_stats(
        get_tuleap_artifacts(API_URL, selected_tracker["id"])
    )
    df1[OLDEST_DURATION] = df1[OLDEST_DURATION].map(
        lambda t: datetime.replace(t, tzinfo=None)
    )
    df1.to_excel(writer, sheet_name=selected_tracker["label"])
    writer.sheets[selected_tracker["label"]].set_column('A:D', 18)
    writer.sheets[selected_tracker["label"]].set_column('D:D', 20)
    writer.sheets[selected_tracker["label"]].set_column('E:E', 30)

    print("Les résultats sont disponibles")

    writer.save()

    pd.Panel()
