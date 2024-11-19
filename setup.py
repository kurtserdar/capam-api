from setuptools import setup, find_packages

setup(
    name="capam",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "requests",
        "pandas",
        "openpyxl",
        "configparser",
    ],
    include_package_data=True,
    description="A Python module for interacting with CyberArk REST API.",
    author="Serdar Kurt",
    author_email="serdar.kurt@outlook.com",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)