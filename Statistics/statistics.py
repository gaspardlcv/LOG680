#!/usr/bin/env python3
# coding: utf8

import json
import re

import requests
import urllib3
import configparser
import pandas as pd
from datetime import datetime, timezone

tracker = 'tracker'
column = 'column'
items_number = 'items_number'
total_duration = 'total_duration'
oldest = 'oldest'

# import configuration from '.ini' file
config = configparser.ConfigParser()
config.read('.ini')
api_url = config['TULEAP_API']['api_url']
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
        params = {
            'offset': offset + size
        }
        request = requests.get(url=url, params={
            **params,
            **API_PARAMS
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

    results = requests.get(url).json()
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
        columns=[column, items_number, total_duration, oldest]
    ).set_index(column)

    for artifact in artifacts:
        # we get the column and the submitted date of the artifact
        column_name = artifact['status']
        submitted_date_str = artifact['submitted_on'][:-3] + "00"

        if column_name == "":
            no_column_artifact_number += 1
            continue

        # the date is converted into python date
        submitted_date = datetime.strptime(
            submitted_date_str, '%Y-%m-%dT%H:%M:%S%z')
        duration = (current_date - submitted_date).total_seconds()

        if column_name not in stats.index:
            stats.loc[column_name] = [1, duration, submitted_date]
        else:
            stats.loc[column_name, items_number] += 1
            stats.loc[column_name, total_duration] += duration
            stats.loc[column_name, oldest] = \
                min(submitted_date, stats.loc[column_name, oldest])
    # calculates the mean duration time for each column
    stats[total_duration] = stats.apply(
        lambda df: df[total_duration] / df[items_number], axis=1
    )

    # duration time is converted in a more readable format
    stats[total_duration] = stats[total_duration].map(
        get_human_duration)

    return stats


def choose_project(projects: []):
    print("Les projets disponibles sont : ")

    for i, project in enumerate(projects, start=1):
        print(f" - {i} : {project['label']} ({project['uri']})")

    while True:
        number_choosen = input(
            f"Entrez un nombre entre 1 et {len(projects)} : ")
        if re.match('^\d*$', number_choosen):
            if 1 <= int(number_choosen) <= len(projects):
                selected_project = projects[int(number_choosen) - 1]
                print("Vous avez sélectionnez le projet " +
                      selected_project['label'])
                return selected_project['uri']

        print("La saisie est incorrecte")

def choose_tracker(api_url, project_uri):
    trackers = get_project_trackers(api_url, project_uri)
    print("Les trackers suivants sont disponibles :")
    i = 0
    for tracker in trackers:
        i += 1
        print(str(i) + " : " + tracker["label"])

    while True:
        number_choosen = input(
            f"Entrez un nombre entre 1 et {len(trackers)} : ")
        if re.match('^\d*$', number_choosen):
            if 1 <= int(number_choosen) <= len(trackers):
                selected_tracker = trackers[int(number_choosen) - 1]
                print("Vous avez sélectionnez le tracker " +
                      selected_tracker["label"])
                if get_tuleap_artifacts(api_url,selected_tracker["id"]) == []:
                    print("Le json du tracker est vide sélectionner un autre")
                else :
                    return selected_tracker

        print("La saisie est incorrecte")


if __name__ == '__main__':
    projects = get_user_projects(api_url)
    project_uri = choose_project(projects)
    tracker = choose_tracker(api_url,project_uri)

    stats = pd.DataFrame()

    file_input = input("Choisissez un nom de fichier : ").split('.')[0]
    file_name = file_input + '.xlsx'
    print("Les stats seront enregistrées ici : " + file_name)
    print("Analyse en cours...")

    writer = pd.ExcelWriter(file_name, engine='xlsxwriter')

    df1 = get_columns_stats(
        get_tuleap_artifacts(api_url,tracker["id"])
    )
    df1[oldest] = df1[oldest].map(
        lambda t: datetime.replace(t, tzinfo=None)
    )
    df1.to_excel(writer, sheet_name=tracker["label"])
    writer.sheets[tracker["label"]].set_column('A:E', 18)

    print("Les résultats sont disponibles")

    writer.save()

    pd.Panel()
