import argparse
import asyncio
import os
import sys
from asyncio.subprocess import Process
from pathlib import Path
from typing import Optional
from urllib.parse import unquote
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientResponse
from bs4 import BeautifulSoup, Tag

parser = argparse.ArgumentParser()
parser.add_argument("--console", help="Console name from allowed console's list", required=True)
parser.add_argument("--name", help="Game name filter", nargs="*", required=False)
parser.add_argument("--exclude", help="Keywords to exclude", nargs="*", required=False)
parser.add_argument("--language", help="Language's keyword", nargs="*", required=False)
parser.add_argument("--path", help="Set a directory to save downloads", required=False, default=".")
parser.add_argument("--override", help="Skip current roms validation", required=False, default=False)
parser.add_argument("--check", help="Set a directory to check current roms", required=False, default=".")
args = parser.parse_args()

CONSOLE_SOURCE_MAP: dict[str, str] = {  # TODO: Update sources
    "psx": "https://myrient.erista.me/files/Internet%20Archive/chadmaster/chd_psx_eur/CHD-PSX-EUR/",
    "gamecube": "https://myrient.erista.me/files/Redump/Nintendo%20-%20GameCube%20-%20NKit%20RVZ%20[zstd-19-128k]/",
    "ps2": "https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation%202/",
    "saturn": "https://myrient.erista.me/files/Internet%20Archive/chadmaster/chd_saturn/CHD-Saturn/Europe/",
    "n64": "https://myrient.erista.me/files/No-Intro/Nintendo%20-%20Nintendo%2064%20(ByteSwapped)/",
    "psv": "https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation%20Portable/",
    "dreamcast": "https://myrient.erista.me/files/Internet%20Archive/chadmaster/dc-chd-zstd-redump/dc-chd-zstd/"
}

async def show_loader() -> None:
    chars: str = "/-\\|"
    i: int = 0
    while True:
        sys.stdout.write(f"\rDownloading... {chars[i % len(chars)]}")
        sys.stdout.flush()
        i += 1
        await asyncio.sleep(0.1)

def raise_for_path() -> None:
    if not os.path.exists(args.path) or not os.path.isdir(args.path):
        raise Exception("Invalid path")

def read_current_files() -> list[str]:
    folder: Path = Path(args.check)
    return [f.name for f in folder.iterdir() if f.is_file()]


async def download(urls: list[str]) -> None:
    loader_task = asyncio.create_task(show_loader())
    try:
        raise_for_path()
        cmd: list[str] = ["aria2c",
                          "-x", "4",
                          "-s", "4",
                          "-d", args.path if args.path else ".",
                          "--show-console-readout=true",
                          "--console-log-level=notice",
                          "-Z"] + urls

        process: Process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if stdout:
            print(stdout.decode().strip(), flush=True)

        if process.returncode == 0:
            print("Download successfully")
        else:
            print(f"Download fail: {stderr.decode().strip()}")
    except Exception as e:
        print(e.args)
    finally:
        loader_task.cancel()
        sys.stdout.write("\r" + " " * 30 + "\r")
        sys.stdout.flush()

def filter_roms(url: str, soup: BeautifulSoup) -> dict[str, str]:
    filter_results: dict[str, str] = {}
    for row in soup.find_all('tr'):
        link: Optional[Tag] = row.find('a')
        if link and link.get('href'):
            filename: str = link.get('href')
            unquoted_filename: str = unquote(filename)
            unquoted_filename_lower: str = unquoted_filename.lower()

            # Build filters
            has_language: bool = any(
                term in unquoted_filename for term in args.language) if args.language else True
            has_excluded: bool = any(
                term in unquoted_filename_lower for term in args.exclude) if args.exclude else False
            has_name: bool = " ".join([n.lower() for n in args.name]) in unquoted_filename_lower if args.name else True

            if has_language and has_name and not has_excluded:
                full_url: str = urljoin(url, filename)
                filter_results[unquoted_filename] = full_url
    return filter_results

async def main():
    if args.console:
        try:
            # Gets page's HTML
            url: str = CONSOLE_SOURCE_MAP[args.console]
            async with aiohttp.ClientSession() as session:
                response: ClientResponse = await session.get(url, headers={"User-Agent": "Mozilla/5.0"})
                soup: BeautifulSoup = BeautifulSoup(await response.text(), 'html.parser')

            # Find and filter urls
            scrapper_results: dict[str, str] = filter_roms(url, soup)
            current_roms: list[str] = read_current_files()

            if not args.override:
                scrapper_results = dict(filter(lambda item: item not in current_roms, scrapper_results.items()))

            roms_names: list[str] = list(scrapper_results.keys())
            if scrapper_results:
                print(f"Search results: \n")
                count: int = 0
                for rom in roms_names:
                    print(f"{count} - {rom}")

                download_choices: list[str] = input("Select roms to download typing index separated by space (0 1 2 3..). Empty to cancel: ").split(" ")

                selected_roms: dict[str, str] = {}
                for choice in download_choices:
                    selected_roms[roms_names[int(choice)]] = scrapper_results[roms_names[int(choice)]]

                download_confirm: bool = (input("\n Start download? N/y: ") == "y")
                if download_confirm:
                    await download(urls=list(scrapper_results.values()))  # Uses 'aria2c' to make all downloads
                else:
                    print("Download cancel")
        except KeyError:
            print(f"Invalid console name: {args.console}")
        except Exception as e:
            print(f"Unhandled error: {e}")
            raise e
        print("Script end")

def init():
    asyncio.run(main())