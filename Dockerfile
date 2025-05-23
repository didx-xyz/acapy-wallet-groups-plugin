FROM ghcr.io/hyperledger/aries-cloudagent-python:py3.12-1.0.0

COPY acapy_wallet_groups_plugin acapy_wallet_groups_plugin
COPY config config

USER root
RUN chown aries:aries -R .
USER aries

ENTRYPOINT [ "aca-py" ]
CMD ["start", "--arg-file", "./config/defaults.yml", "--plugin-config", "./config/plugin.yml"]
