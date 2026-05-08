import os
from steely import Logger

GRAFANA_URL = os.getenv("GRAFANA_URL")
GRAFANA_INSTANCE_ID = os.getenv("GRAFANA_INSTANCE_ID")
GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN")

sink = Logger.set_global_grafana(
    url=GRAFANA_URL,
    labels={"service.name": "steely", "deployment.environment": "dev"},
    auth=(GRAFANA_INSTANCE_ID, GRAFANA_TOKEN),
    protocol="otlp",
    debug=True,
)

log = Logger('test')

log.info("Hello world")
log.warning("Something to watch")
log.error("Something went wrong")

#sink.flush()  # garante envio antes do processo terminar
#sink.close()

