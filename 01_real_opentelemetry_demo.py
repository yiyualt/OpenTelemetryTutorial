"""
Real OpenTelemetry Demo - Using the actual OpenTelemetry library
This demonstrates how to instrument a Flask application with OpenTelemetry
"""

import time
import random
from flask import Flask, jsonify
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Initialize OpenTelemetry
def setup_opentelemetry():
    """Setup OpenTelemetry with console exporters for demo purposes"""
    
    # Setup Tracer
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)
    
    # Add console span exporter
    span_exporter = ConsoleSpanExporter()
    span_processor = BatchSpanProcessor(span_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    # Setup Metrics
    metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
    metric_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(metric_provider)
    meter = metrics.get_meter(__name__)
    
    return tracer, meter

# Create Flask app
app = Flask(__name__)

# Setup OpenTelemetry
tracer, meter = setup_opentelemetry()

# Instrument Flask and Requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Create metrics
request_counter = meter.create_counter(
    name="http_requests_total",
    description="Total number of HTTP requests"
)

response_time_histogram = meter.create_histogram(
    name="http_request_duration_seconds",
    description="HTTP request duration in seconds"
)

@app.route('/')
def home():
    """Home endpoint with tracing and metrics"""
    with tracer.start_as_current_span("home_request") as span:
        # Add attributes to the span
        span.set_attribute("http.route", "/")
        span.set_attribute("user.id", "demo_user")
        
        # Increment request counter
        request_counter.add(1, {"endpoint": "home", "method": "GET"})
        
        # Simulate some work
        time.sleep(10)
        
        # Record response time
        response_time_histogram.record(
            random.uniform(0.1, 0.5),
            {"endpoint": "home", "method": "GET"}
        )
        
        return jsonify({"message": "Hello from OpenTelemetry!", "status": "success"})

@app.route('/api/data')
def get_data():
    """API endpoint with nested spans"""
    with tracer.start_as_current_span("get_data_request") as parent_span:
        parent_span.set_attribute("http.route", "/api/data")
        
        # Increment request counter
        request_counter.add(1, {"endpoint": "api_data", "method": "GET"})
        
        # Simulate database query
        with tracer.start_as_current_span("database_query") as db_span:
            db_span.set_attribute("db.system", "postgresql")
            db_span.set_attribute("db.operation", "SELECT")
            time.sleep(random.uniform(0.2, 0.8))
        
        # Simulate external API call
        with tracer.start_as_current_span("external_api_call") as api_span:
            api_span.set_attribute("http.url", "https://api.example.com/data")
            api_span.set_attribute("http.method", "GET")
            time.sleep(random.uniform(0.1, 0.3))
        
        # Record response time
        response_time_histogram.record(
            random.uniform(0.3, 1.1),
            {"endpoint": "api_data", "method": "GET"}
        )
        
        return jsonify({
            "data": [1, 2, 3, 4, 5],
            "timestamp": time.time(),
            "status": "success"
        })

@app.route('/api/error')
def simulate_error():
    """Endpoint that simulates an error for demonstration"""
    with tracer.start_as_current_span("error_request") as span:
        span.set_attribute("http.route", "/api/error")
        
        # Increment request counter
        request_counter.add(1, {"endpoint": "api_error", "method": "GET"})
        
        # Simulate an error
        try:
            # Simulate some work
            time.sleep(0.1)
            
            # Simulate an error
            if random.random() < 0.7:  # 70% chance of error
                raise Exception("Simulated database connection error")
                
        except Exception as e:
            # Record the error in the span
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            return jsonify({"error": str(e)}), 500
        
        return jsonify({"message": "No error occurred"})

if __name__ == '__main__':
    print("Starting Flask app with OpenTelemetry instrumentation...")
    print("Visit http://localhost:5000 to see traces and metrics in the console")
    app.run(debug=True, port=8080) 