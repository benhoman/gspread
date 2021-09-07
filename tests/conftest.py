import itertools
import os
import vcr
import unittest
import pytest
import pathlib

from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

import gspread
from gspread.exceptions import APIError
from gspread import worksheet, Spreadsheet, Client

CREDS_FILENAME = os.getenv("GS_CREDS_FILENAME")

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive.file",
]
DUMMY_ACCESS_TOKEN = "<ACCESS_TOKEN>"

I18N_STR = "Iñtërnâtiônàlizætiøn"  # .encode('utf8')

def read_credentials(filename):
    return ServiceAccountCredentials.from_service_account_file(filename, scopes=SCOPE)


def prefixed_counter(prefix, start=1):
    c = itertools.count(start)
    for value in c:
        yield "{} {}".format(prefix, value)


def get_method_name(self_id):
    return self_id.split(".")[-1]


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "match_on": ["uri", "method"],  # match each query using the uri and the method
        "decode_compressed_response": True,  # decode requests to save clear content
        "serializer": "json",
        "path_transformer": vcr.VCR.ensure_suffix(".json"),
        "ignore_hosts": [
            "oauth2.googleapis.com",  # skip oauth requests, in replay mode we don't use them
        ],
        "filter_headers": [
            ("authorization", DUMMY_ACCESS_TOKEN)
        ],  # hide token from the recording
    }


class SleepyClient(gspread.Client):
    HTTP_TOO_MANY_REQUESTS = 429
    DEFAULT_SLEEP_SECONDS = 1

    def request(self, *args, **kwargs):
        try:
            return super().request(*args, **kwargs)
        except APIError as err:
            data = err.response.json()

            if data["error"]["code"] == self.HTTP_TOO_MANY_REQUESTS:
                import time

                time.sleep(self.DEFAULT_SLEEP_SECONDS)
                return self.request(*args, **kwargs)
            else:
                raise err


class DummyCredentials(UserCredentials):
    pass


class GspreadTest(unittest.TestCase):
    @classmethod
    def get_temporary_spreadsheet_title(cls):
        return "Test %s" % cls.__name__

    def _sequence_generator(self):
        return prefixed_counter(get_method_name(self.id()))


@pytest.fixture(scope="module")
def client():
    if CREDS_FILENAME:
        auth_credentials = read_credentials(CREDS_FILENAME)
    else:
        auth_credentials = DummyCredentials(DUMMY_ACCESS_TOKEN)

    gc = SleepyClient(auth_credentials)
    assert isinstance(gc, gspread.client.Client) is True

    return gc
