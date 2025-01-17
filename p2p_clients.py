import socket
import threading
import sys

# Predefined ports and IP addresses for the peers
DEFAULT_PEERS = [
    ("127.0.0.1", 5000),  # Peer 1
    ("127.0.0.1", 5001),  # Peer 2
    ("127.0.0.1", 5002)   # Peer 3
]

# Create a mapping of addresses to peer identifiers
PEER_NAMES = {peer: f"Peer {i+1}" for i, peer in enumerate(DEFAULT_PEERS)}

class Peer:
    def __init__(self, my_ip, my_port, peer_addresses):
        self.my_address = (my_ip, my_port)
        self.peer_addresses = peer_addresses
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.my_address)
        self.running = True  # Flag to control the listener thread

    def listen(self):
        """Listen for incoming messages."""
        print(f"Listening on {self.my_address[0]}:{self.my_address[1]}")
        while self.running:
            try:
                self.socket.settimeout(1)  # Set a timeout to periodically check the running flag
                data, addr = self.socket.recvfrom(1024)
                if addr in PEER_NAMES:
                    print(f"Received from {PEER_NAMES[addr]}: {data.decode()}")
                else:
                    print(f"Received from unknown peer {addr}: {data.decode()}")
            except socket.timeout:
                continue  # Ignore timeouts and keep checking for messages
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

    def send_message(self, message):
        """Send a message to all other peers."""
        for peer in self.peer_addresses:
            try:
                self.socket.sendto(message.encode(), peer)
                print(f"Sent to {PEER_NAMES[peer]}: {message}")
            except Exception as e:
                print(f"Error sending to {PEER_NAMES[peer]}: {e}")

    def run(self):
        # Start the listening thread
        threading.Thread(target=self.listen, daemon=True).start()

        # Allow the user to send messages
        while self.running:
            message = input("Enter message to send (type 'exit' to quit): ")
            if message.lower() == "exit":
                print("Exiting...")
                self.running = False  # Stop the listener thread
                break
            self.send_message(message)

        self.socket.close()
        print("Socket closed. Goodbye!")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 udp_p2p.py <my_ip> <my_port>")
        print("Example: python3 udp_p2p.py 127.0.0.1 5000")
        sys.exit(1)

    my_ip = sys.argv[1]
    my_port = int(sys.argv[2])

    # Exclude this peer's address from the list of peers
    peer_addresses = [addr for addr in DEFAULT_PEERS if addr != (my_ip, my_port)]

    # Create and run the peer
    peer = Peer(my_ip, my_port, peer_addresses)
    peer.run()

if __name__ == "__main__":
    main()
