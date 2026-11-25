"""Identity and authorization obligations at a human actor's request boundary."""

AUTHENTICATION = "human.authentication"
HUMAN_KEYS = {AUTHENTICATION, "human.authorization"}
SERVICE_KEYS = {"service_relation.authentication", "service_relation.authorization"}
OUT_OF_SCOPE = "服务间身份认证和权限控制不在当前关注点范围内"


def request_actor(direction, kind, sender_id, sender_type, receiver_id, receiver_type):
    if (
        direction == "request"
        and kind != "action"
        and sender_id != receiver_id
        and receiver_type == "service"
    ):
        return sender_type
    return None


def human_request(step):
    sender, receiver = step["sender"], step["receiver"]
    return (
        request_actor(
            step["direction"],
            step["kind"],
            sender["id"],
            sender.get("type"),
            receiver["id"],
            receiver.get("type"),
        )
        == "human"
    )


def in_scope(key, target, step):
    if key in SERVICE_KEYS:
        return False
    if key in HUMAN_KEYS:
        return bool(step and target == "sender" and human_request(step))
    return True
