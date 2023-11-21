FROM ghcr.io/hyperledger/aries-cloudagent-python:py3.9-0.10.1

COPY acapy_wallet_groups_plugin acapy_wallet_groups_plugin
COPY config config

USER root
RUN chown indy:indy -R .
USER indy

ENTRYPOINT [ "aca-py" ]
CMD ["start", "--arg-file", "./config/defaults.yml", "--plugin-config", "./config/plugin.yml"]
