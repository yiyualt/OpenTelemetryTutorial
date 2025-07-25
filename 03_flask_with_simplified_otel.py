"""
Flask Application with Simplified OpenTelemetry
This demonstrates how our simplified OpenTelemetry implementation works in a web context
"""

import time
import random
import threading
from flask import Flask, jsonify, request
from contextlib import contextmanager

# Import our simplified OpenTelemetry implementation
from simplified_opentelemetry import (
    get_tracer, flush_traces, SpanContext, SpanKind, SpanStatus
)

app = Flask(__name__)

# Get a tracer for our Flask app
tracer = get_tracer("flask_app")

# Simple middleware to trace all requests
@app.before_request
def before_request():
    """Trace incoming requests"""
    # Create a span context for the request
    request_context = SpanContext.generate()
    request.span_context = request_context
    
    # Start a span for the request
    span = tracer.start_span(
        name=f"{request.method} {request.path}",
        parent_context=None
    )
    span.kind = SpanKind.SERVER
    span.set_attribute("http.method", request.method)
    span.set_attribute("http.url", request.url)
    span.set_attribute("http.route", request.path)
    span.set_attribute("user_agent", request.headers.get("User-Agent", "Unknown"))
    
    # Store span in request context
    request.current_span = span

@app.after_request
def after_request(response):
    """Complete request tracing"""
    if hasattr(request, 'current_span'):
        span = request.current_span
        
        # Add response attributes
        span.set_attribute("http.status_code", response.status_code)
        span.set_attribute("http.response_size", len(response.get_data()))
        
        # Set status based on response code
        if response.status_code >= 400:
            span.set_status(SpanStatus.ERROR, f"HTTP {response.status_code}")
        else:
            span.set_status(SpanStatus.OK)
        
        # End the span
        tracer.end_span(span)
    
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle exceptions and trace them"""
    if hasattr(request, 'current_span'):
        span = request.current_span
        span.record_exception(e)
        span.set_status(SpanStatus.ERROR, str(e))
        tracer.end_span(span)
    
    return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    """Home endpoint with custom tracing"""
    with tracer.start_as_current_span("home_processing") as span:
        span.set_attribute("endpoint", "home")
        span.set_attribute("user.id", "demo_user")
        
        # Simulate some processing
        time.sleep(random.uniform(0.1, 0.3))
        
        # Add an event
        span.add_event("home_page_rendered", {"timestamp": time.time()})
        
        return jsonify({
            "message": "Hello from Simplified OpenTelemetry!",
            "status": "success",
            "trace_id": span.context.trace_id
        })

@app.route('/api/data')
def get_data():
    """API endpoint with nested spans"""
    with tracer.start_as_current_span("data_processing") as parent_span:
        parent_span.set_attribute("endpoint", "api_data")
        
        # Simulate database query
        with tracer.start_as_current_span("database_query") as db_span:
            db_span.set_attribute("db.system", "postgresql")
            db_span.set_attribute("db.operation", "SELECT")
            db_span.set_attribute("db.table", "users")
            
            # Simulate database work
            time.sleep(random.uniform(0.2, 0.5))
            
            # Simulate database result
            db_result = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
            db_span.set_attribute("db.rows_returned", len(db_result["users"]))
        
        # Simulate external API call
        with tracer.start_as_current_span("external_api_call") as api_span:
            api_span.set_attribute("http.url", "https://api.example.com/data")
            api_span.set_attribute("http.method", "GET")
            api_span.kind = SpanKind.CLIENT
            
            # Simulate API work
            time.sleep(random.uniform(0.1, 0.3))
            
            # Simulate API response
            api_result = {"external_data": [1, 2, 3, 4, 5]}
            api_span.set_attribute("http.status_code", 200)
        
        # Combine results
        result = {
            "data": db_result["users"],
            "external_data": api_result["external_data"],
            "timestamp": time.time(),
            "trace_id": parent_span.context.trace_id
        }
        
        return jsonify(result)

@app.route('/api/error')
def simulate_error():
    """Endpoint that simulates an error"""
    with tracer.start_as_current_span("error_simulation") as span:
        span.set_attribute("endpoint", "api_error")
        
        # Simulate some work
        time.sleep(0.1)
        
        # Simulate an error
        if random.random() < 0.7:  # 70% chance of error
            error_msg = "Simulated database connection error"
            span.add_event("error_occurred", {"error_type": "DatabaseError"})
            raise Exception(error_msg)
        
        return jsonify({"message": "No error occurred"})

@app.route('/api/performance')
def performance_test():
    """Endpoint to test performance tracing"""
    with tracer.start_as_current_span("performance_test") as span:
        span.set_attribute("endpoint", "api_performance")
        
        # Simulate different types of work
        operations = []
        
        # CPU-intensive operation
        with tracer.start_as_current_span("cpu_operation") as cpu_span:
            cpu_span.set_attribute("operation.type", "cpu_intensive")
            start = time.time()
            
            # Simulate CPU work
            result = 0
            for i in range(1000000):
                result += i * i
            
            cpu_time = time.time() - start
            cpu_span.set_attribute("cpu.time_seconds", cpu_time)
            cpu_span.set_attribute("cpu.result", result)
            operations.append({"type": "cpu", "time": cpu_time})
        
        # I/O operation
        with tracer.start_as_current_span("io_operation") as io_span:
            io_span.set_attribute("operation.type", "io_bound")
            start = time.time()
            
            # Simulate I/O work
            time.sleep(random.uniform(0.1, 0.3))
            
            io_time = time.time() - start
            io_span.set_attribute("io.time_seconds", io_time)
            operations.append({"type": "io", "time": io_time})
        
        # Network operation
        with tracer.start_as_current_span("network_operation") as net_span:
            net_span.set_attribute("operation.type", "network")
            start = time.time()
            
            # Simulate network work
            time.sleep(random.uniform(0.05, 0.15))
            
            net_time = time.time() - start
            net_span.set_attribute("network.time_seconds", net_time)
            operations.append({"type": "network", "time": net_time})
        
        total_time = span.duration()
        span.set_attribute("total.time_seconds", total_time)
        span.set_attribute("operations.count", len(operations))
        
        return jsonify({
            "operations": operations,
            "total_time": total_time,
            "trace_id": span.context.trace_id
        })

@app.route('/api/trace-info')
def trace_info():
    """Endpoint to show current trace information"""
    if hasattr(request, 'current_span'):
        span = request.current_span
        return jsonify({
            "trace_id": span.context.trace_id,
            "span_id": span.context.span_id,
            "span_name": span.name,
            "attributes": span.attributes,
            "duration": span.duration()
        })
    else:
        return jsonify({"error": "No active span"})

@app.route('/api/flush-traces')
def flush_traces_endpoint():
    """Endpoint to manually flush traces"""
    flush_traces()
    return jsonify({"message": "Traces flushed successfully"})

if __name__ == '__main__':
    print("Starting Flask app with Simplified OpenTelemetry...")
    print("Available endpoints:")
    print("  GET  /                    - Home page")
    print("  GET  /api/data            - Data endpoint with nested spans")
    print("  GET  /api/error           - Error simulation")
    print("  GET  /api/performance     - Performance test")
    print("  GET  /api/trace-info      - Current trace info")
    print("  GET  /api/flush-traces    - Manually flush traces")
    print("\nVisit http://localhost:5001 to see traces in the console")
    
    app.run(debug=True, port=5001) 