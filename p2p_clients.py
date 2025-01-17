import socket
import threading
import sys
from queue import Queue
import json
import hashlib


# Predefined ports and IP addresses for the 3 peers
DEFAULT_PEERS = [
    ("127.0.0.1", 5000),  # Peer 1
    ("127.0.0.1", 5001),  # Peer 2
    ("127.0.0.1", 5002)   # Peer 3
]

class Block:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        # self.previous_hash = previous_hash
        # self.hash = calculate_hash(sender, receiver, amount, previous_hash)

    def to_dict(self):
            """Convert the Block object to a dictionary for serialization."""
            return {
                'sender': self.sender,
                'receiver': self.receiver,
                'amount': self.amount
            }

    @classmethod
    def from_dict(cls, obj_dict):
        """Reconstruct the Block object from a dictionary."""
        return cls(
            sender=obj_dict['sender'],
            receiver=obj_dict['receiver'],
            amount=obj_dict['amount']
        )


# Create a mapping of addresses to peer identifiers
PEER_NAMES = {peer: f"Peer {i+1}" for i, peer in enumerate(DEFAULT_PEERS)}

class Peer:
    def __init__(self, my_ip, my_port, peer_addresses):
        self.my_address = (my_ip, my_port) # initialize peer with address
        self.peer_addresses = peer_addresses # list of other peer's addresses
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.my_address) # bind to UDP socket
        self.running = True  # flag to control running state of listener thread
        self.queue = Queue()  # Initialize an empty queue for the Blockchain

    def listen(self):
        # Listen for incoming UDP messages
        print(f"Listening on {self.my_address[0]}:{self.my_address[1]}")
        while self.running:
            try:
                self.socket.settimeout(1)  # Set timeout to periodically check running flag
                data, addr = self.socket.recvfrom(1024) # Receive message
                block_dict = json.loads(data.decode('utf-8'))
                received_block = Block.from_dict(block_dict)
                self.queue.put(received_block)
                message = received_block.amount
                if addr in PEER_NAMES:
                    print(f"Received from {PEER_NAMES[addr]}: {message}")
                else:
                    print(f"Received from unknown peer {addr}: {message}")
            except socket.timeout:
                continue  # Ignore timeouts and keep checking for messages
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

    def send_message(self, message, receiver):
        # Broadcast message to all other peers
        # transaction = [self.my_address, self.peer_addresses[receiver - 1], int(message)]
        block = Block(self.my_address, DEFAULT_PEERS[receiver - 1], int(message))
        self.queue.put(block)
        block_dict = block.to_dict()
        serialized_block = json.dumps(block_dict).encode('utf-8')

        for peer in self.peer_addresses:
            try:
                self.socket.sendto(serialized_block, peer)
                print(f"Sent to {PEER_NAMES[peer]}: {message}")
            except Exception as e:
                print(f"Error sending to {PEER_NAMES[peer]}: {e}")

    def run(self):
        # Start listening thread
        threading.Thread(target=self.listen, daemon=True).start()

        # Allow the user to send messages
        while self.running:
            message = input("Enter message to send (type 'exit' to quit): ")
            if message.lower() == "exit": # user inputs 'exit'
                print("Exiting...")
                self.running = False  # Stop listener thread
                break
            else:
                receiver = int(input("Enter receiver (1, 2, or 3): "))
            self.send_message(message, receiver)

        self.socket.close()
        print("Socket closed.")

def main():
    # read client’s port as arg (run on local host IP) from CLI
    if len(sys.argv) < 2:
        print("Usage: python3 udp_p2p.py <my_ip> <my_port>")
        print("Example: python3 udp_p2p.py 127.0.0.1 5000")
        sys.exit(1)

    my_ip = "127.0.0.1"
    my_port = int(sys.argv[1])

    # Exclude this peer's address from the list of peers
    peer_addresses = [addr for addr in DEFAULT_PEERS if addr != (my_ip, my_port)]

    # Create and run the peer instance
    peer = Peer(my_ip, my_port, peer_addresses)
    peer.run()

if __name__ == "__main__":
    main()
