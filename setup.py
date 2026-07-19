from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

with open("requirements_dev.txt") as f:
    requirements_dev = f.read().splitlines()

with open("README.md") as f:
    long_description = f.read()

setup(
    name="sashimi",
    version="0.2.1",
    author="Vilim Stih @portugueslab",
    author_email="vilim@neuro.mpg.de",
    packages=find_packages(),
    install_requires=requirements,
    extras_require=dict(dev=requirements_dev, kinetix=["pyvcam"]),
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Science/Research",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="imaging microscopy lightsheet",
    description="A user-friendly software for efficient control of digital scanned light sheet microscopes (DSLMs).",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/portugueslab/sashimi",
    entry_points={
        "console_scripts": [
            "sashimi=sashimi.main:main",
            "sashimi-config=sashimi.config:cli_modify_config",
        ]
    },
)
