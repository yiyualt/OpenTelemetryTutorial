"""
Simplified OpenTelemetry Implementation from Scratch
This demonstrates the core concepts and data structures behind OpenTelemetry
"""

import time
import uuid
import threading
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from contextlib import contextmanager
import random

class SpanStatus(Enum):
    """Simplified span status enum"""
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"

class SpanKind(Enum):
    """Simplified span kind enum"""
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"

@dataclass
class SpanContext:
    """Simplified span context - represents the identity of a span"""
    trace_id: str
    span_id: str
    trace_flags: int = 1  # 1 = sampled
    trace_state: str = ""
    
    @classmethod
    def generate(cls) -> 'SpanContext':
        """Generate a new span context with random IDs"""
        return cls(
            trace_id=uuid.uuid4().hex,
            span_id=uuid.uuid4().hex[:16]
        )

@dataclass
class Span:
    """Simplified span implementation"""
    name: str
    context: SpanContext
    parent_context: Optional[SpanContext] = None
    kind: SpanKind = SpanKind.INTERNAL
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: SpanStatus = SpanStatus.UNSET
    status_message: str = ""
    error: Optional[Exception] = None
    
    def set_attribute(self, key: str, value: Any):
        """Set a span attribute"""
        self.attributes[key] = value
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the span"""
        event = {
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        }
        self.events.append(event)
    
    def record_exception(self, exception: Exception):
        """Record an exception in the span"""
        self.error = exception
        self.add_event("exception", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception)
        })
    
    def set_status(self, status: SpanStatus, message: str = ""):
        """Set the span status"""
        self.status = status
        self.status_message = message
    
    def end(self):
        """End the span"""
        self.end_time = time.time()
    
    def duration(self) -> float:
        """Get span duration in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for export"""
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.parent_context.span_id if self.parent_context else None,
            "kind": self.kind.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration(),
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status.value,
            "status_message": self.status_message,
            "error": str(self.error) if self.error else None
        }

class ConsoleSpanExporter:
    """Simple console exporter for spans"""
    
    def export(self, spans: List[Span]):
        """Export spans to console"""
        print("\n" + "="*80)
        print("EXPORTING SPANS TO CONSOLE")
        print("="*80)
        
        for span in spans:
            print(f"\nSpan: {span.name}")
            print(f"  Trace ID: {span.context.trace_id}")
            print(f"  Span ID: {span.context.span_id}")
            print(f"  Parent Span ID: {span.parent_context.span_id if span.parent_context else 'None'}")
            print(f"  Duration: {span.duration():.3f}s")
            print(f"  Status: {span.status.value}")
            
            if span.attributes:
                print(f"  Attributes: {json.dumps(span.attributes, indent=4)}")
            
            if span.events:
                print(f"  Events: {len(span.events)}")
                for event in span.events:
                    print(f"    - {event['name']}: {event.get('attributes', {})}")
            
            if span.error:
                print(f"  Error: {span.error}")
        
        print("="*80)

class BatchSpanProcessor:
    """Simple batch processor for spans"""
    
    def __init__(self, exporter: ConsoleSpanExporter, max_batch_size: int = 10):
        self.exporter = exporter
        self.max_batch_size = max_batch_size
        self.spans: List[Span] = []
        self.lock = threading.Lock()
    
    def add_span(self, span: Span):
        """Add a span to the batch"""
        with self.lock:
            self.spans.append(span)
            if len(self.spans) >= self.max_batch_size:
                self.flush()
    
    def flush(self):
        """Flush the current batch"""
        with self.lock:
            if self.spans:
                self.exporter.export(self.spans)
                self.spans.clear()

class Tracer:
    """Simplified tracer implementation"""
    
    def __init__(self, name: str, processor: BatchSpanProcessor):
        self.name = name
        self.processor = processor
        self._current_span = threading.local()
    
    def start_span(self, name: str, parent_context: Optional[SpanContext] = None) -> Span:
        """Start a new span"""
        context = SpanContext.generate()
        span = Span(
            name=name,
            context=context,
            parent_context=parent_context
        )
        return span
    
    def end_span(self, span: Span):
        """End a span and send it to the processor"""
        span.end()
        self.processor.add_span(span)
    
    @contextmanager
    def start_as_current_span(self, name: str, parent_context: Optional[SpanContext] = None):
        """Context manager for spans"""
        span = self.start_span(name, parent_context)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(SpanStatus.ERROR, str(e))
            raise
        finally:
            self.end_span(span)

class TracerProvider:
    """Simplified tracer provider"""
    
    def __init__(self):
        self.processor = BatchSpanProcessor(ConsoleSpanExporter())
        self.tracers: Dict[str, Tracer] = {}
    
    def get_tracer(self, name: str) -> Tracer:
        """Get or create a tracer"""
        if name not in self.tracers:
            self.tracers[name] = Tracer(name, self.processor)
        return self.tracers[name]
    
    def flush(self):
        """Flush all pending spans"""
        self.processor.flush()

# Global tracer provider
_tracer_provider = TracerProvider()

def get_tracer(name: str) -> Tracer:
    """Get a tracer from the global provider"""
    return _tracer_provider.get_tracer(name)

def flush_traces():
    """Flush all pending traces"""
    _tracer_provider.flush()

# Example usage
def demo_simple_tracing():
    """Demonstrate simple tracing functionality"""
    print("=== Simple OpenTelemetry Demo ===")
    
    tracer = get_tracer("demo")
    
    # Simple span
    with tracer.start_as_current_span("main_operation") as span:
        span.set_attribute("user.id", "demo_user")
        span.set_attribute("operation.type", "demo")
        
        print("Main operation started...")
        time.sleep(0.1)
        
        # Nested span
        with tracer.start_as_current_span("sub_operation") as sub_span:
            sub_span.set_attribute("sub.operation.type", "calculation")
            print("Sub operation started...")
            time.sleep(0.05)
            
            # Simulate some work
            result = random.randint(1, 100)
            sub_span.set_attribute("calculation.result", result)
            print(f"Calculation result: {result}")
        
        print("Main operation completed")
    
    # Error span
    with tracer.start_as_current_span("error_operation") as error_span:
        error_span.set_attribute("operation.type", "error_demo")
        print("Error operation started...")
        
        try:
            # Simulate an error
            raise ValueError("This is a simulated error for demonstration")
        except Exception as e:
            error_span.record_exception(e)
            error_span.set_status(SpanStatus.ERROR, str(e))
            print(f"Error occurred: {e}")
    
    # Flush all traces
    flush_traces()

if __name__ == "__main__":
    demo_simple_tracing() 