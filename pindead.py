#!/usr/bin/env python

import concurrent.futures
import os
import re
import sys
import time
import urllib.error as urllib_error
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from collections import defaultdict, namedtuple
from textwrap import dedent


class Colors:
    HEADER = "\033[95m"
    INFO = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"


class Pindead:
    def __init__(self):
        self.PINBOARD_EMAIL = os.environ.get("PINBOARD_EMAIL")
        self.PINBOARD_TOKEN = os.environ.get("PINBOARD_TOKEN")
        self.api_base_url = "https://api.pinboard.in/v1"
        self.color_codes = defaultdict(lambda: Colors.WARNING)
        self.color_codes[200] = Colors.SUCCESS
        self.color_codes[404] = Colors.FAIL
        self.DeadURL = namedtuple("DeadURL", "url, code, status")
        self.dead_url_list = []
        self.dead_url_info = ""
        self.dead_url_count = 0
        self.headers = {
            "User-Agent": "Pinboard Dead Link Checker 1.0",
            "From": self.PINBOARD_EMAIL,
        }

    WARNING_MESSAGE = """\
        Set these two values in your environment:

        export PINBOARD_EMAIL="yourusername@maildomain.com"
        export PINBOARD_TOKEN="username:XXXXXXXXXXXXXXXXXXX"

        To find out what your Pinboard API token is, go here:
        https://pinboard.in/settings/password
    """

    ERROR_MESSAGE = f"""\
        Looks like there's a problem. Did you set your token correctly?
        export PINBOARD_TOKEN="user:XXXXXXXXXXXXXXXXXXXX"

        It is currently set as {os.environ.get("PINBOARD_TOKEN")}

        You can verify it is set correctly by running:
        echo $PINBOARD_TOKEN
    """

    def check_for_token_and_email(self):
        if not (self.PINBOARD_EMAIL and self.PINBOARD_TOKEN):
            print(dedent(self.WARNING_MESSAGE))
            sys.exit()

    def add_dead_url(self, url, code, status):
        dead_url = self.DeadURL(url, code, status)
        self.dead_url_list.append(dead_url)
        self.dead_url_info += f"{status}\n"
        self.dead_url_count += 1

    def check_url(self, url):
        req = urllib_request.Request(url, headers=self.headers)
        try:
            response = urllib_request.urlopen(req, timeout=30)
        except urllib_error.HTTPError as e:
            code = e.code
        else:
            code = response.getcode()
        status = f"{self.color_codes[code]}{url} ({code}){Colors.END}"
        if code != 200:
            self.add_dead_url(url, code, status)
        print(status)

    def delete_url(self, post_to_delete):
        url = post_to_delete.url
        status = post_to_delete.status

        # We need to parse the URL so Pinboard can delete it via its API
        parsed_url = urllib_parse.quote(url)
        pbd_url = f"{self.api_base_url}/posts/delete?url={parsed_url}&auth_token={self.PINBOARD_TOKEN}"
        req = urllib_request.Request(pbd_url, headers=self.headers)
        try:
            urllib_request.urlopen(req, timeout=30)
            print(status)
        except urllib_error.HTTPError as e:
            print(
                f"Error deleting {status}: ({Colors.WARNING}{e.reason}{Colors.END}).\n"
            )
            sys.exit()

    def optionally_delete_dead_links(self):
        link_or_links = "link" if self.dead_url_count == 1 else "links"
        delete_prompt = f"{Colors.INFO}Would you like to delete the dead {link_or_links} listed above? [Y]es, [N]o:{Colors.END} "
        delete_dead_links = str(input(delete_prompt)).strip().lower()

        if delete_dead_links == "y":
            print(
                f"\n{Colors.HEADER}Deleting {len(self.dead_url_list)} dead {link_or_links}...{Colors.END}\n"
            )
            t1 = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_url = {
                    executor.submit(self.delete_url, url): url
                    for url in self.dead_url_list
                }
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        future.result()
                    except Exception as exc:
                        print(f"{url} generated an exception: {exc}")

            t2 = time.perf_counter()
            print(
                f"\nDeleted {len(self.dead_url_list)} {link_or_links} in {t2 - t1:.2f} seconds.\n"
            )
        else:
            print(
                f"\n{Colors.HEADER}Not deleting {link_or_links}, exiting program.{Colors.END}\n"
            )

    def main(self):
        self.check_for_token_and_email()

        print(f"\n{Colors.HEADER}Initiating link checker...{Colors.END}\n")
        t1 = time.perf_counter()
        pb_url = f"{self.api_base_url}/posts/all&auth_token={self.PINBOARD_TOKEN}"

        req = urllib_request.Request(pb_url, headers=self.headers)
        try:
            with urllib_request.urlopen(req, timeout=30) as response:
                content = response.read()
        except urllib_error.HTTPError:
            print(dedent(self.ERROR_MESSAGE))
            sys.exit()

        decoded_posts = content.decode("utf-8")
        decoded_urls = re.findall(r'(https?://[^\s]+)"', decoded_posts)
        urls_to_check = [s.replace("&amp;", "&") for s in decoded_urls]

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_url = {
                executor.submit(self.check_url, url): url for url in urls_to_check
            }
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    future.result()
                except Exception as exc:
                    # Something got borked, so tagging it as a general server error:
                    #     nodename nor servname provided, or not known
                    #     [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
                    #     Connection refused
                    code = 500
                    status = f"{self.color_codes[code]}{url} ({exc}){Colors.END}"
                    print(status)
                    self.add_dead_url(url, code, status)

        t2 = time.perf_counter()
        print(f"\nProcessed {len(urls_to_check)} links in {t2 - t1:.2f} seconds.\n")
        dead_links_results = "No dead links!"
        if self.dead_url_count:
            dead_links_results = f"Dead links: {self.dead_url_count}\n\n"
            dead_links_results += self.dead_url_info

        print(dead_links_results)

        if self.dead_url_count:
            self.optionally_delete_dead_links()


if __name__ == "__main__":
    Pindead().main()
