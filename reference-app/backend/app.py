from flask import Flask, render_template, request, jsonify
from jaeger_client import Config
from flask_opentracing import FlaskTracer
from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics

import pymongo
from flask_pymongo import PyMongo

app = Flask(__name__)
metrics = GunicornInternalPrometheusMetrics(app)

app.config["MONGO_DBNAME"] = "example-mongodb"
app.config[
    "MONGO_URI"
] = "mongodb://example-mongodb-svc.default.svc.cluster.local:27017/example-mongodb"

mongo = PyMongo(app)

def child_exit(server, worker):
    GunicornInternalPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)

def init_tracer():
    config = Config(
        config={
            "sampler": {"type": "const", "param": 1},
            "logging": True,
            "local_agent": {"reporting_host": "jaeger-operator-metrics.observability.svc.cluster.local"},
        },
        service_name="backend",
    )
    opentracing_tracer = config.initialize_tracer()
    return opentracing_tracer

jaeger_tracer = init_tracer()
tracer = FlaskTracer(jaeger_tracer, True, app)

@app.route("/")
def homepage():
    with opentracing.tracer.start_span("home-route") as span:
        response = {"message": "Home Endpoint"}
        span.set_tag("message", response)
        return jsonify(response)


@app.route("/api")
def my_api():
    with opentracing.tracer.start_span("api-route") as span:
            response = {"message": "API Endpoint"}
            span.set_tag("message", response)
            return jsonify(response)


@app.route("/star", methods=["POST"])
def add_star():
    with opentracing.tracer.start_span("star-route") as span:
        try:
            star = mongo.db.stars
            name = request.json["name"]
            distance = request.json["distance"]
            star_id = star.insert({"name": name, "distance": distance})
            new_star = star.find_one({"_id": star_id})
            output = {"name": new_star["name"], "distance": new_star["distance"]}

            response = jsonify({"result": output})
            span.set_tag("message", json.dumps(response))

            return response
        except Exception as e:
            error_message = "Missing name or distance in request"
            span.set_tag("error", error_message)
            return jsonify({"error": error_message}), 400


if __name__ == "__main__":
    app.run()
