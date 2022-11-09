# ACA-Py Wallet Groups Plugin

This repository contains a plugin for Aries Cloud Agent Python (ACA-Py) that adds a `group_id` to created wallets in multi-tenancy. This can be useful if multiple environments are using the same multi-tenant agent and you want to query wallets for a specific group only.

## Table of Contents

- [About](#about)
- [Getting Started](#getting_started)
- [Usage](#usage)

## Getting Started <a name = "getting_started"></a>

There are two ways of using this plugin: locally or using Docker. The next sections describe the steps for both methods.

### Prerequisites

#### Local usage

- Aries Cloud Agent Python (ACA-Py)

#### Docker

- Docker

### Installing

To install this plugin, all you'll need to do is clone this repository.

## Usage <a name = "usage"></a>

### Local

To run ACA-Py with this plugin locally, you'll need to provide the path to this plugin as a command line argument to ACA-Py. The path should point to the directory that contains `routes.py`, in this case `./acapy_wallet_groups_plugin`.

```sh
aca-py start --plugin ./acapy_wallet_groups_plugin <other params>
```

### Docker

To run the plugin using Docker, build and run the Dockerfile:

```sh
# Build the image
docker build --tag acapy-with-wallet-groups .

# Run the container
docker run -it -p 3000:3000 -p 3001:3001 --rm acapy-with-wallet-groups
```

## Running tests <a name = "tests"></a>

In order to run the tests, you'll need to install the dependencies first. The chosen package manager for this project is [Poetry](https://python-poetry.org/). The unit tests for this plugin have been written using [pytest](https://github.com/pytest-dev/pytest/). The following sections show how to install the dependencies and run the tests using Poetry.

### Poetry

```shell
# Uncomment if you don't have poetry installed
# pip install poetry

# Activate the environment
poetry shell

# Install the dependencies
poetry install

# Run the tests
poetry run pytest ./tests
```
