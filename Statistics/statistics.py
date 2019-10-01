#!/usr/bin/env python3
# coding: utf8
from datetime import datetime, timezone

import requests

url = "https://tuleap.net/api/trackers/149/artifacts"

artifacts = requests.get(url=url).json()

columns = {}
current_date = datetime.now(timezone.utc)

for artifact in artifacts:
    submitted_date_str = artifact['submitted_on'][:-3] + "00"
    submitted_date = datetime.strptime(
        submitted_date_str, '%Y-%m-%dT%H:%M:%S%z')
    duration = current_date - submitted_date

    columnName = artifact['status']
    if columnName not in columns:
        columns[columnName] = {
            'items_number': 1,
            'total_duration': duration,
        }
    else:
        columns[columnName]['items_number'] += 1
        columns[columnName]['total_duration'] += duration

for column in columns:
    mean_duration = columns[column]['total_duration'] \
                    / columns[column]['items_number']
    print(column, mean_duration, sep=': ')


