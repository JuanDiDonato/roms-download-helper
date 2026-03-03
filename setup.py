from setuptools import setup, find_packages

setup(
    name="roms-download-helper-batocera",
    version="0.1.0",
    description="Download ROM files for retro consoles",
    author="Dido",
    python_requires=">=3.8",
    packages=find_packages(where="."),
    install_requires=[
        "aiohttp",
        "beautifulsoup4",
    ],
    entry_points={
        "console_scripts": [
            "rdhb=rdhb.main:init",
        ],
    },
)