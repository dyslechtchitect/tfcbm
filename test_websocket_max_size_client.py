import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def send_large_message():
    uri = "ws://localhost:8766"
    try:
        async with websockets.connect(uri) as websocket:
            logging.info(f"Connected to {uri}")

            # Create a large message (e.g., 2MB of data)
            large_data = "A" * (2 * 1024 * 1024) # 2MB of 'A' characters
            message = json.dumps({"type": "large_test", "content": large_data})

            logging.info(f"Attempting to send message of size: {len(message)} bytes")
            await websocket.send(message)
            logging.info("Message sent successfully (or at least without immediate error).")

            response = await websocket.recv()
            logging.info(f"Received response: {response}")

    except websockets.exceptions.ConnectionClosedOK:
        logging.info("Connection closed gracefully by server.")
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"Connection closed with error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(send_large_message())
