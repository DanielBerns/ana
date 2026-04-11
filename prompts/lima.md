# Goal
I want to build a new version of Ana, an event driven system, following an hexagonal architecture.

## The components of Ana

1. The Sensors are inbound Adapters. An instance of Sensor is created with a yaml formatted text with an url, execution schedule and limitation rate, auth credentials and a list of parameters. After creation, the Sensor can provide info for execution scheduling, and then start to retrieve data (from some foreign sources specified in the yaml formatted text) and store  data (txt, json, yaml, csv, md, docx, pdf, zip, jpeg, png)) and metadata (timestamp, origin, etc) in a ResourceRepository. Adapters receive and process Start, Pause, Resume, and Stop events. Adapters can emit AdapterError events.
2. The ResourceRepository has endpoints to receive and deliver different types of data (txt, json, yaml, csv, md, docx, pdf, zip, jpeg, png) and metadata (timestamp, origin, etc) and emits notification events to registered Processors and Thinkers
3. The Processors review, collect, ignore, aggregate, and transform data in the ResourceRepository and the events stream, and create, read, update and delete 4 tuples in a KnowledgeGraph. The Processors emit events for the Actors
4. The Actors are outbound Adapter. An instance of Actor is created with a yaml formatted text with an url, execution schedule and limitation rate, auth credentials and a list of parameters. After creation, the Actor can provide info for execution scheduling, and then start to publish data (to some foreign targets specified in the yaml formatted text).
  

