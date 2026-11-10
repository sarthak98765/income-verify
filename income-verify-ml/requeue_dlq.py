import argparse
import asyncio
import aio_pika
from config import RABBITMQ_DL_QUEUE, RABBITMQ_EXCHANGE, RABBITMQ_MAIN_QUEUE, RABBITMQ_URL
from logger import custom_logger

async def requeue(limit: int | None) -> int:
    """Move dead-lettered messages back to the main queue with their retry count reset."""
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    moved = 0
    async with connection:
        channel = await connection.channel()
        exchange = await channel.get_exchange(RABBITMQ_EXCHANGE, ensure=False)
        dlq = await channel.get_queue(RABBITMQ_DL_QUEUE, ensure=False)
        while limit is None or moved < limit:
            message = await dlq.get(fail=False)
            if message is None:
                break
            headers = {k: v for k, v in (message.headers or {}).items() if k not in ("x-retries", "x-error")}
            await exchange.publish(aio_pika.Message(body=message.body, headers=headers, delivery_mode=aio_pika.DeliveryMode.PERSISTENT, content_type="application/json"), routing_key=RABBITMQ_MAIN_QUEUE)
            await message.ack()
            moved += 1
            custom_logger.info(f"requeue | moved {message.body[:120]!r}")
    return moved

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="max messages to move")
    args = parser.parse_args()
    custom_logger.info(f"requeue | done, moved {asyncio.run(requeue(args.limit))} message(s)")
