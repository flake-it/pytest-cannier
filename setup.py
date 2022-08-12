#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup


with open("requirements.txt", "r") as f:
    install_requires = [l.strip() for l in f]


setup(
    license="MIT",
    version="0.1.0",
    name="pytest-cannier",

    python_requires=">=3.8",
    install_requires=install_requires,

    author="Owain Parry",
    author_email="oparry1@sheffield.ac.uk",
    
    packages=["pytest_cannier"],
    entry_points={"pytest11": ["cannier=pytest_cannier"]}
)
