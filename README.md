# CS271 Project 1: Blockchain with Lamport's Mutual Exclusion
Julia Novick
Winter 2025 CS271

## Overview
This project implements a distributed blockchain system using Lamport's mutual exclusion algorithm to ensure that transactions are processed correctly across multiple clients. 
Each client maintains a local copy of the blockchain and a balance table. Clients can issue transfer transactions (to send money to another client) and balance inquiries (to check their current balance). 
The system ensures mutual exclusion using Lamport's logical clocks and request queues.

The project is implemented in Python and uses UDP for communication between clients. It is designed to run on localhost with three clients.

---

## Features
- **Blockchain**: Each client maintains a local copy of the blockchain, which stores transactions as blocks.
- **Balance Table**: Each client maintains a balance table to track the balances of all clients.
- **Lamport's Mutual Exclusion**: Clients use Lamport's algorithm to achieve mutual exclusion and atomic operations when adding new blocks to the blockchain and updating the balance table.
- **Transfer Transactions**: Clients can transfer money to each other, provided they have sufficient balance.
- **Balance Inquiries**: Clients can check their current balance at any time.
- **Broadcasting**: New blocks are broadcasted to all clients using UDP.

---
 ## Run with these commands in seperate terminals for peer 1, peer 2, peer 3
 python3 udp_p2p.py 5000
 python3 udp_p2p.py 5001
 python3 udp_p2p.py 5002

## Once all clients are running, you can interact with them using the following commands:
- Transfer Money: Enter the amount to transfer and the recipient's number (1, 2, or 3)
- Check Balance: View the current balance of the client.
- Print Blockchain: Print the entire blockchain for the client.
- Print Balance Table: Print the balance table for all clients.

## Implementation Details
1. Blockchain
- Each block contains:
- Sender: The client sending the money.
- Receiver: The client receiving the money.
- Amount: The amount of money transferred.
- Hash Pointer: A pointer to the previous block and its hash (SHA-256).
The blockchain is implemented as a deque for efficient insertion at the head.

2. Balance Table
- The balance table is a dictionary that maps client ports to their balances.
- Each client starts with a balance of $10.

3. Lamport's Mutual Exclusion
- Each client maintains a logical clock and a request queue.
- When a client wants to add a block to the blockchain, it:
- Sends a REQUEST message to all other clients.
- Waits for ACK messages from all clients.
- Enters the critical section to add the block and update the balance table.
- Sends a RELEASE message to all clients after exiting the critical section.

4. UDP Communication
- Clients communicate using UDP sockets.
- Messages are serialized using JSON and include a Lamport timestamp for ordering.
- Why UDP:
- Take advantage of broadcasting for sending blocks to all clients
- Can tolerate occasional message loss
  - on localhost, message loss is highly unlikely because all communication happens within the same machine.
  - many of the trade-offs related to network reliability (e.g., packet loss, corruption, out-of-order delivery) are no longer relevant
- On localhost, messages are unlikely to arrive out of order, but UDP does not guarantee ordered delivery 
- To rely on message order (e.g., FIFO for mutual exclusion or blockchain updates), I implement my own mechanism to handle out-of-order messages with Lamport total ordering
