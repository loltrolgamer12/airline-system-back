class EventPublisher:
    def __init__(self):
        print("EventPublisher: Running without RabbitMQ")
    
    def publish(self, event_type: str, event_data: dict):
        print(f"Event would be published: {event_type} - {event_data}")
        # No hacer nada por ahora - solo log
