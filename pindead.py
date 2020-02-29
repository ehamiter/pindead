#!/usr/bin/env python

import concurrent.futures
import os
import re
import time
import urllib.error as urllib_error
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from collections import defaultdict, namedtuple
from textwrap import dedent


PINBOARD_EMAIL = os.environ.get("PINBOARD_EMAIL")
PINBOARD_TOKEN = os.environ.get("PINBOARD_TOKEN")

if not (PINBOARD_EMAIL and PINBOARD_TOKEN):
    warning_message = f"""\
        Set these two values in your environment:

        export PINBOARD_EMAIL="yourusername@maildomain.com"
        export PINBOARD_TOKEN="username:XXXXXXXXXXXXXXXXXXX"

        To find out what your Pinboard API token is, go here:
        https://pinboard.in/settings/password
    """
    print(dedent(warning_message))
    exit()


class Colors:
    HEADER = "\033[95m"
    INFO = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"


def check_url(post_url):
    global dead_url_list
    global dead_url_info
    global dead_url_count
    req = urllib_request.Request(post_url, headers=headers)
    try:
        response = urllib_request.urlopen(req)
    except urllib_error.HTTPError as e:
        code = e.code
    else:
        code = response.getcode()

    status = f"{color_codes[code]}{post_url} ({code}){Colors.END}"
    if code != 200:
        dead_url = DeadURL(post_url, code)
        dead_url_list.append(dead_url)
        dead_url_info += f"{status}\n"
        dead_url_count += 1
    print(status)


def delete_url(post_to_delete):
    code = post_to_delete.code
    url = post_to_delete.url

    # We need to parse the URL so Pinboard can delete it via its API
    parsed_url = urllib_parse.quote(url)
    pbd_url = (
        f"{api_base_url}/posts/delete?url={parsed_url}&auth_token={PINBOARD_TOKEN}"
    )
    req = urllib_request.Request(pbd_url, headers=headers)
    try:
        urllib_request.urlopen(req)
        print(f"Deleted {color_codes[code]}{url} ({code}){Colors.END}")
    except urllib_error.HTTPError as e:
        print(
            f"Error deleting {color_codes[code]}{url}{Colors.END}: ({Colors.WARNING}{e.reason}{Colors.END}).\n"
        )
        exit()


print(f"\n{Colors.HEADER}Initiating link checker...{Colors.END}\n")
t1 = time.perf_counter()
api_base_url = "https://api.pinboard.in/v1"
pb_url = f"{api_base_url}/posts/all&auth_token={PINBOARD_TOKEN}"
headers = {"User-Agent": "Pinboard Dead Link Checker 1.0", "From": PINBOARD_EMAIL}

req = urllib_request.Request(pb_url, headers=headers)
try:
    with urllib_request.urlopen(req) as response:
        content = response.read()
except urllib_error.HTTPError as e:
    error_message = f"""\
        Looks like there's a problem ({Colors.WARNING}{e.reason}{Colors.END}).\n
        Did you set your token correctly?
        ({Colors.INFO}export PINBOARD_TOKEN="user:XXXXXXXXXXXXXXXXXXXX"{Colors.END})\n
        It is currently set as {Colors.INFO}{os.environ.get("PINBOARD_TOKEN")}{Colors.END}
        You can verify it is set by running {Colors.INFO}echo $PINBOARD_TOKEN{Colors.END}
        """
    print(dedent(error_message))
    exit()

decoded_posts = content.decode("utf-8")
decoded_urls = re.findall(r'(https?://[^\s]+)"', decoded_posts)
urls_to_check = [s.replace("&amp;", "&") for s in decoded_urls]

color_codes = defaultdict(lambda: Colors.WARNING)
color_codes[200] = Colors.SUCCESS
color_codes[404] = Colors.FAIL

DeadURL = namedtuple("DeadURL", "url, code")
dead_url_list = []
dead_url_info = ""
dead_url_count = 0

with concurrent.futures.ThreadPoolExecutor() as executor:
    executor.map(check_url, urls_to_check)

t2 = time.perf_counter()
print(f"\nProcessed {len(urls_to_check)} links in {t2 - t1:.2f} seconds.\n")
dead_links_results = "No dead links!"
if dead_url_count:
    dead_links_results = f"Dead links: {dead_url_count}\n\n"
    dead_links_results += dead_url_info

results = f"""\
Results:
========
{dead_links_results}
"""

print(results)

if dead_url_count:
    link_or_links = "link" if dead_url_count == 1 else "links"
    delete_prompt = f"{Colors.INFO}Would you like to delete the dead {link_or_links} listed above? [Y]es, [N]o:{Colors.END} "
    delete_dead_links = str(input(delete_prompt)).strip().lower()

    if delete_dead_links == "y":
        print(
            f"\n{Colors.HEADER}Deleting {len(dead_url_list)} dead {link_or_links}...{Colors.END}\n"
        )
        t1 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(delete_url, dead_url_list)
        t2 = time.perf_counter()
        print(
            f"\nDeleted {len(dead_url_list)} {link_or_links} in {t2 - t1:.2f} seconds.\n"
        )
    else:
        print(
            f"\n{Colors.HEADER}Not deleting {link_or_links}, exiting program.{Colors.END}\n"
        )
