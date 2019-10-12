#!/usr/bin/env python3
# coding: utf8

import json
import re

import pandas as pd
from datetime import datetime, timezone

import requests

tracker = 'tracker'
column = 'column'
items_number = 'items_number'
total_duration = 'total_duration'
oldest = 'oldest'


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
        request = requests.get(url=url, params=params)

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


def get_project_trackers(api: str, project_id: int) -> list:
    """
    Returns a list containing the id and labels of all trackers
    associated to a given project\n
    :param api: (str) tuleap api to requests\n
    :param project_id: (int) id of the project to analyze\n
    :return: (list) list of tracker info
    """
    url = f"{api}/projects/{project_id}/trackers"

    return [
        f"{result['id']} {result['label']}"
        for result in requests.get(url).json()
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


if __name__ == '__main__':
    api_url = "https://tuleap.net/api"

    trackers = get_project_trackers(api_url, 101)
    stats = pd.DataFrame()

    writer = pd.ExcelWriter('stats.xlsx', engine='xlsxwriter')

    for tracker_name in trackers:
        df1 = get_columns_stats(
            get_tuleap_artifacts(api_url,
                                 re.sub('\D*', '', tracker_name))
        )
        df1[oldest] = df1[oldest].map(
            lambda t: datetime.replace(t, tzinfo=None)
        )
        df1.to_excel(writer, sheet_name=tracker_name)
        writer.sheets[tracker_name].set_column('A:E', 18)

    writer.save()

    results = pd.Panel()

    pd.Panel()
