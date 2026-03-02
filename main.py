"""
Roms download manager

This script find, filter and download multiple roms files in parallel using aria2c.
Allowed consoles:
    psx (PlayStation 1)
    ps2 (PlayStation 2)
    gamecube (Nintendo Game cube)
    n64 (Nintendo 64)
    saturn (Sega Saturn)


Author:
    Dido

Date:
    02/03/2026

Version:
    0.1.0

Usage:
    python3 main.py
        --console <console-name>
        --exclude <any keyword> like demo, beta, alpha, etc...
        --language <any keyword> like es, en, spain, fr, etc...
        --output ./games-roms
        --name <any keyword> any game title or search keyboard

Dependencies:
    - Python 3.8+
    - aria2c installed (sudo apt install aria2 or brew install aria2)
"""
import asyncio
import sys
from asyncio.subprocess import Process
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote
from urllib.parse import urljoin

import aiohttp
import inquirer
from aiohttp import ClientResponse
from bs4 import BeautifulSoup, Tag

CANCEL: str = "Cancel"
ALL: str = "All"
CONSOLES: list[str] = ["PlayStation 1", "PlayStation 2", "Nintendo GameCube", "Nintendo 64", "Sega Saturn"]
CONSOLE_SOURCE_MAP: dict[str, str] = {  # TODO: Update sources
    "PlayStation 1": "https://myrient.erista.me/files/Internet%20Archive/chadmaster/chd_psx_eur/CHD-PSX-EUR/",
    "Nintendo GameCube": "https://myrient.erista.me/files/Redump/Nintendo%20-%20GameCube%20-%20NKit%20RVZ%20[zstd-19-128k]/",
    "PlayStation 2": "https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation%202/",
    "Sega Saturn": "https://myrient.erista.me/files/Internet%20Archive/chadmaster/chd_saturn/CHD-Saturn/Europe/",
    "Nintendo 64": "https://myrient.erista.me/files/No-Intro/Nintendo%20-%20Nintendo%2064%20(ByteSwapped)/"
}

@dataclass
class Config:
    console: Optional[str]
    name: str
    exclude: list[str]
    language: Optional[list[str]]

def make_question(options: list[str], option_name: str):
    options.insert(0, CANCEL)
    if option_name != "CONSOLE":
        options.insert(1, ALL)

    questions = [
        inquirer.List(option_name,
                      message=f"Choose a {option_name}",
                      choices=options,
                      ),
    ]

    answers = inquirer.prompt(questions)
    if not answers or answers[option_name] == CANCEL:
        return None

    print(f"Selected {answers[option_name]}")
    return answers[option_name]

def request_config(exclude_console: bool = False) -> Optional[Config]:
    console: Optional[str] = make_question(CONSOLES, "CONSOLE") if not exclude_console else None
    name: str = input("Write keywords filter game name. Press enter to skip: ")
    exclude_raw: str = input("Write keywords to exclude. Press enter to skip: ")
    language_raw: str = input("Write language. Press enter to skip: ")

    language: Optional[list[str]] = language_raw.split(" ") if language_raw else None
    exclude: list[str] = ["../", "./", "..", "N&O", "="]
    if exclude_raw:
        exclude.extend(exclude_raw.split(" "))
    return Config(console, name, exclude, language)

async def show_loader() -> None:
    chars: str = "/-\\|"
    i: int = 0
    while True:
        sys.stdout.write(f"\rDownloading... {chars[i % len(chars)]}")
        sys.stdout.flush()
        i += 1
        await asyncio.sleep(0.1)

async def download(urls: list[str]) -> None:
    loader_task = asyncio.create_task(show_loader())
    try:
        cmd: list[str] = ["aria2c", "-x", "4", "-s", "4", "--summary-interval=2",
                          "--console-log-level=warn"] + urls

        process: Process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async for line in process.stdout:
            sys.stdout.write("\r" + " " * len(line.decode().strip()) + "\r")
            print(line.decode().strip(), flush=True)

        await process.wait()

        if process.returncode == 0:
            print("Download successfully")
        else:
            print(f"Download fail: {process.stderr}")
    finally:
        loader_task.cancel()
        sys.stdout.write("\r" + " " * 30 + "\r")
        sys.stdout.flush()


def filter_roms(config: Config, url: str, soup: BeautifulSoup) -> dict[str, str]:
    filter_results: dict[str, str] = {}
    for row in soup.find_all('tr'):
        link: Optional[Tag] = row.find('a')
        if link and link.get('href'):
            filename: str = link.get('href')
            unquoted_filename: str = unquote(filename)
            unquoted_filename_lower: str = unquoted_filename.lower()

            # Build filters
            has_language: bool = any(
                term in unquoted_filename for term in config.language) if config.language else True
            has_excluded: bool = any(
                term in unquoted_filename_lower for term in config.exclude) if config.exclude else False
            has_name: bool = config.name.lower() in unquoted_filename_lower if config.name else True

            if has_language and has_name and not has_excluded:
                full_url: str = urljoin(url, filename)
                filter_results[unquoted_filename] = full_url
    return filter_results


async def main():
    config: Config = request_config()
    if config.console:
        try:
            # Gets page's HTML
            url: str = CONSOLE_SOURCE_MAP[config.console]
            async with aiohttp.ClientSession() as session:
                response: ClientResponse = await session.get(url, headers={"User-Agent": "Mozilla/5.0"})
                soup: BeautifulSoup = BeautifulSoup(await response.text(), 'html.parser')

            # Find and filter urls
            scrapper_results: dict[str, str] = filter_roms(config, url, soup)
            selected_roms: dict[str, str] = {}

            while True:
                more: bool = True
                if scrapper_results:
                    print(f"Found {len(scrapper_results)} roms \n")
                    while more:
                        selected_rom: Optional[str] = make_question(list(scrapper_results.keys()), "ROM")
                        match selected_rom:
                            case None:
                                break
                            case "All":
                                for sr in scrapper_results.keys():
                                    selected_roms[sr] = scrapper_results[sr]
                                scrapper_results.clear()
                            case _:
                                selected_roms[selected_rom] = scrapper_results[selected_rom]
                                scrapper_results.pop(selected_rom)

                        if len(scrapper_results.keys()) == 0:
                            break

                        more: bool = (input("Add another result N/y: \n") == "y")
                        sys.stdout.write("\r" + " " * 30 + "\r")

                    if not (input("Search another rom? N/y: \n") == "y"):
                        break

                    sys.stdout.write("\r" + " " * 30 + "\r")
                    config = request_config(exclude_console=True)
                    scrapper_results = filter_roms(config, url, soup)
                else:
                    print("Nothing to download")
                    config = request_config(exclude_console=True)
                    scrapper_results = filter_roms(config, url, soup)

            if selected_roms:
                print(f"You will download: \n")
                for rom in selected_roms.keys():
                    print(" - " + rom)

                download_confirm: bool = (input("\n Start download? N/y: ") == "y")
                if download_confirm:
                    await download(urls=list(selected_roms.values()))  # Uses 'aria2c' to make all downloads
                else:
                    print("Download cancel")
        except KeyError:
            print(f"Invalid console name: {config.console}")
        except Exception as e:
            print(f"Unhandled error: {e}")
            raise e

asyncio.run(main())