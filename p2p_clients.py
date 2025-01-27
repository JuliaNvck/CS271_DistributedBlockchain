import socket
import threading
import sys
from collections import deque
import json
import hashlib
import heapq
import time


# Predefined ports and IP addresses for the 3 peers
DEFAULT_PEERS = [
    ("127.0.0.1", 5000),  # Peer 1
    ("127.0.0.1", 5001),  # Peer 2
    ("127.0.0.1", 5002)   # Peer 3
]

class HashPointer:
    # Hash pointer object with: 1. pointer to prev block 2. hash of previous block
    def __init__(self, previous_block, previous_hash):
        self.previous_block = previous_block  # Pointer to the previous block
        self.previous_hash = previous_hash    # Hash of the previous block
    
    def to_dict(self):
        # Convert the HashPointer to a dict for serialization
        return {
            'previous_hash': self.previous_hash,
            'previous_block': self.previous_block.to_dict() if self.previous_block else None
        }

    @classmethod
    def from_dict(cls, obj_dict, blockchain_lookup):
        # Reconstruct HashPointer from a dict
        previous_block = blockchain_lookup.get(obj_dict['previous_hash'])
        return cls(
            previous_block=previous_block,
            previous_hash=obj_dict['previous_hash']
        )

class Block:
    # Block object with sender, receiver, amount, hash pointer to the previous block, hash of the current block
    def __init__(self, sender, receiver, amount, hash_pointer=None):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.hash_pointer = hash_pointer
        self.hash = self.calculate_hash()

    def to_dict(self):
        # Convert Block object to a dict for serialization
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'hash_pointer': self.hash_pointer.to_dict() if self.hash_pointer else None,
            'hash': self.hash
        }

    @classmethod
    def from_dict(cls, obj_dict, blockchain_lookup):
        # Reconstruct Block object from a dict
        hash_pointer = HashPointer.from_dict(obj_dict['hash_pointer'], blockchain_lookup) if obj_dict['hash_pointer'] else None
        return cls(
            sender=obj_dict['sender'],
            receiver=obj_dict['receiver'],
            amount=obj_dict['amount'],
            hash_pointer=hash_pointer
        )
    
    def calculate_hash(self):
        # Calculate hash of a block
        block_data = f"{self.sender},{self.receiver},{self.amount},{self.hash_pointer.previous_hash if self.hash_pointer else 'Genesis'}"
        return hashlib.sha256(block_data.encode()).hexdigest()



# Mapping of addresses to peer identifiers (peer 1, 2, 3)
PEER_NAMES = {peer: f"Peer {i+1}" for i, peer in enumerate(DEFAULT_PEERS)}

