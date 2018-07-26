# -*- coding: utf-8 -*-

import csv
import urllib
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

class PagePaths(object):
    """Class responsible for managing connection to the Google Analytics and
    fetching page paths and connections between them.

    Args:
        view_id(string): ID of the GA view.
        key_file_location(string): path to the client credentials JSON file.
        start_date(string, optional): start date used in report, defaults to 'yesterday'.
    """

    scopes = ['https://www.googleapis.com/auth/analytics.readonly']
    view_id = ''
    start_date = ''

    def __init__(self, view_id, key_file_location, start_date='yesterday'):
        self.view_id = view_id
        self.start_date = start_date

        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            key_file_location, self.scopes)

        self.analytics = build('analyticsreporting', 'v4', credentials=credentials)

    def filter_batch(self, response, paths=[], connections=[]):
        """Parses and filters the Analytics Reporting API V4 response.

        Args:
            response(dict): an Analytics Reporting API V4 response.
        Returns:
            list: provided paths list plus new page paths from the current batch.
            list: provided connections list plus new connections.
        """
        for report in response.get('reports', []):
            for row in report.get('data', {}).get('rows', []):
                metrics = row.get('metrics', [])
                dimensions = row.get('dimensions', [])
                if len(dimensions) < 3:
                    continue

                prev = self.filter_path(dimensions[1])
                current = self.filter_path(dimensions[2])
                if prev is None or current is None or prev == current:
                    continue

                if prev in paths:
                    prev_index = paths.index(prev)
                else:
                    paths.append(prev)
                    prev_index = len(paths) - 1

                if current in paths:
                    current_index = paths.index(current)
                else:
                    paths.append(current)
                    current_index = len(paths) - 1

                connections.append([prev_index, current_index, int(metrics[0]['values'][0])])

        return paths, connections

    def filter_path(self, path):
        """Removes GET parameters from path.

        Args:
            path(string)

        Returns:
            string|None: filtered path or None if invalid.
        """

        if path.startswith('/http') or path.startswith('http'):
            return None

        query_start_index = path.find('?')
        if query_start_index != -1:
            path = path[:query_start_index]

        if not path.startswith('/'):
            path = path + '/'
        if not path.endswith('/'):
            path += '/'

        return path

    def get_batch(self, from_index=0):
        """Queries the Analytics Reporting API V4.

        Args:
            from_index(int, optional): offset for current batch, defaults to 0.
        Returns:
            dict: the Analytics Reporting API V4 response.
        """
        return self.analytics.reports().batchGet(
            body = {
                'reportRequests': [{
                    'viewId': self.view_id,
                    'pageToken': str(from_index),
                    'pageSize': 1000,
                    "filtersExpression": "ga:previousPagePath!=(entrance)",
                    'dateRanges': [{'startDate': self.start_date, 'endDate': 'today'}],
                    'metrics': [{'expression': 'ga:pageviews'}],
                    'dimensions': [{'name': 'ga:date'}, {'name': 'ga:previousPagePath'}, {'name': 'ga:pagePath'}]
                }]
            }
        ).execute()

    def get(self):
        """Queries, filters and parses page paths obtained from Google Analytics.

        Returns:
            list: unique page paths.
            list: previous and next page indices with counts.
        """
        paths = []
        connections = []

        more_pages = True
        from_index = 0
        while more_pages:
            response = self.get_batch(from_index)
            reports = response.get('reports', [])
            if len(reports) and 'nextPageToken' in reports[0]:
                more_pages = True
                from_index = reports[0]['nextPageToken']
            else:
                more_pages = False

            paths, connections = self.filter_batch(response, paths, connections)

        return paths, connections

    def show(self, response):
        """Parses and prints the Analytics Reporting API V4 response.

        Args:
            response(dict): an Analytics Reporting API V4 response.
        """
        for report in response.get('reports', []):
            column_header = report.get('columnHeader', {})
            dimension_headers = column_header.get('dimensions', [])
            metric_headers = column_header.get('metricHeader', {}).get('metricHeaderEntries', [])

            row_count = 0
            for row in report.get('data', {}).get('rows', []):
                metrics = row.get('metrics', [])
                dimensions = row.get('dimensions', [])

                print(str(row_count) + '. ')
                for header, dimension in zip(dimension_headers, dimensions):
                    print(header + ': ' + dimension)

                for i, values in enumerate(metrics):
                    for metric_header, value in zip(metric_headers, values.get('values')):
                        print(metric_header.get('name') + '=' + value)
                row_count += 1

    def write(self, data, file_name):
        """Writes given data to file_name.csv

        Args:
            data(iterable)
            file_name(string)
        """
        if not file_name.endswith('.csv'):
            file_name += '.csv'

        with open(file_name, 'w') as file:
            writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for row in data:
                writer.writerow(row if isinstance(row, list) else [row])

    def read(self, file_name, is_flat=False):
        """Reads data from file_name.csv.

        Args:
            file_name(string)
            is_flat(bool): should the reader expect flat, 1D data in file.
        Returns:
            list
        """
        if not file_name.endswith('.csv'):
            file_name += '.csv'

        data = []
        with open(file_name) as file:
            reader = csv.reader(file, delimiter=',', quotechar='"')
            if is_flat:
                for row in reader:
                    data.append(self._maybe_to_number(row[0]))
            else:
                for row in reader:
                    data.append([self._maybe_to_number(el) for el in row])
        return data

    def _maybe_to_number(self, x):
        return (float(x) if '.' in x else int(x)) if x.isdigit() else x
