import json
import pika
import os
from src.core.config import settings

class EventPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.setup_connection()
    
    def setup_connection(self):
        try:
            # RabbitMQ connection parameters
            credentials = pika.PlainCredentials(
                settings.RABBITMQ_USER, 
                settings.RABBITMQ_PASSWORD
            )
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=int(settings.RABBITMQ_PORT),
                credentials=credentials
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
        except Exception as e:
            print(f"Failed to connect to RabbitMQ: {e}")
    
    def publish(self, event_type: str, event_data: dict):
        if not self.connection or self.connection.is_closed:
            self.setup_connection()
            
        # Ensure connection is established
        if not self.connection or not self.channel:
            print("Failed to publish event: RabbitMQ connection not available")
            return
        
        try:
            # Prepare the message
            message = {
                "event_type": event_type,
                "data": event_data
            }
            
            # Publish to RabbitMQ
            self.channel.basic_publish(
                exchange="airline_events",
                routing_key=event_type,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type="application/json"
                )
            )
            print(f"Published event: {event_type}")
        except Exception as e:
            print(f"Failed to publish event: {e}")
