FROM bcgovimages/aries-cloudagent:py36-1.16-1_0.8.0

COPY acapy_wallet_groups_plugin acapy_wallet_groups_plugin
COPY config config

USER root
RUN chown indy:indy -R .
USER indy

ENTRYPOINT [ "aca-py" ]
CMD ["start", "--arg-file", "./config/defaults.yml", "--plugin-config", "./config/plugin.yml"]
