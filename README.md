# ACA-Py Wallet Groups Plugin

This repository contains a plugin for Aries Cloud Agent Python (ACA-Py) that adds a `group_id` to created wallets in multi-tenancy. This can be useful if multiple environments are using the same multi-tenant agent and you want to query wallets for a specific group only.

## Getting Started

There are two ways of using this plugin: locally or using Docker. The next sections describe the steps for both methods.

### Prerequisites

- Aries Cloud Agent Python (ACA-Py)
- Docker (optional)

### Installing

The plugin is hosted on PyPI, and can be installed:

```sh
pip install acapy-wallet-groups-plugin
```

## Usage

### Local

If the plugin has been installed using pip, you can just append `--plugin acapy_wallet_groups_plugin` to the aca-py startup command:

```sh
aca-py start --plugin acapy_wallet_groups_plugin <other params>
```

If you have cloned the repo and made changes locally, you can provide the path to this plugin as a command line argument to ACA-Py. (The path should point to the directory that contains `routes.py`, in this case `./acapy_wallet_groups_plugin`.)

```sh
aca-py start --plugin ./acapy_wallet_groups_plugin <other params>
```

> **NB:**
> When passing an env file or env vars to the aca-py instance, the plugin cannot be run with the multitenant admin API enabled. In other words, make sure to set `ACAPY_MULTITENANT_ADMIN=false` (as opposed to true), or ensure you have `--multitenant admin false` for cli arg, or `multitenant-admin: false` for YAML config file. If the multitenant admin API is enabled, the plugin will register and the endpoint will show up with the correct query fields in OpenAPI, _but_ under the hood not register the plugin correctly. That results in the behaviour where no group_id key is returned in the response and querying by group_id just returns all wallets.

### Docker

To run the plugin using Docker, build and run the Dockerfile:

```sh
# Build the image
docker build --tag acapy-with-wallet-groups .

# Run the container
docker run -it -p 3000:3000 -p 3001:3001 --rm acapy-with-wallet-groups
```

## Running tests

In order to run the tests, you'll need to install the dependencies first. The chosen package manager for this project is [Poetry](https://python-poetry.org/). The unit tests for this plugin have been written using [pytest](https://github.com/pytest-dev/pytest/). The following sections show how to install the dependencies and run the tests using Poetry.

### Poetry

```shell
# Install poetry
pip install poetry==2.1.3

# Activate the environment
poetry shell

# Install the dependencies
poetry install --with dev

# Run the tests
poetry run pytest ./tests
```
