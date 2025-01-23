import socket
import threading
import sys
from collections import deque
import json
import hashlib


# Predefined ports and IP addresses for the 3 peers
DEFAULT_PEERS = [
    ("127.0.0.1", 5000),  # Peer 1
    ("127.0.0.1", 5001),  # Peer 2
    ("127.0.0.1", 5002)   # Peer 3
]

class HashPointer:
    def __init__(self, previous_block, previous_hash):
        self.previous_block = previous_block  # Pointer to the previous block
        self.previous_hash = previous_hash    # Hash of the previous block
    
    def to_dict(self):
        """Convert the HashPointer to a dictionary for serialization."""
        return {
            'previous_hash': self.previous_hash,
            # Optional: include the sender and receiver of the previous block
            'previous_block': self.previous_block.to_dict() if self.previous_block else None
        }

    @classmethod
    def from_dict(cls, obj_dict, blockchain_lookup):
        """Reconstruct the HashPointer from a dictionary."""
        previous_block = blockchain_lookup.get(obj_dict['previous_hash'])
        return cls(
            previous_block=previous_block,
            previous_hash=obj_dict['previous_hash']
        )

class Block:
    def __init__(self, sender, receiver, amount, hash_pointer=None):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.hash_pointer = hash_pointer  # Hash pointer to the previous block
        self.hash = self.calculate_hash()  # Hash of the current block

    def to_dict(self):
        """Convert the Block object to a dictionary for serialization."""
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'hash_pointer': self.hash_pointer.to_dict() if self.hash_pointer else None,
            'hash': self.hash
        }

    @classmethod
    def from_dict(cls, obj_dict, blockchain_lookup):
        """Reconstruct the Block object from a dictionary."""
        hash_pointer = HashPointer.from_dict(obj_dict['hash_pointer'], blockchain_lookup) if obj_dict['hash_pointer'] else None
        return cls(
            sender=obj_dict['sender'],
            receiver=obj_dict['receiver'],
            amount=obj_dict['amount'],
            hash_pointer=hash_pointer
        )
    
    def calculate_hash(self):
        block_data = f"{self.sender},{self.receiver},{self.amount},{self.hash_pointer.previous_hash if self.hash_pointer else 'Genesis'}"
        return hashlib.sha256(block_data.encode()).hexdigest()



# Create a mapping of addresses to peer identifiers
PEER_NAMES = {peer: f"Peer {i+1}" for i, peer in enumerate(DEFAULT_PEERS)}

class Peer:
    def __init__(self, my_ip, my_port, peer_addresses):
        self.my_address = (my_ip, my_port) # initialize peer with address
        self.peer_addresses = peer_addresses # list of other peer's addresses
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.my_address) # bind to UDP socket
        self.running = True  # flag to control running state of listener thread
        self.blockchain = deque()  # Initialize an empty queue for the Blockchain
        self.block_lookup = {} # To look up blocks by hash
        self.initialize_blockchain()
        self.clock = 0

    def initialize_blockchain(self):
        # Create the genesis block
        genesis_block = Block("Genesis", "Genesis", 0)
        self.blockchain.appendleft(genesis_block)  # Add the genesis block to the queue
        self.block_lookup[genesis_block.hash] = genesis_block
        print("Blockchain initialized with Genesis block.")

    def add_block(self, sender, receiver, amount):
        # get block currently at head of blockchain
        prev_block = self.blockchain[0]
        # create hash pointer for prev block
        hash_pointer = HashPointer(prev_block, prev_block.hash)
        # create new block
        block = Block(sender, receiver, amount, hash_pointer)
        # add new block to head of blockchain
        self.blockchain.appendleft(block)
        self.block_lookup[block.hash] = block
        print(f"New block added to the head: {block.hash}")

    def listen(self):
        # Listen for incoming UDP messages
        print(f"Listening on {self.my_address[0]}:{self.my_address[1]}")
        while self.running:
            try:
                self.socket.settimeout(1)  # Set timeout to periodically check running flag
                data, addr = self.socket.recvfrom(1024) # Receive message
                message_data = json.loads(data.decode('utf-8'))

                 # extract lamport pair and block
                lamport_pair = message_data["lamport_pair"]
                received_clock = lamport_pair["clock"]
                sender_port = lamport_pair["port"]
                block_dict = message_data["block"]

                # Update the local clock based on the received Lamport pair
                self.clock = max(self.clock, received_clock) + 1
                print(f"Updated clock: {self.clock} after receiving Lamport pair: ({received_clock}, {sender_port}) from {PEER_NAMES[addr]}")

                # Deserialize block and add it to blockchain
                received_block = Block.from_dict(block_dict, self.block_lookup)
                # self.blockchain.appendleft(received_block)
                self.add_block(received_block.sender, received_block.receiver, received_block.amount)
                self.block_lookup[received_block.hash] = received_block

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
        # make sure to only accept int messages!!
        # send event: increment clock
        self.clock += 1
        # add block to head of blockchain
        self.add_block(self.my_address, DEFAULT_PEERS[receiver - 1], int(message))
        # serialize block and attach lamport pair (clock, port)
        block = self.blockchain[0]
        block_dict = block.to_dict()
        message_data = {
        "block": block_dict,
        "lamport_pair": {
            "clock": self.clock,  # current logical clock
            "port": self.my_address[1]  # process ID (port number)
        }
    }
        serialized_block = json.dumps(message_data).encode('utf-8')

        for peer in self.peer_addresses:
            try:
                self.socket.sendto(serialized_block, peer)
                print(f"Sent to {PEER_NAMES[peer]}: {message} with Lamport pair: ({self.clock}, {self.my_address[1]})")
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