class Peer:
    def __init__(self, my_ip, my_port, peer_addresses):
        self.my_address = (my_ip, my_port) # initialize peer with address
        self.peer_addresses = peer_addresses # list of other peer's addresses
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # udp socket
        self.socket.bind(self.my_address) # bind to UDP socket
        self.running = True  # flag to control running state of listener thread
        self.blockchain = deque()  # initialize empty queue for the Blockchain
        self.block_lookup = {} # To look up blocks by hash
        self.initialize_blockchain()
        self.clock = 0 # local clock
        self.queue = []  # Request priority queue
        self.ack_set = set()  # Set to track ACKs
        self.mutex = False  # Mutex flag
        self.balance_table = {5000:10, 5001:10, 5002:10} # balance table dict, each client starts with 10$

    def initialize_blockchain(self):
        # Create the genesis block
        genesis_block = Block("Genesis", "Genesis", 0)
        self.blockchain.appendleft(genesis_block)  # Add the genesis block to the queue
        self.block_lookup[genesis_block.hash] = genesis_block
        print("Blockchain initialized with Genesis block.")

    def get_balance(self, port_num):
        # Get balance of specific peer or self
        return self.balance_table.get(port_num, 0)

    def can_afford_transfer(self, sender_port, amount):
        # Determine if client can afford transfer
        return self.get_balance(sender_port) >= amount
    
    def update_balance_table(self, sender_port, receiver_port, amount):
        # Update balance table based on transaction
        if self.can_afford_transfer(sender_port, amount):
            self.balance_table[sender_port] -= amount
            self.balance_table[receiver_port] += amount
            print(f"SUCCESS! Updated balances: {self.balance_table}")
        else:
            print(f"FAILED! Insufficient balance: {self.balance_table[sender_port]}")

    def print_blockchain(self):
        # Print the details of each block in the client's blockchain
        print(f"\nBlockchain for {self.my_address[1]} (most recent block first):")
        # Iterate through blockchain
        for block in self.blockchain:
            print(f"Block Hash: {block.hash}")
            print(f"  Sender: {block.sender}")
            print(f"  Receiver: {block.receiver}")
            print(f"  Amount: {block.amount}")
            if block.hash_pointer:
                print(f"  Previous Block Hash: {block.hash_pointer.previous_hash}")
            else:
                print("  Previous Block Hash: None (Genesis Block)")
        print("End of Blockchain\n")

    def print_balance_table(self):
        # Print the contents of the client's local copy of the balance table
        print(f"Balance Table: {self.balance_table}")

    def add_block(self, sender, receiver, amount):
        # Add block to head of blockchain
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

    def request_mutex(self):
        # increment clock and set lamport pair ⟨clock, port⟩
        lamport_pair = (self.clock + 1, self.my_address[1])
        # Add the request to the local priority queue (min heap)
        heapq.heappush(self.queue, lamport_pair)
        print(f"Requesting mutex with Lamport pair: {lamport_pair}")
        # Clear ack_set (new request)
        self.ack_set.clear()
        # Broadcast request to all clients
        request_message = {
            "type": "REQUEST",
            "lamport_pair": lamport_pair
        }
        self.broadcast_message(request_message)

    def handle_request(self, message, addr):
        # Handle received request
        received_lamport_pair = tuple(message["lamport_pair"])
        # update clock based on received message/lamport pair
        self.clock = max(self.clock, received_lamport_pair[0]) + 1
        # Add the request to the priority queue (lower timestamp, lower process id/port first)
        heapq.heappush(self.queue, received_lamport_pair)
        print(f"Received REQUEST from {addr} with Lamport pair: {received_lamport_pair}")
        print(f"Clock: {self.clock}")
        print(f"current queue: {self.queue}")

        # Send an ACK to sender
        ack_message = {
            "type": "ACK",
            "lamport_pair": (self.clock, self.my_address[1])
        }
        self.send_message(ack_message, addr)

    def handle_ack(self, message, addr):
        # Handle received ACK
        received_lamport_pair = tuple(message["lamport_pair"])
        # update clock based on received message/lamport pair
        self.clock = max(self.clock, received_lamport_pair[0]) + 1
        # add sender to the ack_set
        self.ack_set.add(addr)
        print(f"Received ACK from {addr} with Lamport pair: {received_lamport_pair}. Current ack_set: {self.ack_set}")
        print(f"Clock: {self.clock}")

        # Check if mutex can be granted
        self.check_mutex()

    def check_mutex(self):
        # Check if the head of the queue is this process's request and received all ACKs
        if self.queue and self.queue[0][1] == self.my_address[1] and len(self.ack_set) == len(self.peer_addresses):
            print("Mutex granted.")
            self.mutex = True

    def release_mutex(self):
        # Release mutex
        if self.mutex:
            print("Releasing mutex.")
            self.mutex = False
            # remove own request from request queue
            heapq.heappop(self.queue)

            # broadcast RELEASE message
            release_message = {
                "type": "RELEASE",
                "lamport_pair": (self.clock, self.my_address[1])
            }
            self.broadcast_message(release_message)
    
    def handle_release(self, message):
        # Handle received release
        released_lamport_pair = tuple(message["lamport_pair"])
        # update clock based on received message/lamport pair
        self.clock = max(self.clock, released_lamport_pair[0]) + 1
        # remove the released request from request queue
        self.queue = [req for req in self.queue if req[1] != released_lamport_pair[1]]
        # rebuild the heap
        heapq.heapify(self.queue)
        print(f"Processed RELEASE for Lamport pair: {released_lamport_pair}. Updated queue: {self.queue}")
        print(f"Clock: {self.clock}")
        # Check if the mutex can be granted
        self.check_mutex()
        # print query again (after logging to console)
        if not self.mutex:
            print("Would you like to issue a transaction, view balance, print the blockchain, or print the balance table? (0, 1, 2, 3) (type 'exit' to quit): ")

    def handle_block(self, block_dict, addr, lamport_pair):
        # Handle received block
        # update clock based on received message/lamport pair
        received_clock = lamport_pair[0]
        sender_port = lamport_pair[1]
        self.clock = max(self.clock, received_clock) + 1
        print(f"Clock: {self.clock}")
        # print(f"\nUpdated clock: {self.clock} after receiving Lamport pair: ({received_clock}, {sender_port}) from {PEER_NAMES[addr]}")
        # deserialize block and add it to blockchain
        received_block = Block.from_dict(block_dict, self.block_lookup)
        self.add_block(received_block.sender, received_block.receiver, received_block.amount)
        self.block_lookup[received_block.hash] = received_block    
        message = received_block.amount
        if addr in PEER_NAMES:
            print(f"Received from {PEER_NAMES[addr]}: {message} to {PEER_NAMES[tuple(received_block.receiver)]}")
        else:
            print(f"Received from unknown peer {addr}: {message}")
        # update balance table
        print(f"Balance before transfer: {self.get_balance(self.my_address[1])}")
        self.update_balance_table(sender_port, received_block.receiver[1], message)
        print(f"Balance after transfer: {self.get_balance(self.my_address[1])}")

    def listen(self):
        # Listen for incoming UDP messages
        print(f"Listening on {self.my_address[0]}:{self.my_address[1]}")
        while self.running:
            try:
                # set timeout to periodically check running flag
                self.socket.settimeout(1)
                data, addr = self.socket.recvfrom(1024) # receive message
                message_data = json.loads(data.decode('utf-8')) # decode message

                # extract type and lamport pair and block and handle message
                message_type = message_data["type"]
                if message_type == "REQUEST":
                    self.handle_request(message_data, addr)
                elif message_type == "ACK":
                    self.handle_ack(message_data, addr)
                elif message_type == "RELEASE":
                    self.handle_release(message_data)
                elif message_type == "BLOCK":
                    lamport_pair = message_data["lamport_pair"]
                    self.handle_block(message_data["block"], addr, lamport_pair)
                else:
                    print(f"Unknown message type received from {addr}: {message_data}")

            except socket.timeout:
                continue  # ignore timeouts and keep checking for messages
            except Exception as e:
                print(f"Error receiving data: {e}")
                break
    
    def broadcast_message(self, message):
        # Broadcast message to all other peers
        # increment clock before send event
        self.clock += 1
        # update clock in message
        message["lamport_pair"] = (self.clock, self.my_address[1])
        # serialize message
        serialized_message = json.dumps(message).encode('utf-8')
        # add a delay of 3 seconds
        time.sleep(3)
        print(f"Clock: {self.clock}")
        # iterate over all peer addresses and send the message
        for peer in self.peer_addresses:
            try:
                self.socket.sendto(serialized_message, peer)  # send the message via UDP
                print(f"Broadcasted message to {peer}: {message}")
            except Exception as e:
                print(f"Error broadcasting to {peer}: {e}")

    def send_message(self, message, receiver):
        # Send message to specific peer
        # increment clock for send event
        self.clock += 1
        # update clock in message
        message["lamport_pair"] = (self.clock, self.my_address[1])
        # serialize message
        serialized_message = json.dumps(message).encode('utf-8') 
        print(f"Clock: {self.clock}")
        try:
            # add a delay of 3 seconds
            time.sleep(3)
            self.socket.sendto(serialized_message, receiver)  # send the message via UDP
            print(f"Sent message to {receiver}: {message}")
        except Exception as e:
            print(f"Error broadcasting to {receiver}: {e}")

    def send_block(self, message, receiver):
        # Broadcast block to all other peers
        
        # Request the mutex
        # Broadcast REQUEST and wait for ACKs
        print("Requesting mutex before sending block...")
        self.request_mutex()

        # wait for mutex to be granted
        while not self.mutex:
            continue

        # Critical section: Add block to blockchain
        print("Mutex granted. Entering critical section to add block.")
        amount = int(message)
        #  verify client has enough balance to issue this transfer
        if not self.can_afford_transfer(self.my_address[1], amount):
            print("FAILED! Insufficient Balance.")
            # release mutex
            self.release_mutex()
            print("Exiting critical section and releasing mutex.")
        else: # sufficient balance
            # add block to head of blockchain
            self.add_block(self.my_address, DEFAULT_PEERS[receiver - 1], amount)
            # broadcast message to all other peers
            # serialize block and attach lamport pair (clock, port)
            block = self.blockchain[0]
            block_dict = block.to_dict()
            message_data = {
                "type": "BLOCK",
                "block": block_dict,
                "lamport_pair": (self.clock, self.my_address[1])
            }
            self.broadcast_message(message_data)

            # update balance table
            receiver_port = DEFAULT_PEERS[receiver - 1][1]
            print(f"Balance before transfer: {self.get_balance(self.my_address[1])}")
            self.update_balance_table(self.my_address[1], receiver_port, amount)
            print(f"Balance after transfer: {self.get_balance(self.my_address[1])}")

            # release the mutex
            self.release_mutex()
            print("Exiting critical section and releasing mutex.")

    def get_user_input(self):
        while self.running:
            print(f"Balance: {self.get_balance(self.my_address[1])}")
            operation_num = input("Would you like to issue a transaction, view balance, print the blockchain, or print the balance table? (0, 1, 2, 3) (type 'exit' to quit): ")
            # Check if the user wants to exit
            if operation_num.lower() == "exit":
                print("Exiting...")
                self.running = False  # Stop listener thread
                break
            # validate input is an int and within range - 0, 1, 2, 3
            if operation_num.isdigit() and 0 <= int(operation_num) <= 3:
                operation_num = int(operation_num)  # convert to int
                
                if operation_num == 0:
                    # issue transaction
                    while True:
                        message = input("Enter amount to transfer (type 'exit' to quit): ")
                        # check if user wants to exit
                        if message.lower() == "exit":
                            print("Exiting...")
                            self.running = False
                            break
                        
                        # validate input is an int
                        if message.isdigit():
                            message = int(message)
                            receiver = input("Enter receiver (1, 2, or 3): ")
                            
                            # validate receiver input
                            if receiver.isdigit() and 1 <= int(receiver) <= 3:
                                receiver = int(receiver)
                                self.send_block(message, receiver)
                                break  # exit loop after sending block
                            else:
                                print("Invalid receiver. Please enter 1, 2, or 3.")
                        else:
                            print("Invalid amount. Please enter a valid integer.")
                
                elif operation_num == 1:
                    # View balance
                    print(f"Balance: {self.get_balance(self.my_address[1])}")
                elif operation_num == 2:
                    # Print blockchain
                    self.print_blockchain()
                elif operation_num == 3:
                    # Print balance table
                    self.print_balance_table()
            else:
                # invalid input
                print("Invalid input. Please enter 0, 1, 2, or 3, or type 'exit' to quit.")


    def run(self):
        # Start listening thread
        threading.Thread(target=self.listen, daemon=True).start()
        # get user input & handle
        self.get_user_input()

        self.socket.close()
        print("Socket closed.")

def main():
    # read client’s port as arg (run on local host IP) from CLI
    if len(sys.argv) < 2:
        print("Usage: python3 udp_p2p.py <my_port>")
        print("Example: python3 udp_p2p.py 5000")
        sys.exit(1)

    my_ip = "127.0.0.1"
    my_port = int(sys.argv[1])

    # Exclude this peer's address from the list of peers
    peer_addresses = [addr for addr in DEFAULT_PEERS if addr != (my_ip, my_port)]

    # Create and run peer instance
    peer = Peer(my_ip, my_port, peer_addresses)
    peer.run()

if __name__ == "__main__":
    main()
