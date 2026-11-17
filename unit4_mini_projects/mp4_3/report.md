# Publish/Subscribe vs Request/Response for Many-to-Many Telemetry

## The problem
A plant monitors temperature and vibration on several lines. Dashboards, an alerting service, a data-lake loader and a digital twin all want every reading. In this many-to-many telemetry, how publishers and consumers are coupled decides how the system behaves as either side grows.

## What the demonstration showed
Three sensors publish to `plant1/lineA/temperature`, `plant1/lineA/vibration` and `plant1/lineB/temperature`. One aggregator holds a single wildcard subscription, `plant1/+/+`, logs everything, and applies per-topic alert limits (temperature 90, vibration 8, lineB temperature 85). Midway through the run I started a fourth sensor, `plant1/lineB/vibration`. The aggregator logged it as a new topic and began alerting on it, with no code change and no restart. No sensor ever learned that a consumer or a peer had been added.

## Why request/response scales worse
In a polling design (HTTP, or CoAP GET), each consumer must know every sensor's address and ask on its own schedule. With S sensors and C consumers there are up to S x C relationships, and every sensor must answer C polling streams. Adding a consumer therefore changes the load on every sensor, which matters most for battery-powered devices on LPWAN links where each radio wake-up costs energy (Section 4.2). Polling also forces a trade-off: poll fast and waste battery on unchanged readings, or poll slowly and miss events. Adding a sensor means editing every consumer's address list.

With a broker, each sensor keeps one connection and sends each reading once, independent of C, because the broker does the fan-out. Consumers need a topic filter rather than an address list, so relationships fall from S x C to S + C. The cost is a central broker that must be sized, secured and made highly available, plus one extra hop. For many-to-many telemetry that is usually a good trade, which is why Section 4.4 lists MQTT as best suited to "many-to-many telemetry, dashboards" and CoAP to direct device control and web integration.

## QoS: reliability chosen per stream
A publisher cannot see who received its message, so MQTT puts the guarantee on each hop through the broker. QoS 0 is fire-and-forget, QoS 1 is acknowledged and may duplicate, QoS 2 is exactly-once with a four-way handshake. I used QoS 1: a duplicated temperature reading is harmless, a silently lost one feeding a safety alert is not. The level is chosen per publish and per subscription, so a noisy vibration stream could use QoS 0 while alarms use QoS 1 or 2 on the same broker. In request/response, retry logic must be written into every client.

## Retained messages: current state on arrival
A pure subscriber would otherwise be blind until the next publish, which could be minutes on a slow sensor. A retained message lets the broker keep the latest value per topic and deliver it the instant a client subscribes. In the demo, a late-joining aggregator received the latest value of every topic in the same second, flagged RETAINED in its log. One caveat: only the most recent retained message is kept, so every reading must carry the retain flag, otherwise the broker holds a stale first value.

## Last Will and Testament: silence becomes an event
In a polling system a dead sensor shows up as a timeout that each consumer must implement and tune. In MQTT the sensor registers a will, `offline` on its status topic, when it connects. When I killed a sensor with SIGKILL, the broker published the will on its behalf and the aggregator logged an OFFLINE alert, though the sensor sent nothing. For a silent network loss the broker relies on the keep-alive timer (1.5 times the interval). A clean disconnect does not fire the will, so the sensor must publish `offline` itself, as the demo does. With a retained `online`, the status topic always reflects the true state, even for later subscribers.

## Limits
The broker is a single point of failure unless clustered, and a subscriber cannot ask for a value on demand or correlate a response to a request, so command-and-control traffic suits request/response better. Real plants therefore often combine CoAP or MQTT-SN on the constrained link with MQTT at the platform layer.

## Conclusion
As sensors and consumers multiply, the broker keeps each sensor's cost constant and each consumer's configuration to one topic filter, while QoS, retained messages and the Last Will supply tunable reliability, instant current state and explicit failure signals. Together these make publish/subscribe scale more gracefully than polling for many-to-many telemetry.
