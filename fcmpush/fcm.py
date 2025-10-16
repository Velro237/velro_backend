from firebase_admin import messaging

def send_to_token(registration_token: str, title: str, body: str, data: dict | None = None):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=registration_token,
    )
    response = messaging.send(message)
    return response

def send_to_tokens(registration_tokens: list[str], title: str, body: str, data: dict | None = None):
    if not registration_tokens:
        return None
    multicast = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=registration_tokens,
    )
    response = messaging.send_multicast(multicast)
    return response

def send_to_topic(topic: str, title: str, body: str, data: dict | None = None):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        topic=topic,
    )
    response = messaging.send(message)
    return response
