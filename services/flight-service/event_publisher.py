import json
import pika
import os
from typing import Dict, Any
from datetime import datetime
import time

class EventPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.max_retries = 3
        self.retry_delay = 5
        self.setup_connection()
    
    def setup_connection(self):
        retries = 0
        while retries < self.max_retries:
            try:
                # RabbitMQ connection parameters
                rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
                rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
                rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
                rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
                
                credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
                parameters = pika.ConnectionParameters(
                    host=rabbitmq_host,
                    port=rabbitmq_port,
                    credentials=credentials,
                    connection_attempts=3,
                    retry_delay=2
                )
                
                # Connect to RabbitMQ
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                # Declare exchange for events
                self.channel.exchange_declare(
                    exchange="airline_events", 
                    exchange_type="topic",
                    durable=True
                )
                
                # Declare queues for different event types
                self.channel.queue_declare(queue="flight_events", durable=True)
                self.channel.queue_declare(queue="passenger_events", durable=True)
                self.channel.queue_declare(queue="reservation_events", durable=True)
                
                # Bind queues to exchange
                self.channel.queue_bind(
                    exchange="airline_events",
                    queue="flight_events",
                    routing_key="flight.*"
                )
                
                print("✅ Connected to RabbitMQ successfully")
                return
                
            except Exception as e:
                retries += 1
                print(f"❌ Failed to connect to RabbitMQ (attempt {retries}/{self.max_retries}): {e}")
                if retries < self.max_retries:
                    print(f"🔄 Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print("💔 Max retries reached. RabbitMQ unavailable.")
    
    def publish(self, event_type: str, event_data: Dict[Any, Any]):
        if not self.connection or self.connection.is_closed:
            print("🔄 Reconnecting to RabbitMQ...")
            self.setup_connection()
            
        # Ensure connection is established
        if not self.connection or not self.channel:
            print("❌ Failed to publish event: RabbitMQ connection not available")
            return False
        
        try:
            # Prepare the message
            message = {
                "event_type": event_type,
                "data": event_data,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "flight-service"
            }
            
            # Publish to RabbitMQ
            self.channel.basic_publish(
                exchange="airline_events",
                routing_key=event_type,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type="application/json",
                    headers={"source": "flight-service"}
                )
            )
            print(f"📤 Published event: {event_type}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to publish event: {e}")
            return False
    
    def close_connection(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("🔌 RabbitMQ connection closed")

# Instancia global
event_publisher = EventPublisher()
