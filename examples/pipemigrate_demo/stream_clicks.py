# click-stream loader: kafka topic -> hdfs staging
import json

from consumer_lib import KafkaReader

reader = KafkaReader(topic="clicks", group="etl")
for batch in reader.poll():
    for msg in batch:
        row = json.loads(msg.value)
        append_to_staging(row)
