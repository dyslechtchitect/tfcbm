import asyncio
import websockets
import logging
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def test_server(websocket, path):
    logging.info(f"Client connected from {websocket.remote_address}")
    try:
        async for message in websocket:
            logging.info(f"Received message of size: {len(message)} bytes")
            try:
                data = json.loads(message)
                response_message = f"Server received: {data.get('type', 'unknown')} message of size {len(message)} bytes"
                await websocket.send(json.dumps({"status": "success", "message": response_message}))
            except json.JSONDecodeError:
                response_message = f"Server received non-JSON message of size {len(message)} bytes"
                await websocket.send(json.dumps({"status": "error", "message": response_message}))
    except websockets.exceptions.ConnectionClosedOK:
        logging.info("Client disconnected gracefully.")
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"Client disconnected with error: {e}")
    except Exception as e:
        logging.error(f"Error in test_server: {e}")

async def main():
    configured_max_size = 10 * 1024 * 1024 # 10 MB
    logging.info(f"Starting test WebSocket server on ws://localhost:8766 with max_size: {configured_max_size} bytes")
    async with websockets.serve(test_server, "localhost", 8766, max_size=configured_max_size):
        await asyncio.Future() # Run forever

if __name__ == "__main__":
    asyncio.run(main())
