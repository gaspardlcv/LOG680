#!/usr/bin/env python3
# coding: utf8

import pandas as pd
from datetime import datetime, timezone

import requests


def get_tuleap_results(url):
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


if __name__ == '__main__':

    api_url = "https://tuleap.net/api/trackers/149/artifacts"
    artifacts = get_tuleap_results(api_url)

    current_date = datetime.now(timezone.utc)

    column = 'column'
    items_number = 'items_number'
    total_duration = 'total_duration'
    oldest = 'oldest'

    columns = {}

    stats = pd.DataFrame(
        columns=[column, items_number, total_duration, oldest],
    ).set_index(column)

    for artifact in artifacts:
        submitted_date_str = artifact['submitted_on'][:-3] + "00"
        submitted_date = datetime.strptime(
            submitted_date_str, '%Y-%m-%dT%H:%M:%S%z')
        duration = (current_date - submitted_date).total_seconds()

        columnName = artifact['status']

        if columnName not in stats.index:
            stats = stats.append(
                pd.DataFrame(
                    [[columnName, 1, duration, submitted_date]],
                    columns=[
                        column, items_number, total_duration, oldest
                    ],
                ).set_index(column)
            )
        else:
            stats.loc[columnName, items_number] += 1
            stats.loc[columnName, total_duration] += duration
            stats.loc[columnName, oldest] = \
                min(submitted_date, stats.loc[columnName, oldest])

        if columnName not in columns:
            columns[columnName] = {
                'items_number': 1,
                'total_duration': duration,
                'oldest': submitted_date
            }
        else:
            columns[columnName]['items_number'] += 1
            columns[columnName]['total_duration'] += duration
            if columns[columnName]['oldest'] > submitted_date:
                columns[columnName]['oldest'] = submitted_date

    print(stats)
