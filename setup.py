from setuptools import setup, find_packages

setup(
    name="fuser-custom-manager",
    version="1.0.0",
    description="A desktop app for browsing, downloading, and installing custom songs for the game Fuser",
    url="https://github.com/steven-gibbons-code/fuser-custom-manager",
    python_requires=">=3.11",
    packages=find_packages(include=["gui", "gui.*", "sources", "sources.*"]),
    py_modules=["app", "db", "downloader", "installer"],
    entry_points={
        "console_scripts": [
            "fuser-manager=app:main",
        ],
    },
    install_requires=[
        "PySide6>=6.6.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.3",
        "gdown>=5.1.0",
        "patool==4.0.4",
    ],
)